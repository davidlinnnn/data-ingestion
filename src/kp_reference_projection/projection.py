"""The reader, the work table and `reconcile_doc` of the reference projection (#127).

- The reader reads the Change Feed and turns each event into a row of the work table, one per
  `document_uid`, in the transaction that saves its cursor; it reports the cursor only after
  that commit, so an event is durable before its position is (DR A3). It reports the cursor on
  every read, with or without events, which the platform's lag gauge reads.
- Workers take rows by priority, `narrowing` first, and run `reconcile_doc` for the uid. A row
  is one uid, so runs of a uid are serialised and its backlog runs once; an event that comes
  during a run bumps `requested`, and the run then leaves the row for one more run (DR A9).
  Coalescing keeps a row's highest priority, so a deletion is never demoted behind an update.
  A merged run never spans a deletion (DR A3): a run reads the state after the newest event it
  merged, so it sees the deletion, and a resubmitted Document gets a new `document_uid`.
- `reconcile_doc` converges on the Document's current state, whatever order its events came
  in: it removes what the state no longer allows, registers before it writes, confirms after,
  and reports what its store holds when it drops a write (DR §5.2, spec §7.4).
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from typing import Any

from prometheus_client import Counter, Gauge, Histogram
from psycopg_pool import AsyncConnectionPool

from kp_sdk import PlatformError
from kp_sdk.projection import ProjectionClient

log = logging.getLogger(__name__)

PRIORITY = {"narrowing": 0, "normal": 1, "background": 2}
STAGES = ["write"]  # what KP_PIPELINES registers for this projection (spec §7.3)
METHOD_VERSION = "reference-projection@1"

write_seconds = Histogram(
    "kp_projection_write_seconds",
    "time from a registration to the confirmation of its store write",
    buckets=(0.1, 0.5, 1, 5, 15, 60, 300, 900, 1800),
)
removal_seconds = Histogram(
    "kp_projection_removal_seconds",
    "time from a narrowing event to the removed fact the platform took",
    buckets=(1, 5, 15, 60, 120, 300, 600, 1200, 3600),
)
failures = Counter(
    "kp_projection_failures_total",
    "calls or runs that failed, by step and reason (a platform reason code or an error type)",
    ["step", "reason"],
)
backlog = Gauge("kp_projection_backlog", "Documents waiting in the work table", ["priority"])


class Unsettled(Exception):
    """The state kept moving while the run wrote: the run is retried."""


class Expired(Exception):
    """The cursor is past the feed's retention: the projection needs a bootstrap (#280, #281)."""


class _Reports:
    """Reports that change what a heartbeat counts hold a window; the heartbeat waits until
    none is open and holds new ones back, so no report is in flight while it counts (§7.4)."""

    def __init__(self) -> None:
        self._open, self._counting = 0, False
        self._changed = asyncio.Condition()

    @asynccontextmanager
    async def window(self) -> AsyncIterator[None]:
        async with self._changed:
            await self._changed.wait_for(lambda: not self._counting)
            self._open += 1
        try:
            yield
        finally:
            async with self._changed:
                self._open -= 1
                self._changed.notify_all()

    @asynccontextmanager
    async def quiet(self) -> AsyncIterator[None]:
        async with self._changed:
            self._counting = True
            await self._changed.wait_for(lambda: self._open == 0)
        try:
            yield
        finally:
            async with self._changed:
                self._counting = False
                self._changed.notify_all()


