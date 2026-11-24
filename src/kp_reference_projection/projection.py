"""The reader, the work table, the Builds and `reconcile_doc` of the reference projection (#127,
#280).

- **One reader, one cursor, for every Build** (DR A7). The reader reads the Change Feed and turns
  each event into a row of the work table for each Build not retired, one per (Build,
  `document_uid`), in the transaction that saves its cursor; it reports the cursor only after
  that commit, so an event is durable before its position is (DR A3). It reports the cursor on
  every read, with or without events, which the platform's lag gauge reads. A
  `source_profile_changed` event becomes a source-level reconciliation per Build.
- **Workers** take rows by priority, `narrowing` first, and run `reconcile_doc` for the (Build,
  uid). A row is one (Build, uid), so runs of a uid in a Build are serialised and its backlog
  runs once; an event that comes during a run bumps `requested`, and the run then leaves the row
  for one more run (DR A9). Coalescing keeps a row's highest priority, so a deletion is never
  demoted behind an update. A merged run never spans a deletion (DR A3): a run reads the state
  after the newest event it merged, so it sees the deletion, and a resubmitted Document gets a
  new `document_uid`.
- **A source-level reconciliation** (`ReconcileSource`, DR A9) reads the Source's Knowledge
  Profile again on each pass, then queues the Source's Documents at `background` priority a page
  at a time, each page once the one before it has run. Requests for the same (Build, Source)
  merge; one that comes during a pass makes one more pass. A pass that ends while the profile
  lists this projection is that Build's backfill of the Source (spec §7.4), reported once the
  Build serves.
- **`reconcile_doc`** converges on the Document's current state, whatever order its events came
  in: it removes what the state or the Source's profile no longer allows (DR B1, D1), registers
  before it writes, confirms after, and reports what its store holds when it drops a write (DR
  §5.2, spec §7.4).
- **The Builds** (DR §4, D2). `build_id` is the Build that should serve (KP_PROJECTION_BUILD_ID,
  ruling A2 on #280). One not seen before is created at start as a candidate: it follows the
  feed from the reader's position and reconciles every Source from there. Once it has read every
  Source and has nothing left to run, and a read finds no more events, it switches, naming the
  Build it replaces; the platform runs the gates again and a refused switch is tried after the
  next read. The replaced Build is `retained` and keeps following the feed; naming it again is a
  rollback. A retained Build past `retention_s` and a candidate no longer named have their data
  cleared and are reported `retired`. Not in production, so a switch waits for no approval
  (ruling A3): the refs given are recorded and sent.
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
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from kp_sdk import PlatformError
from kp_sdk.projection import ProjectionClient

log = logging.getLogger(__name__)

PRIORITY = {"narrowing": 0, "normal": 1, "background": 2}
STAGES = ["write"]  # what KP_PIPELINES registers for this projection (spec §7.3)
METHOD_VERSION = "reference-projection@1"
LIVE = ["building", "serving", "retained"]  # the Builds that follow the feed and take work
RETENTION_S = 7 * 24 * 3600  # DR D2's default

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
source_passes = Gauge(
    "kp_projection_source_passes", "source-level reconciliations not finished, every Build"
)

# The claim locks the Build's row in share mode, so `_retire` sees every run its state allowed.
CLAIM = (
    "UPDATE work SET claimed = true WHERE (build_id, document_uid) = ("
    " SELECT w.build_id, w.document_uid FROM work w JOIN build b USING (build_id)"
    " WHERE b.state = ANY(%s) AND NOT w.claimed AND w.not_before <= now() AND w.priority <= %s"
    " ORDER BY w.priority, w.queued_at LIMIT 1 FOR UPDATE OF w SKIP LOCKED FOR SHARE OF b)"
    " RETURNING build_id, document_uid, source_id, requested, at_least, narrowed_at"
)
CLAIM_SOURCE = (
    "UPDATE source_work SET claimed = true WHERE (build_id, source_id) = ("
    " SELECT s.build_id, s.source_id FROM source_work s JOIN build b USING (build_id)"
    " WHERE b.state = ANY(%s) AND NOT s.claimed AND s.not_before <= now()"
    # A page is queued once the one before it has run, so the work table stays small.
    " AND NOT EXISTS (SELECT 1 FROM work w WHERE (w.build_id, w.source_id)"
    " = (s.build_id, s.source_id))"
    " ORDER BY s.build_id, s.source_id LIMIT 1 FOR UPDATE OF s SKIP LOCKED FOR SHARE OF b)"
    " RETURNING build_id, source_id, requested, pass_requested, profile_seq, listed, after,"
    " enumerated"
)
QUEUE = (
    "INSERT INTO work (build_id, document_uid, source_id, priority, at_least, narrowed_at)"
    " VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (build_id, document_uid) DO UPDATE SET"
    " priority = least(work.priority, excluded.priority),"
    " at_least = coalesce(excluded.at_least, work.at_least), requested = work.requested + 1,"
    " not_before = now(), narrowed_at = coalesce(work.narrowed_at, excluded.narrowed_at)"
)


class Unsettled(Exception):
    """The state kept moving while the run wrote: the run is retried."""


class Expired(Exception):
    """The cursor is past the feed's retention: the projection needs a bootstrap (#281)."""


