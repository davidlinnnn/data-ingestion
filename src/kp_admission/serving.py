"""Projection report intake (#252, admission spec §7.4, canonical consumption DR §4–§5): the
platform's mirror of the serving facts each projection reports per Build, its repair from the
projection's repair views (#260), the Builds' states, the projections' attempts and their
backfill reports. kp_admission.status reads it for readiness and attention; Source Deletion's
judgment (#98) reads `held`, `silent` and `writes_unrepaired`.

Metrics:

- `kp_serving_facts_total` (count) of the facts and registrations reported, by `projection` and
  `result`: recorded, older (a higher fact_version is held), fenced (§5.3), superseded (a
  registration that failed the B5 check).
- `kp_serving_repairs_requested_total` (count) by `projection` and `reason`
  (heartbeat_mismatch, pending_expired, fenced, view_expired, view_fenced, writes_lost): a Build
  newly asked for a repair view.
- `kp_serving_repair_views_total` (count) of the repair view pages taken, by `projection` and
  `result`: incomplete, installed (the page completed the view), resent (of a view installed),
  expired and fenced (the page discarded the view), discarded (of a view discarded before),
  superseded (of a view a later one replaced).
- `kp_serving_repair_seconds` (histogram) by `projection`: from a repair request to the install
  of the view that ended it (DR §9's repair latency).
- `kp_serving_late_landings_total` (count) by `projection`: an `included` fact recorded for a
  Document that Source Deletion already applies to.
- `kp_serving_builds_without_liveness` (gauge) by `projection`: its Builds not retired whose last
  report is older than the pipeline's update interval.
"""

import asyncio
import hashlib
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import psycopg
from prometheus_client import Counter, Gauge, Histogram
from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from pydantic import AwareDatetime, BaseModel, Field, StrictInt, model_validator

from kp_admission import feed
from kp_admission.errors import Refused
from kp_admission.reports import ErrorBlock, Pipeline, Progress

log = logging.getLogger(__name__)

facts_taken = Counter("kp_serving_facts", "serving facts reported", ["projection", "result"])
repairs = Counter(
    "kp_serving_repairs_requested", "repair views asked for", ["projection", "reason"]
)
late_landings = Counter(
    "kp_serving_late_landings", "included facts of deleted Documents", ["projection"]
)
views = Counter("kp_serving_repair_views", "repair view pages taken", ["projection", "result"])
repair_latency = Histogram(
    "kp_serving_repair_seconds",
    "from a repair request to the view that ended it",
    ["projection"],
    buckets=(10, 30, 60, 300, 900, 1800, 3600, 7200, 21600, 86400),
)
without_liveness = Gauge(
    "kp_serving_builds_without_liveness",
    "Builds not retired that stopped reporting",
    ["projection"],
)

TOMBSTONE = timedelta(days=30)  # how long a `removed` fact is held (DR §5.3)
# Provisional until #127 measures a projection's store writes: a slow write, with a liveness
# pause, stays below it, and a lost confirmation is repaired within the hour.
PENDING_MAX = timedelta(minutes=30)
# Provisional until #127 measures a view's transfer: well below TOMBSTONE (DR §5.3), long enough
# to ride out a platform outage overnight. A report retry gives up after it too (spec §7.4).
VIEW_LIFETIME = timedelta(hours=24)
CLOCK_SKEW = timedelta(minutes=1)  # how far ahead of the platform a view's captured_at may be
SWITCH_LAG_MAX_S = 300  # provisional: how far behind the feed a Build may be when it switches

BuildState = Literal["building", "serving", "retained", "retired"]


class Fact(BaseModel, extra="forbid"):
    """A registration: the fact is `pending` until its store write is confirmed (DR §5.2).
    `resource_id` is the full identifier the Document state read answers."""

    document_uid: str = Field(min_length=1, max_length=64)
    resource_id: str = Field(min_length=1, max_length=512)
    source_revision_id: str = Field(min_length=1, max_length=64)
    canonical_revision_id: str = Field(min_length=1, max_length=64)
    fact_version: StrictInt = Field(ge=1)
    issued_at: AwareDatetime  # when the projection first made this report: the fence reads it


class ServingFact(Fact):
    state: Literal["included", "removed"]


class Registrations(BaseModel, extra="forbid"):
    facts: list[Fact] = Field(min_length=1, max_length=1000)


class ServingFacts(BaseModel, extra="forbid"):
    facts: list[ServingFact] = Field(min_length=1, max_length=1000)


class Heartbeat(BaseModel, extra="forbid"):
    count: StrictInt = Field(ge=0)
    digest: str = Field(pattern="^[0-9a-f]{64}$")


class BuildReport(BaseModel, extra="forbid"):
    """A Build's state. `serving` carries the switch: its number, above every earlier one of the
    projection, the Build it replaces (null for the first), the feed position the new Build has
    read to, and the owner's approval and evidence references (DR D2)."""

    state: BuildState
    switch_seq: StrictInt | None = Field(default=None, ge=1)
    replaces: str | None = None
    feed_position: str | None = None
    approval_ref: str | None = None
    evidence_ref: str | None = None

    @model_validator(mode="after")
    def _switch(self) -> "BuildReport":
        if self.state == "serving" and (self.switch_seq is None or self.feed_position is None):
            raise ValueError("a serving report carries switch_seq and feed_position")
        return self


class Backfill(BaseModel, extra="forbid"):
    profile_seq: str = Field(pattern="^[0-9a-f]{32}$")  # a feed position, as set-profile prints


class AttemptReport(BaseModel, extra="forbid"):
    """A projection's status report (spec §7.4): the fields of canonical processing's without
    request_id, the attempt's unit, and attempt_no, which orders the attempts of one unit.
    error is present exactly when the state is failed or skipped."""

    document_uid: str = Field(min_length=1, max_length=64)
    source_revision_id: str = Field(min_length=1, max_length=64)
    canonical_revision_id: str = Field(min_length=1, max_length=64)
    attempt_no: StrictInt = Field(ge=1)
    attempt_id: str = Field(min_length=1)
    seq: StrictInt = Field(ge=1)
    stages_version: str
    stage: str
    state: Literal["pending", "running", "succeeded", "failed", "skipped"]
    progress: Progress | None
    message: str
    method_version: str
    manifest_ref: str | None
    observed_at: AwareDatetime
    error: ErrorBlock | None

    @model_validator(mode="after")
    def _error_on_failure(self) -> "AttemptReport":
        if (self.state in ("failed", "skipped")) != (self.error is not None):
            raise ValueError("error is required when state is failed or skipped, and only then")
        return self