class Projection:
    """Projection `sdk.projection`'s Build `build_id` over its store in `pool`'s database, which
    holds SCHEMA. One process runs it: `start` takes back every claim (the CLI holds a lock)."""

    def __init__(
        self,
        sdk: ProjectionClient,
        pool: AsyncConnectionPool[Any],
        build_id: str,
        *,
        poll_s: float = 1.0,
        retry_s: float = 30.0,
        run_timeout_s: float = 600.0,
        page: int = 100,
    ) -> None:
        self.sdk, self.pool, self.build_id = sdk, pool, build_id
        self.poll_s, self.retry_s, self.run_timeout_s, self.page = (
            poll_s,
            retry_s,
            run_timeout_s,
            page,
        )
        self.reports = _Reports()

    # The reader

    async def start(self) -> None:
        """Takes back the claims of a process that ended, fixes the starting position of a new
        reader at the feed's head, and creates the Build as `building` until it switches."""
        async with self.pool.connection() as conn:
            await conn.execute("UPDATE work SET claimed = false WHERE claimed")
            saved = await (await conn.execute("SELECT 1 FROM reader")).fetchone()
            # A recorded switch, sent or not, means the Build was reported `building` before.
            switched = await (
                await conn.execute("SELECT 1 FROM build WHERE build_id = %s", (self.build_id,))
            ).fetchone()
        if not saved:
            # shortcut: no bootstrap, so Documents unchanged since the head are not read; #280.
            head = (await self.sdk.feed(None))["next_cursor"]
            async with self.pool.connection() as conn:
                await conn.execute("INSERT INTO reader (cursor) VALUES (%s)", (head,))
        if not switched:
            await self.sdk.report_build(self.build_id, {"state": "building"})

    async def read_once(self) -> int:
        """Reads one page after the saved cursor, queues its events and reports the cursor;
        switches the Build to `serving` once a read finds no more. Returns the events read."""
        async with self.pool.connection() as conn:
            [(cursor,)] = await (await conn.execute("SELECT cursor FROM reader")).fetchall()
        try:
            page = await self.sdk.feed(cursor, self.page)
        except PlatformError as error:
            if error.reason == "CURSOR_EXPIRED":
                raise Expired from error
            raise
        await self.enqueue(page["events"], page["next_cursor"])
        try:
            await self.sdk.report_cursor(page["next_cursor"])
        except PlatformError as error:  # CURSOR_BACKWARDS needs a cursor reset: #281
            failures.labels("report_cursor", error.reason).inc()
            log.warning(
                "cursor refused: projection=%s reason=%s", self.sdk.projection, error.reason
            )
        if not page["events"]:
            await self._switch(page["next_cursor"])
        return len(page["events"])

    async def enqueue(self, events: list[dict[str, Any]], next_cursor: str) -> None:
        """Queues each event's Document and saves `next_cursor`, in one transaction. An event
        without a `document_uid` (`source_profile_changed`, or a kind this reader does not
        know) is logged and skipped; one with a `document_uid` is reconciled whatever its kind
        (DR A2, ruling 2026-11-22)."""
        async with self.pool.connection() as conn, conn.transaction():
            for event in events:
                uid = event.get("document_uid")
                if uid is None:  # source_profile_changed is #280's
                    log.info("event skipped: kind=%s position=%s", event["kind"], event["position"])
                    continue
                narrowing = event["priority"] == "narrowing"
                await conn.execute(
                    "INSERT INTO work (document_uid, priority, at_least, narrowed_at)"
                    " VALUES (%s, %s, %s, %s) ON CONFLICT (document_uid) DO UPDATE SET"
                    " priority = least(work.priority, excluded.priority),"
                    " at_least = excluded.at_least, requested = work.requested + 1,"
                    " not_before = now(),"
                    " narrowed_at = coalesce(work.narrowed_at, excluded.narrowed_at)",
                    (
                        uid,
                        PRIORITY.get(event["priority"], PRIORITY["normal"]),
                        event["position"],
                        event["occurred_at"] if narrowing else None,
                    ),
                )
            await conn.execute("UPDATE reader SET cursor = %s", (next_cursor,))
            counts = await conn.execute("SELECT priority, count(*) FROM work GROUP BY priority")
            waiting = dict(await counts.fetchall())
        for name, value in PRIORITY.items():
            backlog.labels(name).set(waiting.get(value, 0))

    async def _switch(self, feed_position: str) -> None:
        async with self.pool.connection() as conn:
            # Recorded before it is sent, so a resend after a crash carries the same number.
            await conn.execute(
                "INSERT INTO build (build_id, switch_seq) VALUES (%s, nextval('switch_seq'))"
                " ON CONFLICT DO NOTHING",
                (self.build_id,),
            )
            [(switch_seq, serving)] = await (
                await conn.execute(
                    "SELECT switch_seq, serving FROM build WHERE build_id = %s", (self.build_id,)
                )
            ).fetchall()
        if serving:
            return
        report = {
            "state": "serving",
            "switch_seq": switch_seq,
            "replaces": None,  # shortcut: one Build; a new Build replacing one is #280's
            "feed_position": feed_position,
        }
        try:
            await self.sdk.report_build(self.build_id, report)
        except PlatformError as error:  # GATE_FAILED: tried again after the next read
            failures.labels("switch", error.reason).inc()
            log.warning("switch refused: build_id=%s reason=%s", self.build_id, error.reason)
            return
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE build SET serving = true WHERE build_id = %s", (self.build_id,)
            )
        log.info("build serving: build_id=%s switch_seq=%s", self.build_id, switch_seq)

    # Workers

    async def work_once(self, narrowing_only: bool = False) -> bool:
        """Runs `reconcile_doc` for the first row by priority, or only a `narrowing` one;
        False when none is due. A failed run is retried after `retry_s`."""
        async with self.pool.connection() as conn:
            claimed = await (
                await conn.execute(
                    "UPDATE work SET claimed = true WHERE document_uid = ("
                    " SELECT document_uid FROM work WHERE NOT claimed AND not_before <= now()"
                    " AND priority <= %s ORDER BY priority, queued_at LIMIT 1"
                    " FOR UPDATE SKIP LOCKED) RETURNING document_uid, requested, at_least,"
                    " narrowed_at",
                    (PRIORITY["narrowing"] if narrowing_only else PRIORITY["background"],),
                )
            ).fetchone()
        if not claimed:
            return False
        uid, requested, at_least, narrowed_at = claimed
        try:
            async with asyncio.timeout(self.run_timeout_s):
                await self.reconcile_doc(uid, at_least, narrowed_at)
        except Exception as error:
            failures.labels("reconcile", _reason(error)).inc()
            log.warning("run failed: document_uid=%s reason=%s", uid, _reason(error))
            async with self.pool.connection() as conn:
                await conn.execute(
                    "UPDATE work SET claimed = false,"
                    " not_before = now() + make_interval(secs => %s) WHERE document_uid = %s",
                    (self.retry_s, uid),
                )
            return True
        async with self.pool.connection() as conn:
            done = await conn.execute(
                "DELETE FROM work WHERE document_uid = %s AND requested = %s", (uid, requested)
            )
            if not done.rowcount:  # an event came during the run: one more run
                await conn.execute(
                    "UPDATE work SET claimed = false WHERE document_uid = %s", (uid,)
                )
        return True

    # reconcile_doc

    async def reconcile_doc(
        self, uid: str, at_least: str | None = None, narrowed_at: datetime | None = None
    ) -> None:
        """Brings the store's entries of `uid` to the Document's current state."""
        dropped = None
        for _ in range(3):
            async with self.reports.window():
                await self._flush(uid, narrowed_at)
            state = await self.sdk.document_state(uid, at_least)
            # Not active (deleted, later withdrawn), no longer known, or no current revision
            # (DR §6): nothing may be served.
            current = state["current"] if state and state["status"] == "active" else None
            keep = state["resource_id"] if state and current else None
            for resource_id in await self._held(uid):
                if resource_id != keep:  # gone, or rebound to another Resource
                    async with self.reports.window():
                        await self._drop(
                            uid, resource_id, keep_content=False, narrowed_at=narrowed_at
                        )
            if keep is None or current is None:
                return
            if await self._served(uid, keep, current["canonical_revision_id"]):
                return
            if dropped == (keep, current["canonical_revision_id"]):
                break  # the state did not move: the next run tries again after retry_s
            if await self._write(uid, keep, current):
                return
            dropped = (keep, current["canonical_revision_id"])
        raise Unsettled

    async def _held(self, uid: str) -> set[str]:
        async with self.pool.connection() as conn:
            rows = await conn.execute(
                "SELECT resource_id FROM entry WHERE build_id = %s AND document_uid = %s"
                " AND markdown IS NOT NULL UNION SELECT resource_id FROM registration"
                " WHERE build_id = %s AND document_uid = %s",
                (self.build_id, uid, self.build_id, uid),
            )
            return {resource_id for (resource_id,) in await rows.fetchall()}

    async def _served(self, uid: str, resource_id: str, crv: str) -> bool:
        async with self.pool.connection() as conn:
            row = await (
                await conn.execute(
                    "SELECT 1 FROM entry e WHERE build_id = %s AND document_uid = %s"
                    " AND resource_id = %s AND canonical_revision_id = %s"
                    " AND markdown IS NOT NULL AND NOT EXISTS (SELECT 1 FROM registration r"
                    " WHERE (r.build_id, r.document_uid, r.resource_id)"
                    " = (e.build_id, e.document_uid, e.resource_id))",
                    (self.build_id, uid, resource_id, crv),
                )
            ).fetchone()
        return row is not None

    async def _write(self, uid: str, resource_id: str, current: dict[str, str]) -> bool:
        """Registers, reads the content, writes and confirms; False when the write was dropped
        (`SUPERSEDED`, or the content read refused), after reporting what the store holds."""
        srv, crv = current["source_revision_id"], current["canonical_revision_id"]
        attempt = await self._attempt(uid, srv, crv)
        await attempt.report("running")
        started = time.monotonic()
        try:
            async with self.reports.window():
                fact = await self._register_locally(uid, resource_id, srv, crv)
                try:
                    await self.sdk.register(self.build_id, [fact])
                except PlatformError as error:
                    if error.reason != "SUPERSEDED":
                        raise
                    # An earlier send of it may have been recorded: report the store (§7.4).
                    await self._drop(uid, resource_id, keep_content=True)
                    await attempt.report("failed", "SUPERSEDED")
                    return False
            try:
                content = await self.sdk.content(uid, crv)
            except PlatformError as error:
                if not 400 <= error.status < 500:
                    raise
                # Deleted, no longer kept or unknown: the state read decides on the next pass.
                async with self.reports.window():
                    await self._drop(uid, resource_id, keep_content=True)
                await attempt.report("failed", "CONTENT_REFUSED")
                return False
            blocks = json.loads(content)["blocks"]
            markdown = "\n\n".join(block["markdown"] for block in blocks)  # content spec §3.2
            async with self.reports.window():
                await self._store(uid, resource_id, srv, crv, markdown)
                await self._flush(uid)
        except Exception as error:
            with suppress(PlatformError):
                await attempt.report("failed", _reason(error), retryable=True)
            raise
        write_seconds.observe(time.monotonic() - started)
        await attempt.report("succeeded")
        return True

    async def _register_locally(self, uid: str, resource_id: str, srv: str, crv: str) -> dict:
        async with self.pool.connection() as conn:
            [(version, issued_at)] = await (
                await conn.execute(
                    "INSERT INTO registration (build_id, document_uid, resource_id,"
                    " source_revision_id, canonical_revision_id, fact_version, issued_at)"
                    " VALUES (%s, %s, %s, %s, %s, nextval('fact_version'), now())"
                    " ON CONFLICT (build_id, document_uid, resource_id) DO UPDATE SET"
                    " source_revision_id = excluded.source_revision_id,"
                    " canonical_revision_id = excluded.canonical_revision_id,"
                    " fact_version = excluded.fact_version, issued_at = excluded.issued_at"
                    " RETURNING fact_version, issued_at",
                    (self.build_id, uid, resource_id, srv, crv),
                )
            ).fetchall()
        return _fact(uid, resource_id, srv, crv, version, issued_at)

    async def _store(self, uid: str, resource_id: str, srv: str, crv: str, markdown: str) -> None:
        """The write and the end of its registration, in one transaction; `included` follows."""
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "DELETE FROM registration WHERE build_id = %s AND document_uid = %s"
                " AND resource_id = %s",
                (self.build_id, uid, resource_id),
            )
            await conn.execute(
                "INSERT INTO entry (build_id, document_uid, resource_id, source_revision_id,"
                " canonical_revision_id, markdown, fact_version, issued_at) VALUES"
                " (%s, %s, %s, %s, %s, %s, nextval('fact_version'), now())"
                " ON CONFLICT (build_id, document_uid, resource_id) DO UPDATE SET"
                " source_revision_id = excluded.source_revision_id,"
                " canonical_revision_id = excluded.canonical_revision_id,"
                " markdown = excluded.markdown, fact_version = excluded.fact_version,"
                " issued_at = excluded.issued_at, reported = false",
                (self.build_id, uid, resource_id, srv, crv, markdown),
            )

    async def _drop(
        self, uid: str, resource_id: str, *, keep_content: bool, narrowed_at: datetime | None = None
    ) -> None:
        """Ends the key's registration and reports, under a new fact_version, what the store
        holds: its stored revisions `included` when `keep_content` and it has them, else
        `removed`. The caller holds a report window."""
        key = (self.build_id, uid, resource_id)
        async with self.pool.connection() as conn, conn.transaction():
            registered = await (
                await conn.execute(
                    "DELETE FROM registration WHERE build_id = %s AND document_uid = %s"
                    " AND resource_id = %s RETURNING source_revision_id, canonical_revision_id",
                    key,
                )
            ).fetchone()
            updated = await conn.execute(
                "UPDATE entry SET fact_version = nextval('fact_version'), issued_at = now(),"
                " reported = false, markdown = CASE WHEN %s THEN markdown END"
                " WHERE build_id = %s AND document_uid = %s AND resource_id = %s",
                (keep_content, *key),
            )
            if not updated.rowcount and registered:
                await conn.execute(
                    "INSERT INTO entry (build_id, document_uid, resource_id, source_revision_id,"
                    " canonical_revision_id, markdown, fact_version, issued_at)"
                    " VALUES (%s, %s, %s, %s, %s, NULL, nextval('fact_version'), now())",
                    (*key, *registered),
                )
        await self._flush(uid, narrowed_at)

    async def _flush(self, uid: str, narrowed_at: datetime | None = None) -> None:
        """Sends the facts of `uid` the platform has not taken yet, as first issued; a removal
        taken counts toward the time since `narrowed_at`, the narrowing event's."""
        async with self.pool.connection() as conn:
            rows = await (
                await conn.execute(
                    "SELECT resource_id, source_revision_id, canonical_revision_id,"
                    " markdown IS NOT NULL, fact_version, issued_at FROM entry"
                    " WHERE build_id = %s AND document_uid = %s AND NOT reported",
                    (self.build_id, uid),
                )
            ).fetchall()
        if not rows:
            return
        facts = [
            _fact(uid, res, srv, crv, version, issued_at)
            | {"state": "included" if stored else "removed"}
            for res, srv, crv, stored, version, issued_at in rows
        ]
        answer = await self.sdk.report_facts(self.build_id, facts)
        for key in answer["fenced"]:  # never sent again (DR §5.3); the repair is #281's
            log.warning("fact fenced: document_uid=%s", key["document_uid"])
        async with self.pool.connection() as conn:
            for fact in facts:
                await conn.execute(
                    "UPDATE entry SET reported = true WHERE build_id = %s AND document_uid = %s"
                    " AND resource_id = %s AND fact_version = %s",
                    (self.build_id, uid, fact["resource_id"], fact["fact_version"]),
                )
        for fact in facts:
            log.info(
                "fact reported: build_id=%s document_uid=%s resource_id=%s state=%s"
                " fact_version=%s",
                self.build_id,
                uid,
                fact["resource_id"],
                fact["state"],
                fact["fact_version"],
            )
            if narrowed_at and fact["state"] == "removed":
                removal_seconds.observe((datetime.now(UTC) - narrowed_at).total_seconds())
        if answer["repair_requested"]:
            log.warning("repair requested: reason=%s", answer["repair_requested"]["reason"])

    async def _attempt(self, uid: str, srv: str, crv: str) -> "_Attempt":
        async with self.pool.connection() as conn:
            [(attempt_no,)] = await (
                await conn.execute(
                    "INSERT INTO attempt (build_id, document_uid, canonical_revision_id,"
                    " attempt_no) VALUES (%s, %s, %s, 1) ON CONFLICT (build_id, document_uid,"
                    " canonical_revision_id) DO UPDATE SET attempt_no = attempt.attempt_no + 1"
                    " RETURNING attempt_no",
                    (self.build_id, uid, crv),
                )
            ).fetchall()
        return _Attempt(self, uid, srv, crv, attempt_no)

    # Heartbeat

    async def heartbeat(self) -> dict[str, Any]:
        """Sends the count and digest of the store entries and unfinished registrations, a
        registration winning for a key with both (spec §7.4), with no report in flight."""
        async with self.reports.quiet():
            async with self.pool.connection() as conn:
                unsent = await conn.execute(
                    "SELECT DISTINCT document_uid FROM entry WHERE build_id = %s AND NOT reported",
                    (self.build_id,),
                )
                uids = [uid for (uid,) in await unsent.fetchall()]
            for uid in uids:  # a fact a failed report left behind is sent before it is counted
                await self._flush(uid)
            async with self.pool.connection() as conn:
                rows = await (
                    await conn.execute(
                        "SELECT document_uid, resource_id, canonical_revision_id FROM registration"
                        " WHERE build_id = %s UNION ALL SELECT document_uid, resource_id,"
                        " canonical_revision_id FROM entry e WHERE build_id = %s"
                        " AND markdown IS NOT NULL AND NOT EXISTS (SELECT 1 FROM registration r"
                        " WHERE (r.build_id, r.document_uid, r.resource_id)"
                        " = (e.build_id, e.document_uid, e.resource_id))",
                        (self.build_id, self.build_id),
                    )
                ).fetchall()
            # shortcut: digests the whole store per heartbeat; keep a running XOR past ~1e5 keys.
            digest = 0
            for row in rows:
                digest ^= int.from_bytes(hashlib.sha256("\x1f".join(row).encode()).digest())
            answer = await self.sdk.heartbeat(self.build_id, len(rows), f"{digest:064x}")
        if answer["repair_requested"]:
            log.warning("repair requested: reason=%s", answer["repair_requested"]["reason"])
        return answer

    # The process

    async def run(
        self, stop: asyncio.Event, workers: int, narrowing_workers: int, heartbeat_s: float
    ):
        """The reader, `narrowing_workers` that take only narrowing work, `workers` that take
        any, and the heartbeat, until `stop` is set. Raises Expired when the cursor expired."""
        await self.start()

        async def reading() -> None:
            while not stop.is_set():
                try:
                    if await self.read_once():
                        continue
                except PlatformError as error:
                    failures.labels("read_feed", error.reason).inc()
                    log.warning("feed read failed: reason=%s", error.reason)
                await _pause(stop, self.poll_s)

        async def working(narrowing_only: bool) -> None:
            while not stop.is_set():
                if not await self.work_once(narrowing_only):
                    await _pause(stop, self.poll_s)

        async def beating() -> None:
            while not stop.is_set():
                try:
                    await self.heartbeat()
                except PlatformError as error:
                    failures.labels("heartbeat", error.reason).inc()
                    log.warning("heartbeat failed: reason=%s", error.reason)
                await _pause(stop, heartbeat_s)

        async with asyncio.TaskGroup() as group:
            group.create_task(reading())
            group.create_task(beating())
            for _ in range(narrowing_workers):
                group.create_task(working(True))
            for _ in range(workers):
                group.create_task(working(False))