class Retired(Exception):
    """The Build asked to serve was retired: a retired Build never serves again (spec §7.4)."""


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
    """Projection `sdk.projection` over its store in `pool`'s database, which holds SCHEMA, with
    `build_id` the Build that should serve. One process runs it: `start` takes back every claim
    (the CLI holds a lock)."""

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
        retention_s: float = RETENTION_S,
        approval_ref: str | None = None,
        evidence_ref: str | None = None,
    ) -> None:
        self.sdk, self.pool, self.build_id = sdk, pool, build_id
        self.poll_s, self.retry_s, self.run_timeout_s, self.page = (
            poll_s,
            retry_s,
            run_timeout_s,
            page,
        )
        self.retention_s = retention_s
        self.approval_ref, self.evidence_ref = approval_ref, evidence_ref
        self.reports = _Reports()

    # The Builds

    async def start(self) -> None:
        """Takes back the claims of a process that ended, fixes the reader's starting position
        at the feed's head when it has none, gives up every candidate other than `build_id`,
        and creates `build_id` when it is new. Raises Retired for a retired `build_id`."""
        async with self.pool.connection() as conn:
            await conn.execute("UPDATE work SET claimed = false WHERE claimed")
            await conn.execute("UPDATE source_work SET claimed = false WHERE claimed")
            if not await (await conn.execute("SELECT 1 FROM reader")).fetchone():
                head = (await self.sdk.feed(None))["next_cursor"]
                await conn.execute("INSERT INTO reader (cursor) VALUES (%s)", (head,))
            rows = await (await conn.execute("SELECT build_id, state FROM build")).fetchall()
            builds = dict(rows)
            # A recorded switch, sent or not, means the Build was reported `building` before.
            switched = await (
                await conn.execute("SELECT 1 FROM switch WHERE build_id = %s", (self.build_id,))
            ).fetchone()
        state = builds.get(self.build_id)
        if state in ("retiring", "retired"):
            raise Retired(self.build_id)
        for other, other_state in builds.items():
            if other != self.build_id and other_state in ("building", "retiring"):
                await self._give_up(other)  # a candidate given up, or a retirement cut short
        if state is None:
            await self._create()
        if state in (None, "building") and not switched:
            await self.sdk.report_build(self.build_id, {"state": "building"})

    async def _give_up(self, build_id: str) -> None:
        """Retires a Build no longer named, unless the platform took its switch before a crash
        kept the local record from it: that Build serves, and stays."""
        async with self.pool.connection() as conn:
            pending = await (
                await conn.execute(
                    "SELECT switch_seq FROM switch WHERE build_id = %s AND taken_at IS NULL",
                    (build_id,),
                )
            ).fetchone()
        if pending:
            try:
                await self.sdk.report_build(build_id, {"state": "building"})
            except PlatformError as error:
                if error.reason != "BUILD_STATE":
                    raise
                if error.metadata.get("state") == "serving":
                    await self._took(build_id, pending[0])
                    return
        await self._retire(build_id)

    async def _create(self) -> None:
        """A new Build follows the feed from the reader's saved position and reconciles every
        Source from there: the start is fixed before the Sources are listed (DR D2, A4)."""
        sources = await self.sdk.sources()
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO build (build_id, start_position) SELECT %s, cursor FROM reader",
                (self.build_id,),
            )
            for source_id in sources:
                await conn.execute(
                    "INSERT INTO source_work (build_id, source_id) VALUES (%s, %s)",
                    (self.build_id, source_id),
                )
        log.info("build created: build_id=%s count=%s", self.build_id, len(sources))

    async def _switch(self, feed_position: str) -> None:
        """Switches `build_id` to `serving` once its own checks pass: every Source reconciled, no
        Document waiting (the read having found no more events) and no fewer entries than the
        serving Build. The platform runs every gate again from its mirror (spec §7.4), which alone
        knows the deleted Documents; a refusal is tried again after the next read."""
        async with self.pool.connection() as conn, conn.transaction():
            [(state, waiting)] = await (
                await conn.execute(
                    "SELECT state, EXISTS (SELECT 1 FROM work w WHERE w.build_id = b.build_id)"
                    " OR EXISTS (SELECT 1 FROM source_work s WHERE s.build_id = b.build_id)"
                    " FROM build b WHERE build_id = %s",
                    (self.build_id,),
                )
            ).fetchall()
            if state not in ("building", "retained") or waiting:
                return
            [(own, replaced, replaces)] = await (
                await conn.execute(
                    "SELECT count(*) FILTER (WHERE e.build_id = %s),"
                    " count(*) FILTER (WHERE b.state = 'serving'),"
                    " (SELECT build_id FROM build WHERE state = 'serving')"
                    " FROM entry e JOIN build b USING (build_id) WHERE e.markdown IS NOT NULL",
                    (self.build_id,),
                )
            ).fetchall()
            if own < replaced:  # D2's coverage gate, as this store counts it
                return
            # Recorded before it is sent, so a resend after a crash carries the same number.
            await conn.execute(
                "INSERT INTO switch (switch_seq, build_id, evidence_position, approval_ref,"
                " evidence_ref) SELECT nextval('switch_seq'), %s, %s, %s, %s WHERE NOT EXISTS"
                " (SELECT 1 FROM switch WHERE build_id = %s AND taken_at IS NULL)",
                (self.build_id, feed_position, self.approval_ref, self.evidence_ref, self.build_id),
            )
            [(switch_seq, approval_ref, evidence_ref)] = await (
                await conn.execute(
                    "UPDATE switch SET feed_position = %s, replaces = %s"
                    " WHERE build_id = %s AND taken_at IS NULL"
                    " RETURNING switch_seq, approval_ref, evidence_ref",
                    (feed_position, replaces, self.build_id),
                )
            ).fetchall()
        report = {
            "state": "serving",
            "switch_seq": switch_seq,
            "replaces": replaces,
            "feed_position": feed_position,
        } | {k: v for k, v in (("approval_ref", approval_ref), ("evidence_ref", evidence_ref)) if v}
        try:
            answer = await self.sdk.report_build(self.build_id, report)
        except PlatformError as error:
            failures.labels("switch", error.reason).inc()
            log.warning(
                "switch refused: build_id=%s switch_seq=%s reason=%s gate=%s",
                self.build_id,
                switch_seq,
                error.reason,
                error.metadata.get("gate"),
            )
            return
        if answer["state"] != "serving":  # a number the platform had already passed
            async with self.pool.connection() as conn:
                await conn.execute("DELETE FROM switch WHERE switch_seq = %s", (switch_seq,))
            log.warning("switch late: build_id=%s switch_seq=%s", self.build_id, switch_seq)
            return
        await self._took(self.build_id, switch_seq)

    async def _took(self, build_id: str, switch_seq: int) -> None:
        """Records the switch the platform took: the Build serves, the one it replaced is
        `retained` from now (DR D2)."""
        async with self.pool.connection() as conn, conn.transaction():
            # Two statements: one Build serves at any moment, and a query sees both or neither.
            await conn.execute(
                "UPDATE build SET state = 'retained', retained_at = now() WHERE state = 'serving'"
            )
            await conn.execute(
                "UPDATE build SET state = 'serving', retained_at = NULL WHERE build_id = %s",
                (build_id,),
            )
            await conn.execute(
                "UPDATE switch SET taken_at = now() WHERE switch_seq = %s", (switch_seq,)
            )
        log.info("build serving: build_id=%s switch_seq=%s", build_id, switch_seq)

    async def retire_expired(self) -> None:
        """Retires each retained Build past its retention, except `build_id`, which a rollback
        is switching to, and finishes a retirement waiting for its runs to end (DR D2)."""
        async with self.pool.connection() as conn:
            rows = await conn.execute(
                "SELECT build_id FROM build WHERE build_id <> %s AND (state = 'retiring' OR"
                " (state = 'retained' AND retained_at < now() - make_interval(secs => %s)))"
                " ORDER BY build_id",
                (self.build_id, self.retention_s),
            )
            expired = [build_id for (build_id,) in await rows.fetchall()]
        for build_id in expired:
            await self._retire(build_id)

    async def _retire(self, build_id: str) -> None:
        """Stops the Build taking work, and once no run of it is in progress clears its data and
        reports it `retired`, which is final (DR §4): nothing is sent for it after."""
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "UPDATE build SET state = 'retiring' WHERE build_id = %s", (build_id,)
            )
            busy = await (
                await conn.execute(
                    "SELECT 1 FROM work WHERE build_id = %s AND claimed UNION ALL"
                    " SELECT 1 FROM source_work WHERE build_id = %s AND claimed",
                    (build_id, build_id),
                )
            ).fetchone()
            if busy:
                return  # committed as `retiring`: the next pass finishes it
            for table in ("work", "source_work", "backfilled", "registration", "entry", "attempt"):
                await conn.execute(f"DELETE FROM {table} WHERE build_id = %s", (build_id,))
        await self.sdk.report_build(build_id, {"state": "retired"})
        async with self.pool.connection() as conn:
            await conn.execute(
                "UPDATE build SET state = 'retired' WHERE build_id = %s", (build_id,)
            )
        log.info("build retired: build_id=%s", build_id)

    async def report_backfills(self) -> None:
        """Reports each backfill the serving Build completed and has not reported (spec §7.4):
        recorded first, so a failed report is sent again on the next call."""
        async with self.pool.connection() as conn:
            rows = await (
                await conn.execute(
                    "SELECT build_id, source_id, profile_seq FROM backfilled JOIN build"
                    " USING (build_id) WHERE state = 'serving' AND NOT reported"
                )
            ).fetchall()
        for build_id, source_id, profile_seq in rows:
            try:
                await self.sdk.report_backfill(source_id, profile_seq)
            except PlatformError as error:
                failures.labels("backfill", error.reason).inc()
                log.warning("backfill refused: source_id=%s reason=%s", source_id, error.reason)
                return
            async with self.pool.connection() as conn:
                await conn.execute(
                    "UPDATE backfilled SET reported = true WHERE build_id = %s AND source_id = %s"
                    " AND profile_seq = %s",
                    (build_id, source_id, profile_seq),
                )
            log.info(
                "backfill reported: build_id=%s source_id=%s profile_seq=%s",
                build_id,
                source_id,
                profile_seq,
            )

    # The reader

    async def read_once(self) -> int:
        """Reads one page after the saved cursor, queues its events and reports the cursor;
        once a read finds no more, tries the switch of `build_id` and reports the backfills
        not reported yet. Returns the events read."""
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
            await self.report_backfills()
        return len(page["events"])

    async def enqueue(self, events: list[dict[str, Any]], next_cursor: str) -> None:
        """Queues each event for every Build not retired and saves `next_cursor`, in one
        transaction. `source_profile_changed` queues a source-level reconciliation; another
        event without a `document_uid` (a kind this reader does not know) is logged and
        skipped; one with a `document_uid` is reconciled whatever its kind (DR A2, ruling
        2026-11-22)."""
        async with self.pool.connection() as conn, conn.transaction():
            live = await (
                # Shared: a retirement waits for this transaction, or this one sees it.
                await conn.execute(
                    "SELECT build_id FROM build WHERE state = ANY(%s) FOR SHARE", (LIVE,)
                )
            ).fetchall()
            for event in events:
                uid = event.get("document_uid")
                if uid is None and event["kind"] != "source_profile_changed":
                    log.info("event skipped: kind=%s position=%s", event["kind"], event["position"])
                    continue
                for (build_id,) in live:
                    if uid is None:
                        await _queue_source(conn, build_id, event["source_id"])
                        continue
                    narrowing = event["priority"] == "narrowing"
                    await conn.execute(
                        QUEUE,
                        (
                            build_id,
                            uid,
                            event["source_id"],
                            PRIORITY.get(event["priority"], PRIORITY["normal"]),
                            event["position"],
                            event["occurred_at"] if narrowing else None,
                        ),
                    )
            await conn.execute("UPDATE reader SET cursor = %s", (next_cursor,))
            counts = await conn.execute("SELECT priority, count(*) FROM work GROUP BY priority")
            waiting = dict(await counts.fetchall())
            [(passes,)] = await (await conn.execute("SELECT count(*) FROM source_work")).fetchall()
        for name, value in PRIORITY.items():
            backlog.labels(name).set(waiting.get(value, 0))
        source_passes.set(passes)

    # Workers

    async def work_once(self, narrowing_only: bool = False) -> bool:
        """Runs `reconcile_doc` for the first row by priority, or only a `narrowing` one; with
        no row due and not `narrowing_only`, one step of a source-level reconciliation. False
        when nothing is due. A failed run is retried after `retry_s`."""
        limit = PRIORITY["narrowing"] if narrowing_only else PRIORITY["background"]
        async with self.pool.connection() as conn:
            claimed = await (await conn.execute(CLAIM, (LIVE, limit))).fetchone()
        if not claimed:
            return False if narrowing_only else await self._source_step()
        build_id, uid, source_id, requested, at_least, narrowed_at = claimed
        try:
            async with asyncio.timeout(self.run_timeout_s):
                await self.reconcile_doc(build_id, uid, source_id, at_least, narrowed_at)
        except Exception as error:
            failures.labels("reconcile", _reason(error)).inc()
            log.warning(
                "run failed: build_id=%s document_uid=%s reason=%s", build_id, uid, _reason(error)
            )
            async with self.pool.connection() as conn:
                await conn.execute(
                    "UPDATE work SET claimed = false, not_before = now()"
                    " + make_interval(secs => %s) WHERE build_id = %s AND document_uid = %s",
                    (self.retry_s, build_id, uid),
                )
            return True
        async with self.pool.connection() as conn:
            done = await conn.execute(
                "DELETE FROM work WHERE build_id = %s AND document_uid = %s AND requested = %s",
                (build_id, uid, requested),
            )
            if not done.rowcount:  # an event came during the run: one more run
                await conn.execute(
                    "UPDATE work SET claimed = false WHERE build_id = %s AND document_uid = %s",
                    (build_id, uid),
                )
        return True

    async def _source_step(self) -> bool:
        async with self.pool.connection() as conn:
            claimed = await (await conn.execute(CLAIM_SOURCE, (LIVE,))).fetchone()
        if not claimed:
            return False
        build_id, source_id = claimed[:2]
        try:
            await self._pass(*claimed)
        except Exception as error:
            failures.labels("reconcile_source", _reason(error)).inc()
            log.warning(
                "source pass failed: build_id=%s source_id=%s reason=%s",
                build_id,
                source_id,
                _reason(error),
            )
            async with self.pool.connection() as conn:
                await conn.execute(
                    "UPDATE source_work SET claimed = false, not_before = now()"
                    " + make_interval(secs => %s) WHERE build_id = %s AND source_id = %s",
                    (self.retry_s, build_id, source_id),
                )
        return True

    async def _pass(
        self,
        build_id: str,
        source_id: str,
        requested: int,
        pass_requested: int | None,
        profile_seq: str | None,
        listed: bool | None,
        after: str | None,
        enumerated: bool,
    ) -> None:
        """One step of a pass over the Source: it begins by reading the profile, then queues a
        page of Documents, and once every Document queued has run it ends; a request that came
        during the pass begins another (DR A9)."""
        key = (build_id, source_id)
        if pass_requested is None:
            profile = await self.sdk.source_profile(source_id)
            pass_requested, after = requested, None
            listed = _lists(profile, self.sdk.projection)
            profile_seq = profile["profile_seq"] if profile else None
        if not enumerated:
            page = await self.sdk.source_documents(source_id, after, self.page)
            async with self.pool.connection() as conn, conn.transaction():
                for uid in page["document_uids"]:
                    await conn.execute(
                        QUEUE, (build_id, uid, source_id, PRIORITY["background"], None, None)
                    )
                await conn.execute(
                    "UPDATE source_work SET claimed = false, pass_requested = %s, profile_seq = %s,"
                    " listed = %s, after = %s, enumerated = %s"
                    " WHERE build_id = %s AND source_id = %s",
                    (
                        pass_requested,
                        profile_seq,
                        listed,
                        page["next_after"],
                        not page["next_after"],
                        *key,
                    ),
                )
            return
        async with self.pool.connection() as conn, conn.transaction():
            if listed:
                await conn.execute(
                    "INSERT INTO backfilled (build_id, source_id, profile_seq) VALUES (%s, %s, %s)"
                    " ON CONFLICT (build_id, source_id) DO UPDATE SET"
                    " profile_seq = excluded.profile_seq, reported = false",
                    (*key, profile_seq),
                )
            done = await conn.execute(
                "DELETE FROM source_work WHERE build_id = %s AND source_id = %s AND requested = %s",
                (*key, pass_requested),
            )
            if not done.rowcount:  # requested again during the pass: one more
                await conn.execute(
                    "UPDATE source_work SET claimed = false, pass_requested = NULL,"
                    " enumerated = false WHERE build_id = %s AND source_id = %s",
                    key,
                )
        log.info(
            "source reconciled: build_id=%s source_id=%s profile_seq=%s listed=%s",
            build_id,
            source_id,
            profile_seq,
            listed,
        )

    # reconcile_doc

    async def reconcile_doc(
        self,
        build_id: str,
        uid: str,
        source_id: str,
        at_least: str | None = None,
        narrowed_at: datetime | None = None,
    ) -> None:
        """Brings the Build's store entries of `uid`, a Document of `source_id`, to the
        Document's current state."""
        dropped = None
        for _ in range(3):
            async with self.reports.window():
                await self._flush(build_id, uid, narrowed_at)
            state = await self.sdk.document_state(uid, at_least)
            listed = _lists(await self.sdk.source_profile(source_id), self.sdk.projection)
            # Served only when active, current (DR §6) and in a profile that lists us (B1, D1).
            current = state["current"] if state and state["status"] == "active" else None
            keep = state["resource_id"] if state and current and listed else None
            for resource_id in await self._held(build_id, uid):
                if resource_id != keep:  # gone, or rebound to another Resource
                    async with self.reports.window():
                        await self._drop(
                            build_id, uid, resource_id, keep_content=False, narrowed_at=narrowed_at
                        )
            if keep is None or current is None:
                return
            if await self._served(build_id, uid, keep, current["canonical_revision_id"]):
                return
            if dropped == (keep, current["canonical_revision_id"]):
                break  # the state did not move: the next run tries again after retry_s
            if await self._write(build_id, uid, keep, current):
                return
            dropped = (keep, current["canonical_revision_id"])
        raise Unsettled

    async def _held(self, build_id: str, uid: str) -> set[str]:
        async with self.pool.connection() as conn:
            rows = await conn.execute(
                "SELECT resource_id FROM entry WHERE build_id = %s AND document_uid = %s"
                " AND markdown IS NOT NULL UNION SELECT resource_id FROM registration"
                " WHERE build_id = %s AND document_uid = %s",
                (build_id, uid, build_id, uid),
            )
            return {resource_id for (resource_id,) in await rows.fetchall()}

    async def _served(self, build_id: str, uid: str, resource_id: str, crv: str) -> bool:
        async with self.pool.connection() as conn:
            row = await (
                await conn.execute(
                    "SELECT 1 FROM entry e WHERE build_id = %s AND document_uid = %s"
                    " AND resource_id = %s AND canonical_revision_id = %s"
                    " AND markdown IS NOT NULL AND NOT EXISTS (SELECT 1 FROM registration r"
                    " WHERE (r.build_id, r.document_uid, r.resource_id)"
                    " = (e.build_id, e.document_uid, e.resource_id))",
                    (build_id, uid, resource_id, crv),
                )
            ).fetchone()
        return row is not None

    async def _write(
        self, build_id: str, uid: str, resource_id: str, current: dict[str, str]
    ) -> bool:
        """Registers, reads the content, writes and confirms; False when the write was dropped
        (`SUPERSEDED`, or the content read refused), after reporting what the store holds."""
        srv, crv = current["source_revision_id"], current["canonical_revision_id"]
        attempt = await self._attempt(build_id, uid, srv, crv)
        await attempt.report("running")
        started = time.monotonic()
        try:
            async with self.reports.window():
                fact = await self._register_locally(build_id, uid, resource_id, srv, crv)
                try:
                    await self.sdk.register(build_id, [fact])
                except PlatformError as error:
                    if error.reason != "SUPERSEDED":
                        raise
                    # An earlier send of it may have been recorded: report the store (§7.4).
                    await self._drop(build_id, uid, resource_id, keep_content=True)
                    await attempt.report("failed", "SUPERSEDED")
                    return False
            try:
                content = await self.sdk.content(uid, crv)
            except PlatformError as error:
                if not 400 <= error.status < 500:
                    raise
                # Deleted, no longer kept or unknown: the state read decides on the next pass.
                async with self.reports.window():
                    await self._drop(build_id, uid, resource_id, keep_content=True)
                await attempt.report("failed", "CONTENT_REFUSED")
                return False
            markdown, cited = _texts(json.loads(content))
            created_at = current.get("source_revision_created_at")  # in the state from #268
            async with self.reports.window():
                await self._store(build_id, uid, resource_id, srv, crv, markdown, cited, created_at)
                await self._flush(build_id, uid)
        except Exception as error:
            with suppress(PlatformError):
                await attempt.report("failed", _reason(error), retryable=True)
            raise
        write_seconds.observe(time.monotonic() - started)
        await attempt.report("succeeded")
        return True

    async def _register_locally(
        self, build_id: str, uid: str, resource_id: str, srv: str, crv: str
    ) -> dict:
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
                    (build_id, uid, resource_id, srv, crv),
                )
            ).fetchall()
        return _fact(uid, resource_id, srv, crv, version, issued_at)

    async def _store(
        self,
        build_id: str,
        uid: str,
        resource_id: str,
        srv: str,
        crv: str,
        markdown: str,
        cited: str,
        created_at: str | None,
    ) -> None:
        """The write and the end of its registration, in one transaction; `included` follows."""
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "DELETE FROM registration WHERE build_id = %s AND document_uid = %s"
                " AND resource_id = %s",
                (build_id, uid, resource_id),
            )
            await conn.execute(
                "INSERT INTO entry (build_id, document_uid, resource_id, source_revision_id,"
                " canonical_revision_id, markdown, cited, source_revision_created_at,"
                " fact_version, issued_at) VALUES"
                " (%s, %s, %s, %s, %s, %s, %s, %s, nextval('fact_version'), now())"
                " ON CONFLICT (build_id, document_uid, resource_id) DO UPDATE SET"
                " source_revision_id = excluded.source_revision_id,"
                " canonical_revision_id = excluded.canonical_revision_id,"
                " markdown = excluded.markdown, cited = excluded.cited,"
                " source_revision_created_at = excluded.source_revision_created_at,"
                " fact_version = excluded.fact_version, issued_at = excluded.issued_at,"
                " reported = false",
                (build_id, uid, resource_id, srv, crv, markdown, cited, created_at),
            )

    async def _drop(
        self,
        build_id: str,
        uid: str,
        resource_id: str,
        *,
        keep_content: bool,
        narrowed_at: datetime | None = None,
    ) -> None:
        """Ends the key's registration and reports, under a new fact_version, what the store
        holds: its stored revisions `included` when `keep_content` and it has them, else
        `removed`. The caller holds a report window."""
        key = (build_id, uid, resource_id)
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
                " reported = false, markdown = CASE WHEN %s THEN markdown END,"
                " cited = CASE WHEN %s THEN cited END"
                " WHERE build_id = %s AND document_uid = %s AND resource_id = %s",
                (keep_content, keep_content, *key),
            )
            if not updated.rowcount and registered:
                await conn.execute(
                    "INSERT INTO entry (build_id, document_uid, resource_id, source_revision_id,"
                    " canonical_revision_id, markdown, fact_version, issued_at)"
                    " VALUES (%s, %s, %s, %s, %s, NULL, nextval('fact_version'), now())",
                    (*key, *registered),
                )
        await self._flush(build_id, uid, narrowed_at)

    async def _flush(self, build_id: str, uid: str, narrowed_at: datetime | None = None) -> None:
        """Sends the facts of `uid` the platform has not taken yet, as first issued; a removal
        taken counts toward the time since `narrowed_at`, the narrowing event's."""
        async with self.pool.connection() as conn:
            rows = await (
                await conn.execute(
                    "SELECT resource_id, source_revision_id, canonical_revision_id,"
                    " markdown IS NOT NULL, fact_version, issued_at FROM entry"
                    " WHERE build_id = %s AND document_uid = %s AND NOT reported",
                    (build_id, uid),
                )
            ).fetchall()
        if not rows:
            return
        facts = [
            _fact(uid, res, srv, crv, version, issued_at)
            | {"state": "included" if stored else "removed"}
            for res, srv, crv, stored, version, issued_at in rows
        ]
        answer = await self.sdk.report_facts(build_id, facts)
        for key in answer["fenced"]:  # never sent again (DR §5.3); the repair is #281's
            log.warning("fact fenced: build_id=%s document_uid=%s", build_id, key["document_uid"])
        async with self.pool.connection() as conn:
            for fact in facts:
                await conn.execute(
                    "UPDATE entry SET reported = true WHERE build_id = %s AND document_uid = %s"
                    " AND resource_id = %s AND fact_version = %s",
                    (build_id, uid, fact["resource_id"], fact["fact_version"]),
                )
        for fact in facts:
            log.info(
                "fact reported: build_id=%s document_uid=%s resource_id=%s state=%s"
                " fact_version=%s",
                build_id,
                uid,
                fact["resource_id"],
                fact["state"],
                fact["fact_version"],
            )
            if narrowed_at and fact["state"] == "removed":
                removal_seconds.observe((datetime.now(UTC) - narrowed_at).total_seconds())
        if answer["repair_requested"]:
            log.warning(
                "repair requested: build_id=%s reason=%s",
                build_id,
                answer["repair_requested"]["reason"],
            )

    async def _attempt(self, build_id: str, uid: str, srv: str, crv: str) -> "_Attempt":
        async with self.pool.connection() as conn:
            [(attempt_no,)] = await (
                await conn.execute(
                    "INSERT INTO attempt (build_id, document_uid, canonical_revision_id,"
                    " attempt_no) VALUES (%s, %s, %s, 1) ON CONFLICT (build_id, document_uid,"
                    " canonical_revision_id) DO UPDATE SET attempt_no = attempt.attempt_no + 1"
                    " RETURNING attempt_no",
                    (build_id, uid, crv),
                )
            ).fetchall()
        return _Attempt(self.sdk, build_id, uid, srv, crv, attempt_no)

    # Heartbeat

    async def heartbeat(self) -> dict[str, dict[str, Any]]:
        """Sends, for each Build not retired (`building` and `retained` too, spec §7.4), the
        count and digest of its store entries and unfinished registrations, a registration
        winning for a key with both, with no report in flight. Returns the answers by Build."""
        answers = {}
        async with self.reports.quiet():
            async with self.pool.connection() as conn:
                rows = await conn.execute(
                    "SELECT build_id FROM build WHERE state <> 'retired' ORDER BY build_id"
                )
                builds = [build_id for (build_id,) in await rows.fetchall()]
            for build_id in builds:
                try:  # one Build's failure does not cost the others their liveness
                    answers[build_id] = await self._beat(build_id)
                except PlatformError as error:
                    failures.labels("heartbeat", error.reason).inc()
                    log.warning("heartbeat failed: build_id=%s reason=%s", build_id, error.reason)
        for build_id, answer in answers.items():
            if answer["repair_requested"]:
                log.warning(
                    "repair requested: build_id=%s reason=%s",
                    build_id,
                    answer["repair_requested"]["reason"],
                )
        return answers

    async def _beat(self, build_id: str) -> dict[str, Any]:
        async with self.pool.connection() as conn:
            unsent = await conn.execute(
                "SELECT DISTINCT document_uid FROM entry WHERE build_id = %s AND NOT reported",
                (build_id,),
            )
            uids = [uid for (uid,) in await unsent.fetchall()]
        for uid in uids:  # a fact a failed report left behind is sent before it is counted
            await self._flush(build_id, uid)
        async with self.pool.connection() as conn:
            rows = await (
                await conn.execute(
                    "SELECT document_uid, resource_id, canonical_revision_id FROM registration"
                    " WHERE build_id = %s UNION ALL SELECT document_uid, resource_id,"
                    " canonical_revision_id FROM entry e WHERE build_id = %s"
                    " AND markdown IS NOT NULL AND NOT EXISTS (SELECT 1 FROM registration r"
                    " WHERE (r.build_id, r.document_uid, r.resource_id)"
                    " = (e.build_id, e.document_uid, e.resource_id))",
                    (build_id, build_id),
                )
            ).fetchall()
        # shortcut: digests the whole store per heartbeat; keep a running XOR past ~1e5 keys.
        digest = 0
        for row in rows:
            digest ^= int.from_bytes(hashlib.sha256("\x1f".join(row).encode()).digest())
        return await self.sdk.heartbeat(build_id, len(rows), f"{digest:064x}")

    # The process

    async def run(
        self, stop: asyncio.Event, workers: int, narrowing_workers: int, heartbeat_s: float
    ):
        """The reader, `narrowing_workers` that take only narrowing work, `workers` that take
        any, and the heartbeat with the retirement of expired Builds, until `stop` is set.
        Raises Expired when the cursor expired, Retired when `build_id` was retired."""
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
                    await self.retire_expired()
                except PlatformError as error:
                    failures.labels("retire", error.reason).inc()
                    log.warning("retirement failed: reason=%s", error.reason)
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


