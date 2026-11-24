"""Source Deletion (admission spec §5.8, §8): the DELETE call applies the deletion in the
transaction that records it, and the enforce CronJob judges it enforced (C3 of the canonical
consumption DR)."""

import logging
import uuid
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from kp_admission import feed, gauges, serving
from kp_admission.reports import Pipeline

ERROR_DOMAIN = "admission.knowledge-platform"
TARGET = timedelta(minutes=10)  # spec §11's enforced target; #56 sets the cleanup time limit

# A queued request ended by the deletion: the Source's own act, so its message is shown.
DOCUMENT_DELETED = {
    "domain": ERROR_DOMAIN,
    "reason": "DOCUMENT_DELETED",
    "message": "The document was deleted before its processing started.",
    "retryable": False,
    "metadata": {"cause": "source"},
}

_LIVE = "tenant_id = %s AND source_id = %s AND document_id = %s AND deleted_at IS NULL"

_INSERT = """
INSERT INTO request (request_id, tenant_id, kind, document_uid, state, initiator, priority,
                     trace_id)
VALUES (%s, %s, 'delete', %s, 'applied', 'source', 'normal', %s)
"""

_APPLY = """
UPDATE document SET deleted_at = now(), delete_request_id = %s, title = NULL, source_url = NULL,
                    metadata = NULL, readiness = 'deleted', readiness_since = now()
WHERE document_uid = %s
RETURNING tenant_id, source_id
"""

# A row a dispatcher holds is being started: it runs on, and Canonical Acceptance discards its
# result (§8). Skipping it, not waiting, keeps the dispatcher's lock order from deadlocking.
_UNSTARTED = """
DELETE FROM outbox WHERE request_id IN (
    SELECT o.request_id FROM outbox o JOIN request r USING (request_id)
    WHERE r.document_uid = %s AND r.state = 'queued' AND o.dispatched_at IS NULL
    FOR UPDATE OF o SKIP LOCKED)
RETURNING request_id
"""

_END = """
UPDATE request SET state = 'failed', error = %s, terminal_at = now(), updated_at = now()
WHERE request_id = ANY(%s)
"""

# The generation deleted last, while it is visible (§8: 30 days after applied).
_DELETED = """
SELECT r.request_id, r.state FROM document d JOIN request r ON r.request_id = d.delete_request_id
WHERE d.tenant_id = %s AND d.source_id = %s AND d.document_id = %s
  AND d.deleted_at > now() - interval '30 days'
ORDER BY d.deleted_at DESC LIMIT 1
"""

log = logging.getLogger(__name__)


async def delete(
    conn: AsyncConnection, *, tenant_id: str, source_id: str, document_id: str, trace_id: str
) -> dict[str, Any] | None:
    """Source Deletion of the Source's Document `document_id` (§5.8): in one transaction a delete
    request is recorded `applied`, the Document reads `deleted` with its catalog fields cleared,
    a document_deleted event is appended, and its process requests not yet dispatched end
    `failed` with DOCUMENT_DELETED. Without a current generation it returns the delete request of
    the one deleted last, for 30 days, as a repeated call does; None when there is neither."""
    params = (tenant_id, source_id, document_id)
    async with conn.transaction():
        # A statement of its own: one that waits for the lock reads rows as they were at its start.
        await conn.execute(f"SELECT 1 FROM document WHERE {_LIVE} FOR UPDATE", params)  # type: ignore[arg-type]
        cursor = await conn.execute(f"SELECT document_uid FROM document WHERE {_LIVE}", params)  # type: ignore[arg-type]
        if (live := await cursor.fetchone()) is None:
            row = await (await conn.execute(_DELETED, params)).fetchone()
            return None if row is None else _view(*row)
        uid, request_id = live[0], f"req_{uuid.uuid4().hex}"
        await conn.execute(_INSERT, (request_id, tenant_id, uid, trace_id))
        await conn.execute(_APPLY, (request_id, uid))
        ended = [r for (r,) in await (await conn.execute(_UNSTARTED, (uid,))).fetchall()]
        if ended:
            await conn.execute(_END, (Jsonb(DOCUMENT_DELETED), ended))
        await feed.append(
            conn,
            "document_deleted",
            tenant_id=tenant_id,
            source_id=source_id,
            document_uid=uid,
            priority="narrowing",
        )
    log.info(
        "deletion applied",
        extra={"correlation": {"request_id": request_id, "document_uid": uid,
                               "requests_ended": len(ended)}},
    )  # fmt: skip
    return _view(request_id, "applied")


def _view(request_id: str, state: str) -> dict[str, Any]:
    return {"request_id": request_id, "kind": "delete", "state": state}


async def enforce(
    conn: AsyncConnection, pipelines: Mapping[str, Pipeline], now: datetime
) -> Counter[str]:
    """One run of the enforcement judgment, on an autocommit connection: each applied deletion
    becomes `enforced` once no Build that is not retired holds an included or pending fact of its
    Document (C3). It judges none while a Build lacks liveness (R-c), while a Build has not
    repaired the last loss of committed writes, or within the longest projection update interval
    after its declaration (K2). `pipelines` are the registered ones by track. Records the
    kp_admission_deletions_unenforced gauge and returns how many deletions went each way:
    enforced, held, or suspended with its reason."""
    judged: Counter[str] = Counter()
    suspended = await _suspended(conn, pipelines, now)
    cursor = await conn.execute(
        "SELECT r.request_id, r.document_uid, d.deleted_at FROM request r"
        " JOIN document d ON d.document_uid = r.document_uid"
        " WHERE r.kind = 'delete' AND r.state = 'applied' ORDER BY d.deleted_at"
    )
    overdue: Counter[str] = Counter()
    for request_id, uid, applied_at in await cursor.fetchall():
        if suspended:
            judged[f"suspended_{suspended}"] += 1
            reason = suspended
        else:
            # The Document lock first, as registration takes it (#252): a registration either
            # committed its pending fact before this read, or it meets the deletion and is refused.
            async with conn.transaction():
                await conn.execute(
                    "SELECT 1 FROM document WHERE document_uid = %s FOR UPDATE", (uid,)
                )
                if await serving.held(conn, uid):
                    reason = "held"
                else:
                    await conn.execute(
                        "UPDATE request SET state = 'enforced', terminal_at = now(),"
                        " updated_at = now() WHERE request_id = %s AND state = 'applied'",
                        (request_id,),
                    )
                    reason = "enforced"
            judged[reason] += 1
            if reason == "enforced":
                log.info(
                    "deletion enforced",
                    extra={"correlation": {"request_id": request_id, "document_uid": uid}},
                )
                continue
        if now - applied_at > TARGET:
            overdue[reason] += 1
    await gauges.record(
        conn,
        "enforce",
        {"kp_admission_deletions_unenforced": {r: float(overdue[r]) for r in REASONS}},
    )
    if suspended:
        log.warning("enforcement judgment suspended: %s", suspended)
    return judged


REASONS = ("held", "liveness", "writes_lost")


async def _suspended(
    conn: AsyncConnection, pipelines: Mapping[str, Pipeline], now: datetime
) -> str | None:
    if await serving.silent(conn, pipelines, now):
        return "liveness"
    if await serving.writes_unrepaired(conn):
        return "writes_lost"
    declared = await serving.writes_lost_at(conn)
    intervals = [p.update_interval_s for track, p in pipelines.items() if track != "canonical"]
    # A Build the restore erased reports again within its own interval, starting unrepaired.
    if declared and now < declared + timedelta(seconds=max(intervals, default=0)):
        return "writes_lost"
    return None
