"""The allow-all provider on PostgreSQL (#113, authorization design §4, top note)."""

import asyncio
import contextlib
import time
from datetime import UTC, datetime
from typing import Any

import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg_pool import AsyncConnectionPool

from kp_admission.authz import TIMEOUT_S, AllowAll, Ref

pytestmark = pytest.mark.docker

ALICE = Ref(type="user", id="alice")


@pytest.fixture
async def pool(dsn):
    async with AsyncConnectionPool(dsn, kwargs={"autocommit": True}, open=False) as pool:
        yield pool


async def resource(conn, resource_id: str = "res_01") -> str:
    await conn.execute(
        "INSERT INTO authz.resource (resource_id, tenant_id, name, created_by_source)"
        " VALUES (%s, 't1', 'rd / nlp', 'rd_papers')",
        (resource_id,),
    )
    return resource_id


@pytest.mark.parametrize("action", ["read", "place", "manage"])
async def test_every_action_on_an_existing_resource_is_allowed(conn, pool, action):
    res = await resource(conn)
    before = datetime.now(UTC)

    decision = await AllowAll(pool).check(ALICE, action, res, trace_id="4bf92f3577b34da6")

    assert decision.outcome == "allow"
    assert decision.reason is None
    assert before <= decision.evaluated_at <= datetime.now(UTC)
    assert decision.valid_until == decision.evaluated_at  # no reuse (§8)
    assert (decision.subject, decision.action, decision.resource) == (
        ALICE,
        action,
        Ref(type="resource", id=res),
    )
    assert decision.decided_by == "allow-all/model-1"
    assert decision.trace_id == "4bf92f3577b34da6"


async def test_an_unknown_resource_is_denied_as_not_found(conn, pool):
    await resource(conn, "res_01")

    decision = await AllowAll(pool).check(ALICE, "read", "res_02", trace_id="t")

    assert (decision.outcome, decision.reason) == ("deny", "resource_not_found")


async def test_list_resources_returns_every_resource_in_pages_of_1000(conn, pool):
    await conn.execute(
        "INSERT INTO authz.resource (resource_id, tenant_id, name, created_by_source)"
        " SELECT 'res_' || lpad(i::text, 4, '0'), 't1', 'r', 'rd_papers'"
        " FROM generate_series(1, 2001) AS i"
    )
    provider, pages, cursor = AllowAll(pool), [], None
    while True:
        page = await provider.list_resources(ALICE, "read", cursor=cursor, trace_id="t")
        assert (page.outcome, page.resource) == ("allow", None)
        pages.append(page.resource_ids)
        if not (cursor := page.next_cursor):
            break

    assert [len(ids) for ids in pages] == [1000, 1000, 1]
    assert sum(pages, []) == [f"res_{i:04}" for i in range(1, 2002)]


async def test_list_resources_without_resources_is_an_empty_allow(pool):
    page = await AllowAll(pool).list_resources(ALICE, "read", trace_id="t")

    assert (page.outcome, page.resource_ids, page.next_cursor) == ("allow", [], None)


async def test_a_database_that_refuses_connections_is_unavailable_within_the_timeout():
    async with AsyncConnectionPool("host=127.0.0.1 port=9", open=False) as pool:
        start = time.monotonic()

        decision = await AllowAll(pool).check(ALICE, "read", "res_01", trace_id="t")

        assert 0 <= time.monotonic() - start <= TIMEOUT_S + 0.25
    assert (decision.outcome, decision.reason) == ("unavailable", None)


@contextlib.asynccontextmanager
async def freezable(dsn: str):
    """A TCP proxy to the database, and an event that makes it stop forwarding: the server
    seems to stop answering mid-query, and a cancel request never arrives either."""
    upstream: dict[str, Any] = conninfo_to_dict(dsn)
    frozen, writers = asyncio.Event(), []

    async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        with contextlib.suppress(ConnectionError):
            while (data := await reader.read(65536)) and not frozen.is_set():
                writer.write(data)
                await writer.drain()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        up_reader, up_writer = await asyncio.open_connection(upstream["host"], upstream["port"])
        writers.extend([writer, up_writer])
        await asyncio.gather(pipe(reader, up_writer), pipe(up_reader, writer))

    server = await asyncio.start_server(serve, "127.0.0.1", 0)
    try:
        yield make_conninfo(dsn, host="127.0.0.1", port=server.sockets[0].getsockname()[1]), frozen
    finally:
        for writer in writers:
            writer.transport.abort()
        server.close()


@pytest.mark.network
async def test_a_database_that_stops_answering_mid_query_is_unavailable_within_the_timeout(
    conn, dsn
):
    res = await resource(conn)
    async with freezable(dsn) as (url, frozen):
        async with AsyncConnectionPool(url, kwargs={"autocommit": True}, open=False) as pool:
            provider = AllowAll(pool)
            assert (await provider.check(ALICE, "read", res, trace_id="t")).outcome == "allow"
            frozen.set()
            start = time.monotonic()

            decision = await provider.check(ALICE, "read", res, trace_id="t")

            assert 0 <= time.monotonic() - start <= TIMEOUT_S + 0.25
            assert decision.outcome == "unavailable"


async def test_list_resources_on_a_database_that_refuses_connections_is_unavailable():
    async with AsyncConnectionPool("host=127.0.0.1 port=9", open=False) as pool:
        page = await AllowAll(pool).list_resources(ALICE, "read", trace_id="t")

    assert (page.outcome, page.resource_ids, page.next_cursor) == ("unavailable", None, None)
