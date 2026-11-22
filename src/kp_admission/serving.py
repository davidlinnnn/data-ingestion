"""Projection report intake (#252, admission spec §7.4, canonical consumption DR §4–§5): the
platform's mirror of the serving facts each projection reports per Build, the Builds' states,
the projections' attempts and their backfill reports. kp_admission.status reads it for readiness
and attention; Source Deletion's judgment (#98) reads `held` and `silent`.

Metrics:

- `kp_serving_facts_total` (count) of the facts and registrations reported, by `projection` and
  `result`: recorded, older (a higher fact_version is held), fenced (§5.3), superseded (a
  registration that failed the B5 check).
- `kp_serving_repairs_requested_total` (count) by `projection` and `reason`
  (heartbeat_mismatch, pending_expired, fenced): a Build newly asked for a repair view.
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

from prometheus_client import Counter, Gauge
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
without_liveness = Gauge(
    "kp_serving_builds_without_liveness",
    "Builds not retired that stopped reporting",
    ["projection"],
)

TOMBSTONE = timedelta(days=30)  # how long a `removed` fact is held (DR §5.3)
# Provisional until #127 measures a projection's store writes: a slow write, with a liveness
# pause, stays below it, and a lost confirmation is repaired within the hour.
PENDING_MAX = timedelta(minutes=30)
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
    profile_seq: str = Field(min_length=1)


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


class Key(BaseModel):
    document_uid: str
    resource_id: str


class Repair(BaseModel):
    reason: Literal["heartbeat_mismatch", "pending_expired", "fenced"]
    requested_at: datetime


class Answer(BaseModel):
    """Every 2xx of a Build's reports says whether the platform asks for a repair view of it
    (DR §5.1); #260 takes the view and ends the request."""

    repair_requested: Repair | None


class FactsAnswer(Answer):
    fenced: list[Key]  # not recorded, and never to be sent again (DR §5.3)


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


async def report_build(
    conn: AsyncConnection, projection: str, build_id: str, report: BuildReport
) -> tuple[BuildAnswer, list[str]]:
    """Takes a Build's state report (DR §4, D2), in one transaction, and returns the Builds whose
    Documents' readiness it may have changed. A Build starts `building`. `serving` is a switch:
    the platform re-runs the gates and, in the same step, retains the Build it replaces; a switch
    numbered at or below the projection's last one came late and changes nothing. `retired` is
    final. A report of the state the Build is in is a repeat. Refused: 409 GATE_FAILED naming
    the gate (replaces, caught_up, coverage, removed_documents), 409 BUILD_STATE for a state the
    Build cannot take from where it is, 400 for a feed_position that is not one."""
    async with conn.transaction():
        await conn.execute(
            "INSERT INTO build (projection, build_id, state) VALUES (%s, %s, 'building')"
            " ON CONFLICT DO NOTHING",
            (projection, build_id),
        )
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
            changed = [build_id] if state == "serving" else []  # a retry finishes the refresh
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
            if gate:
                _log(logging.WARNING, "switch refused", projection, build_id, reason=gate)
                raise Refused(
                    409,
                    "FAILED_PRECONDITION",
                    "GATE_FAILED",
                    f"The switch failed the gate {gate}.",
                    metadata={"gate": gate},
                )
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
            state, changed = "serving", [b for b in (build_id, replaced) if b]
        await conn.execute(
            "UPDATE build SET reported_at = now() WHERE projection = %s AND build_id = %s",
            (projection, build_id),
        )
    _log(logging.INFO, "build state", projection, build_id, state=state, reported=report.state)
    repair = Repair(reason=reason, requested_at=requested_at) if reason else None
    return BuildAnswer(state=state, repair_requested=repair), changed


async def _failed_gate(
    conn: AsyncConnection,
    projection: str,
    build_id: str,
    replaced: str | None,
    report: BuildReport,
) -> str | None:
    """The first switch gate of D2 the Build fails: caught up with the feed, coverage not below
    the Build it replaces, no fact of a Document deleted or moved out of the fact's Resource."""
    assert report.feed_position is not None
    try:
        lag = await feed.lag_s(conn, report.feed_position)
    except ValueError:
        raise Refused(
            400, "INVALID_ARGUMENT", "INVALID_ARGUMENT", "feed_position: not a feed position"
        ) from None
    if lag > SWITCH_LAG_MAX_S:
        return "caught_up"
    cursor = await conn.execute(
        "SELECT build_id, count(*) FROM serving_fact WHERE projection = %s AND state = 'included'"
        " AND build_id = ANY(%s) GROUP BY build_id",
        (projection, [build_id, replaced]),
    )
    included = dict(await cursor.fetchall())
    if included.get(build_id, 0) < included.get(replaced, 0):
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
        placed = [(f, _place(held.get((f.document_uid, f.resource_id)), f, now)) for f in facts]
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
        # reports wait; keep a running count and digest per Build when one holds millions.
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
    for the Document's current Resource."""
    cursor = await conn.execute(
        "SELECT f.document_uid, f.projection, f.source_revision_id, s.source_version"
        " FROM serving_fact f"
        " JOIN build b ON b.projection = f.projection AND b.build_id = f.build_id"
        " JOIN document d ON d.document_uid = f.document_uid AND d.resource_id = f.resource_id"
        " LEFT JOIN source_revision s ON s.source_revision_id = f.source_revision_id"
        " WHERE f.document_uid = ANY(%s) AND f.state = 'included' AND b.state = 'serving'",
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
    for projection in pipelines:
        without_liveness.labels(projection).set(sum(p == projection for p, _ in found))
    return found


async def _reported(conn: AsyncConnection, projection: str, build_id: str) -> Repair | None:
    """Marks a report of the Build, its liveness signal, and returns the repair asked of it. It
    locks the Build's row, so the reports of one Build are taken one at a time."""
    cursor = await conn.execute(
        "UPDATE build SET reported_at = now() WHERE projection = %s AND build_id = %s"
        " RETURNING repair_reason, repair_requested_at",
        (projection, build_id),
    )
    if (row := await cursor.fetchone()) is None:
        raise Refused(404, "NOT_FOUND", "NOT_FOUND", "The projection reported no such Build.")
    return Repair(reason=row[0], requested_at=row[1]) if row[0] else None


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
    state, version, recorded_at = held
    expiry = recorded_at + TOMBSTONE
    if state == "removed" and expiry <= now:
        behind = fact.fact_version <= version and fact.issued_at < expiry
        return "fenced" if behind else "recorded"
    return "recorded" if fact.fact_version > version else "older"


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
        " fact_version = excluded.fact_version, recorded_at = now()",
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
