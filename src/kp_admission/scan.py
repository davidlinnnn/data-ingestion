"""The scan (#98, admission spec §9): a CronJob that, under the version adopted for each
Document's media type, reruns a latest Source Revision without a result, refreshes a current
Canonical Revision a version in the refresh scope made, and redoes one a withdrawn version made.

A Document that is deleted or has an active request is left alone. For the others, the first
rule that holds decides:

1. The latest Source Revision's Canonical Revision is current and the adopted version made it:
   nothing.
2. It is current and another version made it: when that version is withdrawn or in the latest
   adoption's refresh scope, and the revision may be reopened, a platform request, low priority.
3. The latest Source Revision has none and may be reopened: an operator request, normal
   priority, whatever the scope.
4. It has none and may not be reopened; the current one, of an earlier Source Revision, is a
   withdrawn version's or in the scope, and its Source Revision may be reopened: a platform
   request for that Source Revision, low priority.
5. Otherwise nothing; the current revision, if any, is still served.

Whether a Source Revision may be reopened follows from the last request of it under the
adoption, whoever made it: none, yes; a retryable failure, once the retry interval since it
has passed; a withdrawn version, at once; a failure that is not retryable, a rejection or a
success without a candidate, not before the next adoption. No request the scan makes counts
against a quota."""

import logging
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from psycopg import AsyncConnection

from kp_admission import adoption, gauges
from kp_admission.requests import ERROR_DOMAIN, create_process_request

# The retry interval after the nth retryable failure of a Source Revision under an adoption:
# RETRY_FIRST * 2^(n-1), at most RETRY_CAP, so the documents an outage left are rerun within an
# hour of its end and a service that is down is asked once an hour per document. The CronJob
# runs every 5 minutes, which rounds each interval up by at most that much.
RETRY_FIRST = timedelta(minutes=10)
RETRY_CAP = timedelta(hours=1)
WARN_AFTER = 5  # retryable failures after which kp_admission_reruns_retrying counts it
# The scan's requests waiting for dispatch it keeps at most, the PROD burst's 500 documents
# (#88): a refresh of every Document trickles in as the dispatcher's budgets take them.
PACE = 500
OVERDUE = timedelta(hours=1)  # the time limit of the documents and requests gauges
PAGE = 500

Initiator = Literal["operator", "platform"]


@dataclass(frozen=True)
class Plan:
    """The request the scan opens for a Document; rank orders the run: 0 a rerun of content
    never accepted, 1 a redo of a withdrawn version's revision, 2 a refresh."""

    tenant_id: str
    source_revision_id: str
    initiator: Initiator
    rank: int
    adopted: tuple[str, int]


@dataclass(frozen=True)
class Limit:
    """Whether a Source Revision may be reopened under the adoption; when not before the next
    adoption, `stopped` is why, and `retrying` is the last failure's reason once WARN_AFTER
    retryable failures have passed."""

    open: bool
    stopped: str | None = None
    retrying: str | None = None


_DOCUMENT = """
SELECT d.tenant_id, d.deleted_at IS NOT NULL, d.latest_source_revision_id,
       d.current_source_revision_id, d.current_adopted_version, l.files, c.files,
       EXISTS (SELECT 1 FROM request r WHERE r.document_uid = d.document_uid
               AND r.kind = 'process' AND r.state IN ('queued', 'processing'))
FROM document d
JOIN source_revision l ON l.source_revision_id = d.latest_source_revision_id
LEFT JOIN source_revision c ON c.source_revision_id = d.current_source_revision_id
WHERE d.document_uid = %s
"""

_REQUESTS = """
SELECT r.state, r.error, r.terminal_at,
       EXISTS (SELECT 1 FROM canonical_revision c WHERE c.request_id = r.request_id)
FROM request r
WHERE r.source_revision_id = %s AND r.kind = 'process' AND r.adoption_sequence = %s
ORDER BY r.created_at DESC, r.request_id DESC
"""

