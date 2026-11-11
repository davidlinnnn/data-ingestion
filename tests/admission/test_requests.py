"""Admission records and process requests on PostgreSQL (#95, admission spec §3, §9)."""

import asyncio
from collections.abc import Awaitable, Callable

import psycopg
import pytest
from psycopg import AsyncConnection
from temporalio.service import RPCError, RPCStatusCode

from tests.admission.support import request, revision

pytestmark = pytest.mark.docker


async def test_a_committed_request_is_visible_to_another_connection_before_any_workflow(
    conn, dsn, temporal
):
    uid, srv = await revision(conn)
    request_id, created = await request(conn, uid, srv)

    async with await psycopg.AsyncConnection.connect(dsn) as other:  # another API instance
        cursor = await other.execute(
            "SELECT r.state, o.dispatched_at FROM request r JOIN outbox o USING (request_id)"
            " WHERE request_id = %s",
            (request_id,),
        )
        assert created
        assert await cursor.fetchall() == [("queued", None)]
    with pytest.raises(RPCError) as missing:
        await temporal.get_workflow_handle(request_id).describe()
    assert missing.value.status == RPCStatusCode.NOT_FOUND


async def race[T](
    dsn: str, callers: int, attempt: Callable[[AsyncConnection], Awaitable[T]]
) -> list[T]:
    """Runs attempt in `callers` transactions that all start it at once and commit after it."""
    barrier = asyncio.Barrier(callers)

    async def caller() -> T:
        async with await psycopg.AsyncConnection.connect(dsn) as own, own.transaction():
            await barrier.wait()
            return await attempt(own)

    return await asyncio.gather(*(caller() for _ in range(callers)))


async def test_concurrent_requests_for_one_source_revision_create_one_active_request(conn, dsn):
    uid, srv = await revision(conn)

    results = await race(dsn, 8, lambda own: request(own, uid, srv))

    assert sorted(created for _, created in results) == [False] * 7 + [True]
    assert len({request_id for request_id, _ in results}) == 1
    cursor = await conn.execute(
        "SELECT count(*), count(o.request_id) FROM request r LEFT JOIN outbox o USING (request_id)"
        " WHERE r.source_revision_id = %s",
        (srv,),
    )
    assert await cursor.fetchone() == (1, 1)


async def test_without_the_index_the_same_race_creates_a_request_per_caller(conn, dsn):
    """Negative control: when checks overlap uncommitted inserts, as in the race above, only the
    index keeps it to one request."""
    uid, srv = await revision(conn)
    await conn.execute("DROP INDEX request_one_active")
    checked = asyncio.Barrier(8)

    async def check_then_insert(own: AsyncConnection) -> None:
        await own.execute(
            "INSERT INTO request (request_id, tenant_id, kind, document_uid, source_revision_id,"
            " state, initiator, priority, adopted_version, adoption_sequence, trace_id)"
            " SELECT gen_random_uuid(), 't1', 'process', %(uid)s, %(srv)s, 'queued', 'source',"
            " 'normal', 'paper-pdf@1', 7, 't' WHERE NOT EXISTS (SELECT 1 FROM request"
            " WHERE document_uid = %(uid)s AND source_revision_id = %(srv)s)",
            {"uid": uid, "srv": srv},
        )
        await checked.wait()  # no caller commits before every caller has checked

    await race(dsn, 8, check_then_insert)

    cursor = await conn.execute(
        "SELECT count(*) FROM request WHERE source_revision_id = %s", (srv,)
    )
    assert await cursor.fetchone() == (8,)


async def test_a_source_revision_gets_a_new_request_once_its_active_one_ends(conn):
    uid, srv = await revision(conn)
    failed, _ = await request(conn, uid, srv)
    await conn.execute("UPDATE request SET state = 'failed' WHERE request_id = %s", (failed,))

    retry, created = await request(conn, uid, srv, retry_of=failed)

    assert created
    assert retry != failed
    assert await request(conn, uid, srv) == (retry, False)


async def test_every_admission_record_carries_a_tenant(conn):
    cursor = await conn.execute(
        "SELECT t.table_name, c.is_nullable FROM information_schema.tables t"
        " LEFT JOIN information_schema.columns c ON c.table_name = t.table_name"
        " AND c.column_name = 'tenant_id' WHERE t.table_schema = 'public'"
    )

    assert dict(await cursor.fetchall()) == dict.fromkeys(
        ["batch", "batch_item", "document", "source_revision", "request", "outbox",
         "idempotency_key"], "NO",
    )  # fmt: skip


async def test_a_document_id_is_unique_among_the_live_documents_of_a_source(conn):
    insert = (
        "INSERT INTO document (document_uid, tenant_id, source_id, document_id, resource_id)"
        " VALUES (%s, 't1', %s, 'hr/leave-policy', 'res_1')"
    )
    await conn.execute(insert, ("doc_1", "s1"))
    await conn.execute(insert, ("doc_2", "s2"))  # another Source

    with pytest.raises(psycopg.errors.UniqueViolation):
        await conn.execute(insert, ("doc_3", "s1"))
    await conn.execute("UPDATE document SET deleted_at = now() WHERE document_uid = 'doc_1'")
    await conn.execute(insert, ("doc_3", "s1"))  # a new generation after deletion