class AttemptPosition(BaseModel):
    """The current attempt of a unit and the seq of its last report taken."""

    attempt_no: int
    seq: int


class ViewEntry(BaseModel, extra="forbid"):
    """A store entry (`included`) or an unfinished registration (`pending`) of a repair view, with
    the fact_version last reported for it, which the expiry fence reads (DR §5.4)."""

    document_uid: str = Field(min_length=1, max_length=64)
    resource_id: str = Field(min_length=1, max_length=512)
    state: Literal["included", "pending"]
    source_revision_id: str = Field(min_length=1, max_length=64)
    canonical_revision_id: str = Field(min_length=1, max_length=64)
    fact_version: StrictInt = Field(ge=1)


class ViewPage(BaseModel, extra="forbid"):
    """A page of a repair view. Every page of one view states the same capture time, watermark
    (the highest fact_version allocated in the Build at capture) and number of pages."""

    captured_at: AwareDatetime
    watermark: StrictInt = Field(ge=0)
    pages: StrictInt = Field(ge=1)
    entries: list[ViewEntry] = Field(max_length=1000)

    @model_validator(mode="after")
    def _below_watermark(self) -> "ViewPage":
        if any(e.fact_version > self.watermark for e in self.entries):
            raise ValueError("an entry's fact_version is above the watermark")
        return self


class Key(BaseModel):
    document_uid: str
    resource_id: str


class Repair(BaseModel):
    reason: Literal[
        "heartbeat_mismatch", "pending_expired", "fenced", "view_expired", "view_fenced",
        "writes_lost",
    ]  # fmt: skip
    requested_at: datetime


class Answer(BaseModel):
    """Every 2xx of a Build's reports says whether the platform asks for a repair view of it
    (DR §5.1), until a repair view is installed."""

    repair_requested: Repair | None


class FactsAnswer(Answer):
    fenced: list[Key]  # not recorded, and never to be sent again (DR §5.3)


class ViewAnswer(Answer):
    view: Literal["incomplete", "installed"]


class BuildAnswer(Answer):
    state: BuildState  # the Build's state now, which a report that came late did not change


@dataclass(frozen=True)
class Served:
    source_revision_id: str
    source_version: str | None  # as the Source Revision carries it now (#258)


@dataclass(frozen=True)
class Attempt:
    source_revision_id: str
    last_report: dict[str, Any]
    reported_at: datetime


_Held = tuple[str, int, datetime]  # state, fact_version, recorded_at


@dataclass(frozen=True)
class _Row:
    """A key's fact in the mirror, as a repair reads it."""

    state: str
    srv: str
    crv: str
    version: int
    recorded_at: datetime


async def report_build(
    conn: AsyncConnection, projection: str, build_id: str, report: BuildReport
) -> tuple[BuildAnswer, list[str]]:
    """Takes a Build's state report (DR §4, D2), in one transaction, and returns the Builds whose
    Documents' readiness it may have changed. A Build starts `building`. `serving` is a switch:
    the platform re-runs the gates and, in the same step, retains the Build it replaces; a switch
    numbered at or below the projection's last one came late and changes nothing. `retired` is
    final. A report of the state the Build is in is a repeat, and returns the Builds again so
    the caller finishes a refresh the first call did not. Refused: 409 GATE_FAILED naming the
    gate (replaces, caught_up, coverage, removed_documents), 409 BUILD_STATE for a state the
    Build cannot take from where it is, 400 for a feed_position that is not one or is ahead of
    the feed."""
    async with conn.transaction():
        cursor = await conn.execute(
            "INSERT INTO build (projection, build_id, state) VALUES (%s, %s, 'building')"
            " ON CONFLICT DO NOTHING RETURNING build_id",
            (projection, build_id),
        )
        if await cursor.fetchone() and await writes_unrepaired(conn):
            # It may be one the loss erased, whose owner reports it again (DR §5.6, K2).
            await _repair(conn, projection, build_id, None, "writes_lost")
        # Every Build of the projection, so two switches cannot both read the same serving one.
        cursor = await conn.execute(
            "SELECT build_id, state, switch_seq, repair_reason, repair_requested_at FROM build"
            " WHERE projection = %s ORDER BY build_id FOR UPDATE",
            (projection,),
        )
        builds = {row[0]: row for row in await cursor.fetchall()}
        _, state, _, reason, requested_at = builds[build_id]
        changed: list[str] = []
        if report.state == state:
            # A resend finishes the refresh that a crash after the first one cut short.
            finishing = state in ("serving", "retired")
            changed = [b for b in (build_id, report.replaces) if b] if finishing else []
        elif state == "retired" or report.state in ("building", "retained"):
            # The platform retains a Build when another replaces it; its owner only repeats it.
            raise Refused(
                409,
                "FAILED_PRECONDITION",
                "BUILD_STATE",
                f"The Build is {state}.",
                metadata={"state": state},
            )
        elif report.state == "retired":
            changed = [build_id] if state == "serving" else []
            state = "retired"
            await conn.execute(
                "UPDATE build SET state = 'retired' WHERE projection = %s AND build_id = %s",
                (projection, build_id),
            )
        elif report.switch_seq > max(row[2] for row in builds.values()):  # type: ignore[operator]
            replaced = next((b for b, row in builds.items() if row[1] == "serving"), None)
            gate = (
                "replaces"
                if replaced != report.replaces
                else await _failed_gate(conn, projection, build_id, replaced, report)
            )
            if not gate:
                try:
                    await _switch(conn, projection, build_id, replaced, report)
                except psycopg.errors.UniqueViolation:
                    # build_one_serving: another Build's switch, of a row this one did not see
                    # and so did not lock, committed first. A retry would read it as serving.
                    gate = "replaces"
            if gate:
                _log(logging.WARNING, "switch refused", projection, build_id, reason=gate)
                raise Refused(
                    409,
                    "FAILED_PRECONDITION",
                    "GATE_FAILED",
                    f"The switch failed the gate {gate}.",
                    metadata={"gate": gate},
                )
            state, changed = "serving", [b for b in (build_id, replaced) if b]
        await conn.execute(
            "UPDATE build SET reported_at = now() WHERE projection = %s AND build_id = %s",
            (projection, build_id),
        )
    _log(logging.INFO, "build state", projection, build_id, state=state, reported=report.state)
    repair = Repair(reason=reason, requested_at=requested_at) if reason else None
    return BuildAnswer(state=state, repair_requested=repair), changed