_CANDIDATES = """
SELECT d.document_uid FROM document d
WHERE d.deleted_at IS NULL AND d.latest_source_revision_id IS NOT NULL AND d.document_uid > %s
  AND NOT EXISTS (SELECT 1 FROM request r WHERE r.document_uid = d.document_uid
                  AND r.kind = 'process' AND r.state IN ('queued', 'processing'))
ORDER BY d.document_uid LIMIT %s
"""

_WAITING = """
SELECT count(*) FROM request r JOIN outbox o USING (request_id)
WHERE r.initiator <> 'source' AND r.state = 'queued' AND o.dispatched_at IS NULL
"""

log = logging.getLogger(__name__)


async def run(conn: AsyncConnection, now: datetime, pace: int = PACE) -> Counter[str]:
    """One run of the scan on an autocommit connection, each Document read on its own and each
    request opened in a transaction that locks its Document first. It opens reruns, then redos,
    then refreshes, while fewer than `pace` requests it made wait for dispatch. Records its
    gauges and returns how many requests it opened of each kind: rerun, redo, refresh."""
    plans: list[tuple[int, str]] = []
    stopped: Counter[str] = Counter()
    retrying: Counter[str] = Counter()
    after = ""
    while uids := [u for (u,) in await (await conn.execute(_CANDIDATES, (after, PAGE))).fetchall()]:
        after = uids[-1]
        for uid in uids:
            plan, limit = await _decide(conn, uid, now)
            if plan:
                plans.append((plan.rank, uid))
            if limit and limit.stopped:
                stopped[limit.stopped] += 1
            if limit and limit.retrying:
                retrying[limit.retrying] += 1
    [(waiting,)] = await (await conn.execute(_WAITING)).fetchall()
    opened: Counter[str] = Counter()
    trace_id = uuid.uuid4().hex
    for _, uid in sorted(plans):
        if waiting >= pace:
            break
        if kind := await _open(conn, uid, now, trace_id):
            opened[kind] += 1
            waiting += 1
    await _record(conn, stopped, retrying)
    log.info(
        "scan run",
        extra={"correlation": {"trace_id": trace_id, "planned": len(plans), **opened,
                               "stopped": sum(stopped.values()),
                               "retrying": sum(retrying.values())}},
    )  # fmt: skip
    return opened


async def _open(conn: AsyncConnection, uid: str, now: datetime, trace_id: str) -> str | None:
    async with conn.transaction():
        # A statement of its own: one that waits for the lock reads rows as they were at its start.
        await conn.execute("SELECT 1 FROM document WHERE document_uid = %s FOR UPDATE", (uid,))
        plan, _ = await _decide(conn, uid, now)
        if plan is None:
            return None
        request_id, created = await create_process_request(
            conn,
            tenant_id=plan.tenant_id,
            document_uid=uid,
            source_revision_id=plan.source_revision_id,
            initiator=plan.initiator,
            priority="normal" if plan.rank == 0 else "low",
            adopted_version=plan.adopted[0],
            adoption_sequence=plan.adopted[1],
            trace_id=trace_id,
        )
    if not created:
        return None
    kind = ("rerun", "redo", "refresh")[plan.rank]
    log.info(
        "scan opened a request",
        extra={"correlation": {"trace_id": trace_id, "request_id": request_id,
                               "document_uid": uid, "kind": kind,
                               "adopted_version": plan.adopted[0]}},
    )  # fmt: skip
    return kind


async def _decide(
    conn: AsyncConnection, uid: str, now: datetime
) -> tuple[Plan | None, Limit | None]:
    """The request the rules open for the Document now, and the limit of its latest Source
    Revision when a rule read it."""
    row = await (await conn.execute(_DOCUMENT, (uid,))).fetchone()
    if row is None:
        return None, None
    tenant_id, deleted, latest, current, made_by, latest_files, current_files, active = row
    if deleted or active:
        return None, None
    media_type = _media_type(latest_files)
    adopted = await adoption.current(conn, media_type)
    withdrawn = await adoption.withdrawn(conn, media_type)
    # A withdrawn version is not adopted again (#261); if it were, every run would open and end.
    if adopted is None or adopted[0] in withdrawn:
        return None, None
    redo = made_by is not None and (
        made_by in withdrawn or _in_scope(made_by, await adoption.refresh_scope(conn, media_type))
    )
    rank = 1 if made_by in withdrawn else 2

    def plan(srv: str, initiator: Initiator, rank: int) -> Plan:
        return Plan(tenant_id, srv, initiator, rank, adopted)

    if current == latest:
        if made_by == adopted[0]:
            return None, None  # rule 1
        limit = await _limit(conn, latest, adopted[1], now) if redo else None
        return (plan(latest, "platform", rank) if limit and limit.open else None), limit  # rule 2
    limit = await _limit(conn, latest, adopted[1], now)
    if limit.open:
        return plan(latest, "operator", 0), limit  # rule 3
    if (
        current
        and redo
        and _media_type(current_files) == media_type
        and (await _limit(conn, current, adopted[1], now)).open
    ):
        return plan(current, "platform", rank), limit  # rule 4
    return None, limit  # rule 5