class _Attempt:
    """The status reports of one attempt at a unit (Build, Document, Canonical Revision)."""

    def __init__(self, projection: Projection, uid: str, srv: str, crv: str, no: int) -> None:
        self.projection, self.seq = projection, 0
        self.body = {
            "document_uid": uid,
            "source_revision_id": srv,
            "canonical_revision_id": crv,
            "attempt_no": no,
            "attempt_id": uuid.uuid4().hex,
            "stages_version": "1",
            "stage": STAGES[-1],
            "progress": None,
            "message": "",
            "method_version": METHOD_VERSION,
            "manifest_ref": None,
        }

    async def report(self, state: str, reason: str | None = None, retryable: bool = False):
        self.seq += 1
        error = reason and {
            "domain": "reference-projection",
            "reason": reason,
            "message": "The write was not completed.",  # fixed: no content in a report
            "retryable": retryable,
        }
        body = self.body | {
            "seq": self.seq,
            "state": state,
            "observed_at": datetime.now(UTC).isoformat(),
            "error": error or None,
        }
        position = await self.projection.sdk.report_attempt(self.projection.build_id, body)
        if position:
            log.warning("attempt report out of order: attempt_no=%s", self.body["attempt_no"])


def _fact(uid: str, res: str, srv: str, crv: str, version: int, issued_at: datetime) -> dict:
    return {
        "document_uid": uid,
        "resource_id": res,
        "source_revision_id": srv,
        "canonical_revision_id": crv,
        "fact_version": version,
        "issued_at": issued_at.isoformat(),
    }


def _reason(error: BaseException) -> str:
    return error.reason if isinstance(error, PlatformError) else type(error).__name__


async def _pause(stop: asyncio.Event, seconds: float) -> None:
    with suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), seconds)