async def _switch(
    conn: AsyncConnection, projection: str, build_id: str, replaced: str | None, report: BuildReport
) -> None:
    """Makes the Build the serving one and the one it replaces `retained`."""
    await conn.execute(
        "UPDATE build SET state = 'retained' WHERE projection = %s AND build_id = %s",
        (projection, replaced),
    )
    await conn.execute(
        "UPDATE build SET state = 'serving', switch_seq = %s, feed_position = %s,"
        " approval_ref = %s, evidence_ref = %s WHERE projection = %s AND build_id = %s",
        (
            report.switch_seq,
            report.feed_position,
            report.approval_ref,
            report.evidence_ref,
            projection,
            build_id,
        ),
    )


async def _failed_gate(
    conn: AsyncConnection,
    projection: str,
    build_id: str,
    replaced: str | None,
    report: BuildReport,
) -> str | None:
    """The first switch gate of D2 the Build fails: caught up with the feed, serving no fewer
    Documents than the Build it replaces, no fact of a Document deleted or moved out of the
    fact's Resource."""
    assert report.feed_position is not None
    try:
        lag = await feed.lag_s(conn, report.feed_position)
    except ValueError:
        raise Refused(
            400, "INVALID_ARGUMENT", "INVALID_ARGUMENT", "feed_position: not a feed position"
        ) from None
    if lag > SWITCH_LAG_MAX_S:
        return "caught_up"
    # A fact being written over one that was included still serves the earlier revision.
    cursor = await conn.execute(
        "SELECT build_id, count(*) FROM serving_fact WHERE projection = %s"
        " AND (state = 'included' OR served_source_revision_id IS NOT NULL)"
        " AND build_id = ANY(%s) GROUP BY build_id",
        (projection, [build_id, replaced]),
    )
    serves = dict(await cursor.fetchall())
    if serves.get(build_id, 0) < serves.get(replaced, 0):
        return "coverage"
    cursor = await conn.execute(
        "SELECT count(*) FROM serving_fact f LEFT JOIN document d USING (document_uid)"
        " WHERE f.projection = %s AND f.build_id = %s AND f.state <> 'removed'"
        " AND (d.document_uid IS NULL OR d.deleted_at IS NOT NULL"
        "      OR d.resource_id <> f.resource_id)",
        (projection, build_id),
    )
    [(stray,)] = await cursor.fetchall()
    return "removed_documents" if stray else None


async def register(
    conn: AsyncConnection, projection: str, build_id: str, facts: Sequence[Fact]
) -> Answer:
    """Records every fact as `pending`, or none, with the B5 check in the same transaction (DR
    §5.2, K1): each Document is not deleted, is bound to the fact's Resource, and has the fact's
    revisions as its current ones. The Documents stay locked until it commits, so a deletion's
    judgment (#98) that locks the Document sees the `pending` fact or comes first. Refused: 409
    SUPERSEDED naming the first Document that fails the check, 409 FENCED when the expiry fence
    stops a fact (a repair is then requested), 404 for a Build the projection did not report."""
    uids = sorted({f.document_uid for f in facts})
    now = datetime.now(UTC)
    fenced: Fact | None = None
    async with conn.transaction():
        # A statement of its own, in declaration and finalization's order (document_id).
        await conn.execute(
            "SELECT 1 FROM document WHERE document_uid = ANY(%s) ORDER BY document_id,"
            " document_uid FOR UPDATE",
            (uids,),
        )
        cursor = await conn.execute(
            "SELECT document_uid, resource_id, current_source_revision_id,"
            " current_canonical_revision_id FROM document"
            " WHERE document_uid = ANY(%s) AND deleted_at IS NULL",
            (uids,),
        )
        current = {row[0]: row[1:] for row in await cursor.fetchall()}
        repair = await _reported(conn, projection, build_id)
        for fact in facts:
            stated = (fact.resource_id, fact.source_revision_id, fact.canonical_revision_id)
            if current.get(fact.document_uid) != stated:
                facts_taken.labels(projection, "superseded").inc()
                _log(logging.WARNING, "registration refused", projection, build_id, fact=fact,
                     reason="SUPERSEDED")  # fmt: skip
                raise Refused(
                    409,
                    "FAILED_PRECONDITION",
                    "SUPERSEDED",
                    "The Document's current revision or binding is not the registration's.",
                    metadata={"document_uid": fact.document_uid},
                )
        held = await _held(conn, projection, build_id, uids)
        placed: list[tuple[Fact, str]] = []
        for fact in facts:
            key = (fact.document_uid, fact.resource_id)
            placed.append((fact, _place(held.get(key), fact, now)))
            if placed[-1][1] == "recorded":  # a later fact of the call with the same key meets it
                held[key] = ("pending", fact.fact_version, now)
        fenced = next((f for f, result in placed if result == "fenced"), None)
        if fenced:
            repair = await _repair(conn, projection, build_id, repair, "fenced")
        else:
            for fact, result in placed:
                if result == "recorded":
                    await _record(conn, projection, build_id, fact, "pending")
                facts_taken.labels(projection, result).inc()
    if fenced:  # after the commit, which keeps the repair request
        facts_taken.labels(projection, "fenced").inc()
        _log(logging.WARNING, "registration refused", projection, build_id, fact=fenced,
             reason="FENCED")  # fmt: skip
        raise Refused(
            409,
            "FAILED_PRECONDITION",
            "FENCED",
            "A fact is at or below an expired removal; send a repair view.",
            metadata={"document_uid": fenced.document_uid},
        )
    _log(logging.INFO, "registered", projection, build_id, count=len(facts))
    return Answer(repair_requested=repair)


