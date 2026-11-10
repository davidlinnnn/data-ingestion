"""Records and Temporal checks shared by the admission tests and the crash harness."""

import asyncio
import uuid
from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from temporalio.client import Client

from kp_admission.requests import create_process_request

FILES = [
    {
        "path": "paper.pdf",
        "role": "main",
        "custody_ref": "custody://kp-dev/sources/s1/paper.pdf",
        "sha256": "a" * 64,
        "size": 18342,
        "media_type": "application/pdf",
    }
]


def queue(adopted_version: str) -> str:
    """A task queue per Processing Profile version; the real format is #135's."""
    return f"test-{adopted_version.replace('@', '-')}"


async def revision(conn: AsyncConnection, source_id: str = "s1") -> tuple[str, str]:
    """A new document with one Source Revision: (document_uid, source_revision_id)."""
    uid, srv = f"doc_{uuid.uuid4().hex[:12]}", f"srv_{uuid.uuid4().hex[:12]}"
    await conn.execute(
        "INSERT INTO document (document_uid, tenant_id, source_id, document_id, resource_id)"
        " VALUES (%s, 't1', %s, %s, 'res_1')",
        (uid, source_id, f"papers/{uid}"),
    )
    await conn.execute(
        "INSERT INTO source_revision (source_revision_id, tenant_id, document_uid,"
        " source_version, files) VALUES (%s, 't1', %s, '1', %s)",
        (srv, uid, Jsonb(FILES)),
    )
    return uid, srv


async def request(conn: AsyncConnection, uid: str, srv: str, **fields: Any) -> tuple[str, bool]:
    defaults: dict[str, Any] = {
        "tenant_id": "t1",
        "initiator": "source",
        "priority": "normal",
        "adopted_version": "paper-pdf@1",
        "adoption_sequence": 7,
        "trace_id": "4bf92f3577b34da6",
    }
    return await create_process_request(
        conn, document_uid=uid, source_revision_id=srv, **(defaults | fields)
    )


async def runs(client: Client, request_id: str) -> int:
    """Workflow executions, open or closed, with workflow ID request_id, once visibility lists
    any (it trails the start by a moment); 0 when none appears within 5 seconds."""
    for _ in range(50):
        if count := (await client.count_workflows(f"WorkflowId = '{request_id}'")).count:
            return count
        await asyncio.sleep(0.1)
    return 0