async def _limit(conn: AsyncConnection, srv: str, adoption_sequence: int, now: datetime) -> Limit:
    rows = await (await conn.execute(_REQUESTS, (srv, adoption_sequence))).fetchall()
    if not rows:
        return Limit(True)
    state, error, terminal_at, accepted = rows[0]
    if state in ("queued", "processing"):
        return Limit(False)
    if state == "succeeded":
        return Limit(False, stopped=None if accepted else "NO_CANDIDATE")
    error = error or {}
    reason = error.get("reason") or "UNKNOWN"
    if _withdrawn(error):
        return Limit(True)
    if (error.get("metadata") or {}).get("cause") == "source" or error.get("retryable") is False:
        return Limit(False, stopped=reason)
    failures = 0
    for s, e, _, _ in rows:  # the retryable failures in a row, the last one first
        if s != "failed" or (e or {}).get("retryable") is False or _withdrawn(e or {}):
            break
        failures += 1
    wait = min(RETRY_FIRST * 2 ** min(failures - 1, 10), RETRY_CAP)  # 2^10 is past the cap
    due = terminal_at is None or now >= terminal_at + wait
    return Limit(due, retrying=reason if failures >= WARN_AFTER else None)


def _withdrawn(error: dict[str, Any]) -> bool:
    return (error.get("domain"), error.get("reason")) == (ERROR_DOMAIN, "VERSION_WITHDRAWN")


def _in_scope(version: str, scope: Any) -> bool:
    if scope == "all":
        return True
    return isinstance(scope, dict) and version in scope.get("made_by", [])


def _media_type(files: list[dict[str, Any]]) -> str:
    return next(f["media_type"] for f in files if f["role"] == "main")


_ON_WITHDRAWN = """
SELECT d.current_adopted_version, count(*) FROM document d
WHERE d.deleted_at IS NULL
  AND d.current_adopted_version IN (SELECT version FROM withdrawn_version)
GROUP BY 1
"""

_WITHOUT_CURRENT = """
SELECT source_id, count(*) FROM document
WHERE deleted_at IS NULL AND current_canonical_revision_id IS NULL AND created_at < now() - %s
GROUP BY 1
"""

_OVERDUE = """
SELECT r.adopted_version, count(*) FROM request r JOIN outbox o USING (request_id)
WHERE r.kind = 'process' AND r.state IN ('queued', 'processing')
  AND o.dispatched_at < now() - %s
GROUP BY 1
"""


async def _record(conn: AsyncConnection, stopped: Counter[str], retrying: Counter[str]) -> None:
    async def by_label(query: str, *params: Any) -> dict[str, float]:
        rows = await (await conn.execute(query, params)).fetchall()  # type: ignore[arg-type]
        return {label: float(n) for label, n in rows}

    await gauges.record(
        conn,
        "scan",
        {
            "kp_admission_documents_on_withdrawn": await by_label(_ON_WITHDRAWN),
            "kp_admission_documents_without_current": await by_label(_WITHOUT_CURRENT, OVERDUE),
            "kp_admission_requests_overdue": await by_label(_OVERDUE, OVERDUE),
            "kp_admission_reruns_retrying": {r: float(n) for r, n in retrying.items()},
            "kp_admission_reruns_stopped": {r: float(n) for r, n in stopped.items()},
        },
    )