async def report_facts(
    conn: AsyncConnection, projection: str, build_id: str, facts: Sequence[ServingFact]
) -> FactsAnswer:
    """Takes `included` and `removed` facts one by one, in one transaction (DR §5.1, §5.3): the
    highest fact_version of a key is kept and an older one changes nothing. A fact the expiry
    fence stops is not recorded and is listed in the answer, and a repair is requested; the
    other facts of the call are taken. 404 for a Build the projection did not report."""
    now = datetime.now(UTC)
    fenced: list[Key] = []
    landed: list[str] = []
    counts = {"recorded": 0, "older": 0, "fenced": 0}
    async with conn.transaction():
        repair = await _reported(conn, projection, build_id)
        held = await _held(conn, projection, build_id, [f.document_uid for f in facts])
        for fact in facts:
            key = (fact.document_uid, fact.resource_id)
            result = _place(held.get(key), fact, now)
            counts[result] += 1
            if result == "recorded":
                await _record(conn, projection, build_id, fact, fact.state)
                held[key] = (fact.state, fact.fact_version, now)
                if fact.state == "included":
                    landed.append(fact.document_uid)
            elif result == "fenced":
                fenced.append(Key(document_uid=key[0], resource_id=key[1]))
                _log(logging.WARNING, "fact fenced", projection, build_id, fact=fact)
        if fenced:
            repair = await _repair(conn, projection, build_id, repair, "fenced")
        cursor = await conn.execute(
            "SELECT count(*) FROM document WHERE document_uid = ANY(%s) AND deleted_at IS NOT NULL",
            (landed,),
        )
        [(late,)] = await cursor.fetchall()
    for result, count in counts.items():
        facts_taken.labels(projection, result).inc(count)
    late_landings.labels(projection).inc(late)
    _log(logging.INFO, "facts taken", projection, build_id, late_landings=late, results=counts)
    return FactsAnswer(fenced=fenced, repair_requested=repair)


async def heartbeat(
    conn: AsyncConnection, projection: str, build_id: str, beat: Heartbeat
) -> Answer:
    """Compares the Build's count and digest with the mirror's `included` and `pending` facts
    (DR §5.5) and asks for a repair when they differ, or when a `pending` fact is older than
    PENDING_MAX (§5.2). 404 for a Build the projection did not report."""
    now = datetime.now(UTC)
    async with conn.transaction():
        repair = await _reported(conn, projection, build_id)
        cursor = await conn.execute(
            "SELECT document_uid, resource_id, canonical_revision_id, state, recorded_at"
            " FROM serving_fact WHERE projection = %s AND build_id = %s AND state <> 'removed'",
            (projection, build_id),
        )
        rows = await cursor.fetchall()
        # shortcut: reads and hashes the whole Build while it holds the Build's row, so its other
        # reports wait, keep a running count and digest per Build when one holds millions.
        mirror = await asyncio.to_thread(digest, [row[:3] for row in rows])
        reason = None
        if (len(rows), mirror) != (beat.count, beat.digest):
            reason = "heartbeat_mismatch"
        elif any(row[3] == "pending" and row[4] + PENDING_MAX < now for row in rows):
            reason = "pending_expired"
        if reason:
            repair = await _repair(conn, projection, build_id, repair, reason)
    _log(logging.INFO, "heartbeat", projection, build_id, count=beat.count, reason=reason)
    return Answer(repair_requested=repair)


def digest(entries: Iterable[tuple[str, str, str]]) -> str:
    """The heartbeat digest (DR §5.5, spec §7.4) of (document_uid, resource_id, Canonical
    Revision) entries: the XOR of each one's SHA-256 over the three joined by the byte 0x1F, as
    64 hex digits; all zeros for none."""
    total = 0
    for entry in entries:
        total ^= int.from_bytes(hashlib.sha256("\x1f".join(entry).encode()).digest())
    return f"{total:064x}"


