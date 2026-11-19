"""Process requests, their outbox rows and their outcomes (admission spec §3, §9)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

_INSERT = """
INSERT INTO request (request_id, tenant_id, kind, document_uid, source_revision_id, state,
                     initiator, retry_of, batch_id, priority, adopted_version, adoption_sequence,
                     trace_id)
VALUES (%(request_id)s, %(tenant_id)s, 'process', %(document_uid)s, %(source_revision_id)s,
        'queued', %(initiator)s, %(retry_of)s, %(batch_id)s, %(priority)s, %(adopted_version)s,
        %(adoption_sequence)s, %(trace_id)s)
ON CONFLICT (document_uid, source_revision_id)
    WHERE kind = 'process' AND state IN ('queued', 'processing') DO NOTHING
RETURNING request_id
"""

_ACTIVE = """
SELECT request_id FROM request
WHERE document_uid = %(document_uid)s AND source_revision_id = %(source_revision_id)s
  AND kind = 'process' AND state IN ('queued', 'processing')
"""


async def create_process_request(
    conn: AsyncConnection,
    *,
    tenant_id: str,
    document_uid: str,
    source_revision_id: str,
    initiator: Literal["source", "operator", "platform"],
    priority: Literal["normal", "low"],
    adopted_version: str,
    adoption_sequence: int,
    trace_id: str,
    batch_id: str | None = None,
    retry_of: str | None = None,
) -> tuple[str, bool]:
    """Creates a queued process request and its outbox row in one transaction, or in a savepoint
    when the caller has one open, and returns (request_id, True). When the Source Revision already
    has a queued or processing request, it creates nothing and returns (that request_id, False)."""
    params = {
        "tenant_id": tenant_id,
        "document_uid": document_uid,
        "source_revision_id": source_revision_id,
        "initiator": initiator,
        "priority": priority,
        "adopted_version": adopted_version,
        "adoption_sequence": adoption_sequence,
        "trace_id": trace_id,
        "batch_id": batch_id,
        "retry_of": retry_of,
    }
    async with conn.transaction():
        while True:
            params["request_id"] = f"req_{uuid.uuid4().hex}"
            if await (await conn.execute(_INSERT, params)).fetchone():
                await conn.execute(
                    "INSERT INTO outbox (request_id, tenant_id) VALUES (%s, %s)",
                    (params["request_id"], tenant_id),
                )
                return params["request_id"], True
            if active := await (await conn.execute(_ACTIVE, params)).fetchone():
                return active[0], False
            # The active request ended between the two statements: insert again.


_END = """
UPDATE request SET state = %s, terminal_at = %s, error = %s, updated_at = now()
WHERE request_id = %s AND kind = 'process' AND state IN ('queued', 'processing')
RETURNING initiator, source_revision_id
"""

# An accepted revision stays accepted: a later run that fails does not undo the acceptance.
_OUTCOME = """
UPDATE source_revision SET outcome = %s WHERE source_revision_id = %s AND outcome <> 'accepted'
"""


async def record_outcome(
    conn: AsyncConnection,
    request_id: str,
    state: Literal["succeeded", "failed"],
    error: dict[str, Any] | None,
    terminal_at: datetime | None,
) -> bool:
    """Ends a queued or processing process request with `state` and `error`, the status report's or
    the workflow's error block, in one transaction, and returns whether it did; an ended request
    keeps its outcome. Unless the request is a platform refresh (§3), its Source Revision's outcome
    follows: succeeded makes it pending, which #251 turns into accepted; failed with
    error.metadata.cause "source" makes it rejected, any other failure failed. An accepted
    revision keeps its outcome."""
    async with conn.transaction():
        ended = await (
            await conn.execute(_END, (state, terminal_at, error and Jsonb(error), request_id))
        ).fetchone()
        if ended is None:
            return False
        initiator, source_revision_id = ended
        if initiator != "platform":
            await conn.execute(_OUTCOME, (revision_outcome(state, error), source_revision_id))
    return True


def revision_outcome(state: str, error: dict[str, Any] | None) -> str:
    if state == "succeeded":
        return "pending"
    cause = ((error or {}).get("metadata") or {}).get("cause")
    return "rejected" if cause == "source" else "failed"