async def _queue_source(conn: AsyncConnection, build_id: str, source_id: str) -> None:
    await conn.execute(
        "INSERT INTO source_work (build_id, source_id) VALUES (%s, %s)"
        " ON CONFLICT (build_id, source_id) DO UPDATE SET"
        " requested = source_work.requested + 1, not_before = now()",
        (build_id, source_id),
    )


class _Attempt:
    """The status reports of one attempt at a unit (Build, Document, Canonical Revision)."""

    def __init__(
        self, sdk: ProjectionClient, build_id: str, uid: str, srv: str, crv: str, no: int
    ) -> None:
        self.sdk, self.build_id, self.seq = sdk, build_id, 0
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
        position = await self.sdk.report_attempt(self.build_id, body)
        if position:
            log.warning(
                "attempt report out of order: build_id=%s attempt_no=%s",
                self.build_id,
                self.body["attempt_no"],
            )


def _fact(uid: str, res: str, srv: str, crv: str, version: int, issued_at: datetime) -> dict:
    return {
        "document_uid": uid,
        "resource_id": res,
        "source_revision_id": srv,
        "canonical_revision_id": crv,
        "fact_version": version,
        "issued_at": issued_at.isoformat(),
    }


WITHHELD = "[withheld: disputed]"


def _texts(content: dict[str, Any]) -> tuple[str, str]:
    """The body Markdown (content spec §3.2) and the same with each block a `disputed`
    enrichment targets withheld, for snippets (#279). A figure's OCR text is not in the body,
    so the d3 signal that its `unverified` lacks is never needed here."""
    disputed = {
        ref
        for item in content.get("enrichments", [])
        if item["status"] == "disputed"
        for ref in item["target_refs"]
    }
    blocks = content["blocks"]
    markdown = "\n\n".join(block["markdown"] for block in blocks)
    cited = "\n\n".join(
        WITHHELD if block["ref"] in disputed else block["markdown"] for block in blocks
    )
    return markdown, cited


def _lists(profile: dict[str, Any] | None, projection: str) -> bool:
    return bool(profile) and projection in profile["projections"]


def _reason(error: BaseException) -> str:
    return error.reason if isinstance(error, PlatformError) else type(error).__name__


async def _pause(stop: asyncio.Event, seconds: float) -> None:
    with suppress(TimeoutError):
        await asyncio.wait_for(stop.wait(), seconds)