async def repair_view(
    conn: AsyncConnection, projection: str, build_id: str, view_id: str, number: int, page: ViewPage
) -> tuple[ViewAnswer, bool]:
    """Takes page `number` of a repair view of the Build (DR §5.4), in one transaction, and
    returns whether the caller refreshes the readiness of the Build's Documents: the page
    completed the view, or is a resend of the view installed. A view captured after the Build's
    last one starts and ends any other in transfer. Pages arrive in any order, a duplicate
    changes nothing, and when every page is in, the Build's mirror is replaced in one step and
    the repair request ends. Refused: 409 VIEW_DISCARDED naming why (`expired`, past
    VIEW_LIFETIME from capture; `fenced`, an entry the expiry fence stops; `writes_lost`, the
    view was in transfer or done when committed writes were lost; `superseded`, a later view
    started), which except for `superseded` asks for a fresh view; 400 for a page beyond
    `pages`, a header unlike the view's first page or a captured_at more than CLOCK_SKEW ahead
    of the platform's clock; 404 for a Build the projection did not
    report."""
    if number > page.pages:
        raise Refused(400, "INVALID_ARGUMENT", "INVALID_ARGUMENT", "page: beyond pages")
    now = datetime.now(UTC)
    if page.captured_at > now + CLOCK_SKEW:
        raise Refused(
            400,
            "INVALID_ARGUMENT",
            "INVALID_ARGUMENT",
            "captured_at: ahead of the platform's clock",
        )
    async with conn.transaction():
        repair = await _reported(conn, projection, build_id)
        cursor = await conn.execute(
            "SELECT view_id, view_state, view_captured_at, view_watermark, view_pages FROM build"
            " WHERE projection = %s AND build_id = %s",
            (projection, build_id),
        )
        [(current, stored, *header)] = await cursor.fetchall()
        if view_id != current:
            if header[0] is not None and page.captured_at <= header[0]:
                # Without a later view in transfer, a lost-writes request still wants a fresh one.
                lost = stored != "incomplete" and repair and repair.reason == "writes_lost"
                stored = "writes_lost" if lost else "superseded"
            else:
                await _start_view(conn, projection, build_id, view_id, page)
                stored = "incomplete"
        # A loss of writes moves view_captured_at; a discarded view's pages are only refused.
        elif stored in ("incomplete", "installed") and tuple(header) != (
            page.captured_at, page.watermark, page.pages
        ):  # fmt: skip
            raise Refused(400, "INVALID_ARGUMENT", "INVALID_ARGUMENT", "a header unlike the view's")
        if stored != "incomplete":
            result = {"installed": "resent", "superseded": "superseded"}.get(stored, "discarded")
        elif now >= page.captured_at + VIEW_LIFETIME:
            result = "expired"
        else:
            await _add_page(conn, projection, build_id, number, page)
            result = "incomplete"
            if await _complete(conn, projection, build_id, page.pages):
                result = await _install(conn, projection, build_id, page, now)
        if result in ("expired", "fenced"):
            await _end_view(conn, projection, build_id, result)
            repair = await _repair(conn, projection, build_id, repair, f"view_{result}")
        elif result == "installed":
            if repair:
                seconds = (now - repair.requested_at).total_seconds()
                repair_latency.labels(projection).observe(seconds)
            repair = None
    views.labels(projection, result).inc()
    installed = result in ("installed", "resent")
    # Why the page is refused: the view was discarded, now or before, or a later one replaced it.
    refused = (
        None if installed or result == "incomplete" else stored if result == "discarded" else result
    )
    fields: dict[str, Any] = {"reason": refused} if refused else {}
    _log(logging.WARNING if refused else logging.INFO, "repair view", projection, build_id,
         view_id=view_id, page=number, pages=page.pages, watermark=page.watermark,
         count=len(page.entries), result=result, **fields)  # fmt: skip
    if refused:  # after the commit, which keeps the repair request
        raise Refused(
            409,
            "FAILED_PRECONDITION",
            "VIEW_DISCARDED",
            "The repair view was discarded.",
            metadata={"reason": refused},
        )
    answer = ViewAnswer(view="installed" if installed else "incomplete", repair_requested=repair)
    return answer, installed


async def _start_view(
    conn: AsyncConnection, projection: str, build_id: str, view_id: str, page: ViewPage
) -> None:
    await _drop_pages(conn, projection, build_id)
    await conn.execute(
        "UPDATE build SET view_id = %s, view_state = 'incomplete', view_captured_at = %s,"
        " view_watermark = %s, view_pages = %s WHERE projection = %s AND build_id = %s",
        (view_id, page.captured_at, page.watermark, page.pages, projection, build_id),
    )


async def _add_page(
    conn: AsyncConnection, projection: str, build_id: str, number: int, page: ViewPage
) -> None:
    await conn.execute(
        "INSERT INTO repair_page (projection, build_id, page, entries) VALUES (%s, %s, %s, %s)"
        " ON CONFLICT DO NOTHING",
        (projection, build_id, number, Jsonb([e.model_dump() for e in page.entries])),
    )


async def _complete(conn: AsyncConnection, projection: str, build_id: str, pages: int) -> bool:
    cursor = await conn.execute(
        "SELECT count(*) FROM repair_page WHERE projection = %s AND build_id = %s",
        (projection, build_id),
    )
    [(received,)] = await cursor.fetchall()
    return received == pages


async def _drop_pages(conn: AsyncConnection, projection: str, build_id: str) -> None:
    await conn.execute(
        "DELETE FROM repair_page WHERE projection = %s AND build_id = %s", (projection, build_id)
    )


async def _end_view(conn: AsyncConnection, projection: str, build_id: str, state: str) -> None:
    await _drop_pages(conn, projection, build_id)
    await conn.execute(
        "UPDATE build SET view_state = %s WHERE projection = %s AND build_id = %s",
        (state, projection, build_id),
    )


async def _install(
    conn: AsyncConnection, projection: str, build_id: str, page: ViewPage, now: datetime
) -> Literal["installed", "fenced"]:
    """Replaces the Build's mirror with the complete view (DR §5.4 step 4), unless the expiry
    fence stops one of its entries at its own version (step 3). A fact above the watermark was
    reported after the capture and stays; a key of the view takes the view's state, a key it
    lacks becomes a tombstone, both stamped with the watermark. A key the view holds both
    stored and registered is `pending`, its stored revision still served (spec §7.4)."""
    cursor = await conn.execute(
        "SELECT entries FROM repair_page WHERE projection = %s AND build_id = %s ORDER BY page",
        (projection, build_id),
    )
    view: dict[tuple[str, str], dict[str, Any]] = {}
    served: dict[tuple[str, str], str] = {}
    for (entries,) in await cursor.fetchall():
        for e in entries:
            key = (e["document_uid"], e["resource_id"])
            if e["state"] == "included":
                served[key] = e["source_revision_id"]
            if key not in view or e["state"] == "pending":
                view[key] = e
    cursor = await conn.execute(
        "SELECT document_uid, resource_id, state, source_revision_id, canonical_revision_id,"
        " fact_version, recorded_at FROM serving_fact WHERE projection = %s AND build_id = %s",
        (projection, build_id),
    )
    mirror = {(row[0], row[1]): _Row(*row[2:]) for row in await cursor.fetchall()}
    for key, e in view.items():
        if (held := mirror.get(key)) and _fences(
            (held.state, held.version, held.recorded_at), e["fact_version"], page.captured_at, now
        ):
            return "fenced"
    rows = []
    for key in mirror.keys() | view.keys():
        held = mirror.get(key)
        if held and held.version > page.watermark:
            continue
        if e := view.get(key):
            state, srv, crv = e["state"], e["source_revision_id"], e["canonical_revision_id"]
        elif held and (held.state != "removed" or held.recorded_at + TOMBSTONE > now):
            state, srv, crv = "removed", held.srv, held.crv
        else:
            continue  # an expired tombstone stays as it is: it still fences (DR §5.3)
        kept = served.get(key) if state == "pending" else None
        rows.append((projection, build_id, *key, state, srv, crv, page.watermark, kept))
    # shortcut: rewrites the whole Build in one transaction while it holds the Build's row, which
    # the database ends at 60 s; write only the keys that change when #99 measures a large Build.
    async with conn.cursor() as cur:
        await cur.executemany(
            "INSERT INTO serving_fact (projection, build_id, document_uid, resource_id, state,"
            " source_revision_id, canonical_revision_id, fact_version, served_source_revision_id)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (projection, build_id, document_uid, resource_id) DO UPDATE SET"
            " state = excluded.state, source_revision_id = excluded.source_revision_id,"
            " canonical_revision_id = excluded.canonical_revision_id,"
            " fact_version = excluded.fact_version, recorded_at = now(),"
            " served_source_revision_id = excluded.served_source_revision_id",
            rows,
        )
    await _end_view(conn, projection, build_id, "installed")
    await conn.execute(
        "UPDATE build SET repair_reason = NULL, repair_requested_at = NULL"
        " WHERE projection = %s AND build_id = %s",
        (projection, build_id),
    )
    return "installed"


