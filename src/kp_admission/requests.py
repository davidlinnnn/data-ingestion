"""Process requests and their outbox rows (admission spec §3, §9)."""

import uuid
from typing import Literal

from psycopg import AsyncConnection

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