async def lose_writes(conn: AsyncConnection, event: int) -> int | None:
    """Applies operations' declaration that the admission database lost committed writes (DR
    §5.6, K2), once per `event`, a number each declaration raises: every Build not retired is
    asked for a repair, `writes_lost`, which replaces any earlier request, and its last view,
    in transfer or installed, is discarded, so only a view captured after now ends the request.
    A Build first reported while one still carries that request starts with it (report_build).
    Returns how many Builds were asked, or None for the event applied last, run again.
    ValueError for an event below it: the declaration's number was not raised."""
    async with conn.transaction():
        cursor = await conn.execute("SELECT coalesce(max(event), 0) FROM writes_lost")
        [(applied,)] = await cursor.fetchall()
        if event < applied:
            raise ValueError(f"event {event} is below the last applied, {applied}")
        if event == applied:
            return None
        cursor = await conn.execute(
            "INSERT INTO writes_lost (event) VALUES (%s) ON CONFLICT DO NOTHING RETURNING event",
            (event,),
        )
        if await cursor.fetchone() is None:
            return None  # a concurrent run applied it
        # In report_build's order within a projection, which locks a projection's Builds.
        await conn.execute(
            "SELECT 1 FROM build WHERE state <> 'retired' ORDER BY projection, build_id FOR UPDATE"
        )
        cursor = await conn.execute(
            "UPDATE build SET repair_reason = 'writes_lost', repair_requested_at = now(),"
            " view_captured_at = now(),"
            " view_state = CASE WHEN view_id IS NULL THEN NULL ELSE 'writes_lost' END"
            " WHERE state <> 'retired' RETURNING projection, build_id"
        )
        builds = await cursor.fetchall()
        await conn.execute("DELETE FROM repair_page")  # pages are only of views in transfer
    for projection, build_id in builds:
        repairs.labels(projection, "writes_lost").inc()
        _log(logging.WARNING, "repair requested", projection, build_id, reason="writes_lost")
    return len(builds)


async def writes_unrepaired(conn: AsyncConnection) -> list[tuple[str, str]]:
    """(projection, build_id) of the Builds not retired that no view captured after the last
    loss of committed writes has repaired. While there is one, and for the longest update
    interval of the registered pipelines after the declaration, #98 makes no enforcement
    judgment (DR §5.6, K2, spec §7.4)."""
    cursor = await conn.execute(
        "SELECT projection, build_id FROM build WHERE repair_reason = 'writes_lost'"
        " AND state <> 'retired' ORDER BY 1, 2"
    )
    return await cursor.fetchall()


async def take_attempt(
    conn: AsyncConnection, pipeline: Pipeline, build_id: str, report: AttemptReport
) -> Literal["recorded", "repeated"] | AttemptPosition:
    """Takes a projection's status report (spec §7.4), in one transaction. The unit is the
    Build, the Document and its Canonical Revision; the highest attempt_no reported for it is
    its current attempt, and within it #97's rule holds: a seq above the last one taken is
    recorded, the last report again is `repeated`, and anything else, a lower attempt_no
    included, is answered with the current position. 400 for a stage the pipeline did not
    register, 404 for a Build the projection did not report."""
    if report.stage not in pipeline.stages:
        raise Refused(
            400,
            "INVALID_ARGUMENT",
            "INVALID_ARGUMENT",
            "stage: not a stage the pipeline registered",
        )
    projection, body = pipeline.track, report.model_dump(mode="json")
    unit = (projection, build_id, report.document_uid, report.canonical_revision_id)
    async with conn.transaction():
        await _reported(conn, projection, build_id)
        cursor = await conn.execute(
            "SELECT attempt_no, last_report FROM projection_attempt WHERE projection = %s"
            " AND build_id = %s AND document_uid = %s AND canonical_revision_id = %s",
            unit,
        )
        result: Literal["recorded", "repeated"] | AttemptPosition = "recorded"
        if row := await cursor.fetchone():
            attempt_no, last = row
            if last == body:
                result = "repeated"
            elif report.attempt_no < attempt_no or (
                report.attempt_no == attempt_no and report.seq <= last["seq"]
            ):
                result = AttemptPosition(attempt_no=attempt_no, seq=last["seq"])
        if result == "recorded":
            await conn.execute(
                "INSERT INTO projection_attempt (projection, build_id, document_uid,"
                " canonical_revision_id, source_revision_id, attempt_no, last_report)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (projection, build_id,"
                " document_uid, canonical_revision_id) DO UPDATE SET source_revision_id ="
                " excluded.source_revision_id, attempt_no = excluded.attempt_no,"
                " last_report = excluded.last_report, reported_at = now()",
                (*unit, report.source_revision_id, report.attempt_no, Jsonb(body)),
            )
    fields: dict[str, Any] = {
        "document_uid": report.document_uid,
        "attempt_no": report.attempt_no,
        "seq": report.seq,
        "stage": report.stage,
        "state": report.state,
        "result": result if isinstance(result, str) else "out_of_order",
    }
    if report.error:
        fields["reason"] = report.error.reason  # never the message: it can be exception text
    level = logging.INFO if isinstance(result, str) else logging.WARNING
    _log(level, "attempt report", projection, build_id, **fields)
    return result


async def report_backfill(
    conn: AsyncConnection, projection: str, source_id: str, profile_seq: str
) -> None:
    """Records that the projection finished its backfill of the Source at `profile_seq` (DR B1);
    an earlier one than recorded changes nothing. 404 for a Source without a Knowledge Profile,
    400 for a profile_seq after the Source's own."""
    async with conn.transaction():
        cursor = await conn.execute(
            "SELECT tenant_id, profile_seq, backfilled FROM source WHERE source_id = %s FOR UPDATE",
            (source_id,),
        )
        if (row := await cursor.fetchone()) is None:
            raise Refused(404, "NOT_FOUND", "NOT_FOUND", "No such Source.")
        tenant_id, current, backfilled = row
        if profile_seq > current:
            raise Refused(
                400,
                "INVALID_ARGUMENT",
                "INVALID_ARGUMENT",
                "profile_seq: after the Source's profile_seq",
            )
        if backfilled.get(projection, "") < profile_seq:
            await conn.execute(
                "UPDATE source SET backfilled = %s WHERE tenant_id = %s AND source_id = %s",
                (Jsonb(backfilled | {projection: profile_seq}), tenant_id, source_id),
            )
    log.info(
        "backfill reported",
        extra={"correlation": {"projection": projection, "source_id": source_id}},
    )


async def required(conn: AsyncConnection, tenant_id: str, source_id: str) -> dict[str, bool]:
    """The Source's required projections, in the profile's order, and whether each counts toward
    readiness (DR B1): one of the Source's first profile does at once, one added later when its
    owner reported the backfill complete at or after the profile_seq that added it."""
    cursor = await conn.execute(
        "SELECT projections, added, backfilled FROM source WHERE tenant_id = %s AND source_id = %s",
        (tenant_id, source_id),
    )
    if (row := await cursor.fetchone()) is None:
        return {}
    projections, added, backfilled = row
    return {p: backfilled.get(p, "") >= added.get(p, "") for p in projections}


async def served(conn: AsyncConnection, uids: Sequence[str]) -> dict[str, dict[str, Served]]:
    """Per Document and projection, the Source Revision the projection's serving Build includes
    for the Document's current Resource; while it writes a newer one over it, still that one."""
    cursor = await conn.execute(
        "SELECT f.document_uid, f.projection, v.srv, s.source_version"
        " FROM serving_fact f"
        " JOIN build b ON b.projection = f.projection AND b.build_id = f.build_id"
        " JOIN document d ON d.document_uid = f.document_uid AND d.resource_id = f.resource_id"
        " CROSS JOIN LATERAL (SELECT CASE WHEN f.state = 'included' THEN f.source_revision_id"
        "  WHEN f.state = 'pending' THEN f.served_source_revision_id END AS srv) v"
        " LEFT JOIN source_revision s ON s.source_revision_id = v.srv"
        " WHERE f.document_uid = ANY(%s) AND v.srv IS NOT NULL AND b.state = 'serving'",
        (list(uids),),
    )
    found: dict[str, dict[str, Served]] = {}
    for uid, projection, srv, version in await cursor.fetchall():
        found.setdefault(uid, {})[projection] = Served(srv, version)
    return found


async def attempts(conn: AsyncConnection, uids: Sequence[str]) -> dict[str, dict[str, Attempt]]:
    """Per Document and projection, the current attempt for the Document's current Canonical
    Revision in the projection's serving Build: the only attempt attention reads (DR C4)."""
    cursor = await conn.execute(
        "SELECT a.document_uid, a.projection, a.source_revision_id, a.last_report, a.reported_at"
        " FROM projection_attempt a"
        " JOIN build b ON b.projection = a.projection AND b.build_id = a.build_id"
        " JOIN document d ON d.document_uid = a.document_uid"
        "  AND d.current_canonical_revision_id = a.canonical_revision_id"
        " WHERE a.document_uid = ANY(%s) AND b.state = 'serving'",
        (list(uids),),
    )
    found: dict[str, dict[str, Attempt]] = {}
    for uid, projection, srv, last, at in await cursor.fetchall():
        found.setdefault(uid, {})[projection] = Attempt(srv, last, at)
    return found


async def serving_builds(conn: AsyncConnection) -> dict[str, datetime]:
    """Each projection's serving Build's last report of any kind: its liveness signal."""
    cursor = await conn.execute("SELECT projection, reported_at FROM build WHERE state = 'serving'")
    return dict(await cursor.fetchall())


async def documents(
    conn: AsyncConnection, projection: str, builds: Sequence[str], after: str, limit: int
) -> list[str]:
    """Up to `limit` uids, in order after `after`, of the Documents the Builds hold a fact of."""
    cursor = await conn.execute(
        "SELECT DISTINCT document_uid FROM serving_fact WHERE projection = %s"
        " AND build_id = ANY(%s) AND document_uid > %s ORDER BY document_uid LIMIT %s",
        (projection, list(builds), after, limit),
    )
    return [uid for (uid,) in await cursor.fetchall()]


async def held(conn: AsyncConnection, document_uid: str) -> list[tuple[str, str, str, str]]:
    """(projection, build_id, resource_id, state) of each `included` or `pending` fact a Build
    not retired holds of the Document. C3 (#98) judges a deletion enforced when there is none,
    and a move out of a Resource complete when none names it."""
    cursor = await conn.execute(
        "SELECT f.projection, f.build_id, f.resource_id, f.state FROM serving_fact f"
        " JOIN build b ON b.projection = f.projection AND b.build_id = f.build_id"
        " WHERE f.document_uid = %s AND f.state <> 'removed' AND b.state <> 'retired'"
        " ORDER BY 1, 2, 3",
        (document_uid,),
    )
    return await cursor.fetchall()


async def silent(
    conn: AsyncConnection, pipelines: Mapping[str, Pipeline], now: datetime
) -> list[tuple[str, str]]:
    """(projection, build_id) of the Builds not retired without liveness: no report within the
    update interval of the projection's pipeline, `pipelines` by track. While there is one, #98
    makes no enforcement judgment (R-c). Sets kp_serving_builds_without_liveness."""
    cursor = await conn.execute(
        "SELECT projection, build_id, reported_at FROM build WHERE state <> 'retired' ORDER BY 1, 2"
    )
    found = [
        (projection, build_id)
        for projection, build_id, at in await cursor.fetchall()
        if (p := pipelines.get(projection)) and at + timedelta(seconds=p.update_interval_s) < now
    ]
    without_liveness.clear()
    for projection in pipelines.keys() - {"canonical"}:
        without_liveness.labels(projection).set(sum(p == projection for p, _ in found))
    return found


async def _reported(conn: AsyncConnection, projection: str, build_id: str) -> Repair | None:
    """Marks a report of the Build, its liveness signal, and returns the repair asked of it. It
    locks the Build's row, so the reports of one Build are taken one at a time. 409 BUILD_STATE
    for a retired Build: its data is gone, and `held` no longer reads its facts."""
    cursor = await conn.execute(
        "UPDATE build SET reported_at = now() WHERE projection = %s AND build_id = %s"
        " RETURNING repair_reason, repair_requested_at, state, view_state, view_captured_at",
        (projection, build_id),
    )
    if (row := await cursor.fetchone()) is None:
        raise Refused(404, "NOT_FOUND", "NOT_FOUND", "The projection reported no such Build.")
    reason, requested_at, state, view_state, captured_at = row
    if state == "retired":
        raise Refused(
            409,
            "FAILED_PRECONDITION",
            "BUILD_STATE",
            "The Build is retired.",
            metadata={"state": "retired"},
        )
    repair = Repair(reason=reason, requested_at=requested_at) if reason else None
    # A view whose pages stopped coming is discarded by the Build's next report (DR §5.4).
    if view_state == "incomplete" and captured_at + VIEW_LIFETIME <= datetime.now(UTC):
        await _end_view(conn, projection, build_id, "expired")
        views.labels(projection, "expired").inc()
        repair = await _repair(conn, projection, build_id, repair, "view_expired")
    return repair


async def _repair(
    conn: AsyncConnection, projection: str, build_id: str, asked: Repair | None, reason: Any
) -> Repair:
    """Asks the Build's owner for a repair view, unless one is asked for already."""
    if asked:
        return asked
    cursor = await conn.execute(
        "UPDATE build SET repair_reason = %s, repair_requested_at = now()"
        " WHERE projection = %s AND build_id = %s RETURNING repair_requested_at",
        (reason, projection, build_id),
    )
    [(requested_at,)] = await cursor.fetchall()
    repairs.labels(projection, reason).inc()
    _log(logging.WARNING, "repair requested", projection, build_id, reason=reason)
    return Repair(reason=reason, requested_at=requested_at)


async def _held(
    conn: AsyncConnection, projection: str, build_id: str, uids: Sequence[str]
) -> dict[tuple[str, str], _Held]:
    cursor = await conn.execute(
        "SELECT document_uid, resource_id, state, fact_version, recorded_at FROM serving_fact"
        " WHERE projection = %s AND build_id = %s AND document_uid = ANY(%s)",
        (projection, build_id, list(uids)),
    )
    return {(row[0], row[1]): row[2:] for row in await cursor.fetchall()}


def _place(held: _Held | None, fact: Fact, now: datetime) -> Literal["recorded", "older", "fenced"]:
    """Where a reported fact stands against the one held for its key. The highest fact_version
    wins (C2). A tombstone past its 30 days counts as no fact, except that it stops a report at
    or below its version that was issued before it expired (§5.3)."""
    if held is None:
        return "recorded"
    if _fences(held, fact.fact_version, fact.issued_at, now):
        return "fenced"
    state, version, recorded_at = held
    if state == "removed" and recorded_at + TOMBSTONE <= now:
        return "recorded"
    return "recorded" if fact.fact_version > version else "older"


def _fences(held: _Held, version: int, issued: datetime, now: datetime) -> bool:
    """Whether the held fact is an expired tombstone that stops a report at `version` issued
    (for a repair view, captured) at `issued` (DR §5.3)."""
    state, held_version, recorded_at = held
    expiry = recorded_at + TOMBSTONE
    return state == "removed" and expiry <= now and version <= held_version and issued < expiry


async def _record(
    conn: AsyncConnection, projection: str, build_id: str, fact: Fact, state: str
) -> None:
    await conn.execute(
        "INSERT INTO serving_fact (projection, build_id, document_uid, resource_id, state,"
        " source_revision_id, canonical_revision_id, fact_version)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        " ON CONFLICT (projection, build_id, document_uid, resource_id) DO UPDATE SET"
        " state = excluded.state, source_revision_id = excluded.source_revision_id,"
        " canonical_revision_id = excluded.canonical_revision_id,"
        " fact_version = excluded.fact_version, recorded_at = now(),"
        # A write over a served revision keeps it for readiness until confirmed (spec §7.4).
        " served_source_revision_id = CASE WHEN excluded.state <> 'pending' THEN NULL"
        " WHEN serving_fact.state = 'included' THEN serving_fact.source_revision_id"
        " ELSE serving_fact.served_source_revision_id END",
        (
            projection,
            build_id,
            fact.document_uid,
            fact.resource_id,
            state,
            fact.source_revision_id,
            fact.canonical_revision_id,
            fact.fact_version,
        ),
    )


def _log(
    level: int,
    message: str,
    projection: str,
    build_id: str,
    fact: Fact | None = None,
    **fields: Any,
) -> None:
    correlation = {"projection": projection, "build_id": build_id} | fields
    if fact:
        correlation |= fact.model_dump(include={"document_uid", "resource_id", "fact_version"})
    log.log(level, message, extra={"correlation": correlation})
