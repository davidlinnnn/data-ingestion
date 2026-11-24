"""The reference projection's query endpoint (#279) end to end: the real api with its authz API
over a paging fake (#204), the reader of #127 filling the projection's store, and the query app
over HTTP. Each test drives the reader step by step, then searches as a user."""

import json
import logging

import httpx
import pytest
from prometheus_client import generate_latest

from kp_admission import deletion, feed, status
from kp_admission.api import app
from kp_reference_projection import cli, query
from kp_sdk.projection import ProjectionClient
from tests.admission.authz_fake import FakeAuthorizer
from tests.admission.support import INTAKE
from tests.admission.test_reference_projection import (  # noqa: F401 (fixtures)
    PIPELINES,
    Platform,
    no_wait,
    pool,
    projection,
    settle,
    store,
)
from tests.admission.test_serving import accepted, profile, revised
from tests.admission.test_status import credential, digest, document

pytestmark = pytest.mark.docker

USERS = {digest("alice-token"): "alice"}


@pytest.fixture
def authorizer() -> FakeAuthorizer:
    return FakeAuthorizer(resource_ids=("s1/hr-all",))


@pytest.fixture
def platform(pool, authorizer) -> Platform:  # noqa: F811
    return Platform(
        app(
            authorizer,
            {digest("retrieval"): "retrieval"},
            {digest("s1"): credential("s1")},
            pool,
            INTAKE,
            pipelines={digest("retrieval"): PIPELINES["retrieval"]},
        )
    )


@pytest.fixture
async def reader(conn, platform, store):  # noqa: F811
    await profile(conn, "retrieval")
    started = projection(platform, store)
    await started.start()
    await settle(started)
    return started


@pytest.fixture
async def client(platform, store):  # noqa: F811
    sdk = ProjectionClient(
        "http://api", "retrieval", "retrieval", transport=platform, sleep=no_wait
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(query.app(sdk, store, USERS)), base_url="http://query"
    ) as http:
        yield http
    await sdk.aclose()


async def search(client: httpx.AsyncClient, text: str, **fields) -> httpx.Response:
    return await client.post(
        "/v1/entries:search",
        json={"query": text} | fields,
        headers={"authorization": "Bearer alice-token"},
    )


async def found(client: httpx.AsyncClient, text: str, **fields) -> list[str]:
    response = await search(client, text, **fields)
    assert response.status_code == 200, response.text
    return [hit["document_uid"] for hit in response.json()["results"]]


async def written(conn, platform, reader, document_id: str, key: str, blocks: list[str]) -> str:
    uid, srv = await document(conn, document_id, key=key)
    crv = f"crv_{document_id.lower()}1"
    platform.contents[crv] = blocks
    await accepted(conn, uid, srv, crv)
    await settle(reader)
    return uid


async def test_only_a_user_who_may_list_the_resource_finds_its_document(
    conn, platform, reader, client, authorizer
):
    uid = await written(conn, platform, reader, "A", "hr-all", ["# Travel", "Rules for trips."])

    allowed = await found(client, "trips")
    authorizer.resource_ids = ("s1/legal",)

    assert (allowed, await found(client, "trips")) == ([uid], [])


async def delete(conn, document_id: str = "A") -> None:
    await deletion.delete(
        conn, tenant_id="t1", source_id="s1", document_id=document_id, trace_id="t"
    )


async def rebind(conn, uid: str, resource_id: str) -> None:
    """As the rebind of #205 will record it."""
    async with conn.transaction():
        await conn.execute(
            "UPDATE document SET resource_id = %s WHERE document_uid = %s", (resource_id, uid)
        )
        await feed.append(conn, "inclusion_changed", tenant_id="t1", source_id="s1",
                          document_uid=uid, priority="narrowing")  # fmt: skip
    await status.refresh(conn, [uid])


async def two_documents(conn, platform, reader) -> tuple[str, str]:
    a = await written(conn, platform, reader, "A", "hr-all", ["Rules for trips."])
    b = await written(conn, platform, reader, "B", "legal", ["Contracts for trips."])
    return a, b


async def test_every_page_of_the_list_is_read_including_after_an_empty_page(
    conn, platform, reader, client, authorizer
):
    a, b = await two_documents(conn, platform, reader)
    authorizer.resource_ids, authorizer.page_size = ("s1/hr-all", "s1/legal"), 1
    paged = await found(client, "trips")  # B's Resource is on the second page
    authorizer.pages = ((), ("s1/legal",))
    after_empty = await found(client, "trips")  # B's Resource follows an empty page

    assert (sorted(paged), after_empty) == (sorted([a, b]), [b])
    first_pages = [r for r in platform.sent if r.url.path.endswith("/list_resources")
                   and b"cursor" not in r.content]  # fmt: skip
    assert len(first_pages) == 2  # one listing per query: nothing reused


async def refuse_authz(request: httpx.Request) -> httpx.Response | None:
    if request.url.path.startswith("/authz/"):
        error = {"code": 503, "status": "UNAVAILABLE", "message": "No decision could be made.",
                 "details": [{"reason": "UNAVAILABLE"}]}  # fmt: skip
        return httpx.Response(503, json={"error": error})
    return None


async def unreachable_authz(request: httpx.Request) -> httpx.Response | None:
    if request.url.path.startswith("/authz/"):
        raise httpx.ConnectError("refused")
    return None


@pytest.mark.parametrize("failure", [refuse_authz, unreachable_authz])
async def test_no_decision_gives_no_content(conn, platform, reader, client, failure):
    await written(conn, platform, reader, "A", "hr-all", ["Rules for trips."])

    platform.hooks.append(failure)
    response = await search(client, "trips")

    assert response.status_code == 503
    assert "results" not in response.json()
    assert sum(r.url.path.startswith("/authz/") for r in platform.sent) == 2  # retried once


async def test_a_failed_page_reads_again_from_the_first_page(
    conn, platform, reader, client, authorizer
):
    a, b = await two_documents(conn, platform, reader)
    authorizer.resource_ids, authorizer.page_size = ("s1/hr-all", "s1/legal"), 1
    failed: list[bytes] = []

    async def fail_page_two_once(request: httpx.Request) -> httpx.Response | None:
        if b"cursor" in request.content and not failed:
            failed.append(request.content)
            return httpx.Response(500)
        return None

    platform.hooks.append(fail_page_two_once)
    hits = await found(client, "trips")

    listed = [r.content for r in platform.sent if r.url.path.endswith("/list_resources")]
    assert sorted(hits) == sorted([a, b])
    assert [b"cursor" in body for body in listed] == [False, True, False, True]


async def test_a_caller_without_a_registered_token_is_refused(reader, client):
    response = await client.post("/v1/entries:search", json={"query": "trips"},
                                 headers={"authorization": "Bearer mallory"})  # fmt: skip

    assert response.status_code == 401


async def test_the_trace_headers_and_the_actor_go_on_to_the_authz_api(
    conn, platform, reader, client
):
    await written(conn, platform, reader, "A", "hr-all", ["Rules for trips."])
    trace = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    await client.post("/v1/entries:search", json={"query": "trips"}, headers={
        "authorization": "Bearer alice-token", "traceparent": trace, "x-request-id": "r-1",
        "x-actor-id": "research-agent"})  # fmt: skip

    [listing] = [r for r in platform.sent if r.url.path.endswith("/list_resources")]
    assert (listing.headers["traceparent"], listing.headers["x-request-id"]) == (trace, "r-1")
    assert json.loads(listing.content)["actor"] == {"type": "client", "id": "research-agent"}
    assert json.loads(listing.content)["subject"] == {"type": "user", "id": "alice"}


async def stored_texts(projection_store) -> list[tuple]:
    async with projection_store.connection() as conn:
        rows = await conn.execute("SELECT resource_id, markdown, cited FROM entry ORDER BY 1")
        return await rows.fetchall()


async def test_a_deleted_document_is_not_found_once_the_reader_removed_it(
    conn, platform, reader, client
):
    await written(conn, platform, reader, "A", "hr-all", ["Rules for trips."])
    await delete(conn)
    before = await found(client, "trips")  # removal is the reader's cleanup (ADR-0014)

    await settle(reader)

    assert (len(before), await found(client, "trips")) == (1, [])
    assert await stored_texts(reader.pool) == [("s1/hr-all", None, None)]  # no copy left


async def test_after_a_rebind_only_readers_of_the_new_resource_find_it(
    conn, platform, reader, client, authorizer
):
    uid = await written(conn, platform, reader, "A", "hr-all", ["Rules for trips."])
    await rebind(conn, uid, "s1/legal")
    await settle(reader)

    old_readers = await found(client, "trips")
    authorizer.resource_ids = ("s1/legal",)

    assert (old_readers, await found(client, "trips")) == ([], [uid])
    assert await stored_texts(reader.pool) == [
        ("s1/hr-all", None, None),
        ("s1/legal", "Rules for trips.", "Rules for trips."),
    ]


async def test_a_result_names_its_served_revision_and_latest_only_leaves_out_a_stale_one(
    conn, platform, reader, client
):
    uid = await written(conn, platform, reader, "A", "hr-all", ["Rules for trips."])
    await revised(conn, uid, "srv_2")
    platform.contents["crv_a2"] = ["Rules for trips, revised."]
    await accepted(conn, uid, "srv_2", "crv_a2")
    await reader.read_once()  # the event is queued, not yet run

    [hit] = (await search(client, "trips")).json()["results"]
    latest_only = await found(client, "trips", latest_only=True)
    await settle(reader)
    [fresh] = (await search(client, "trips", latest_only=True)).json()["results"]

    assert hit == {
        "document_uid": uid,
        "resource_id": "s1/hr-all",
        "source_revision_id": "srv_s1_A",
        "source_revision_created_at": None,  # until #268's state gives it
        "canonical_revision_id": "crv_a1",
        "stale": True,
        "snippet": "Rules for **trips**",
    }
    assert latest_only == []
    assert (fresh["source_revision_id"], fresh["canonical_revision_id"], fresh["stale"]) == (
        "srv_2",
        "crv_a2",
        False,
    )


def enriched(crv: str, canary: str = "") -> dict:
    """A content object (content spec §3) with a disputed formula and table and an unverified
    formula; the search term `kinetic` is only in the disputed formula."""

    def item(ref: str, status: str) -> dict:
        return {"item_id": ref, "target_refs": [ref], "status": status, "signals": [],
                "scope": "item", "origin": "reconstruction", "content": ""}  # fmt: skip

    return {
        "canonical_revision_id": crv,
        "blocks": [
            {"ref": "#/texts/0", "kind": "text", "markdown": f"Energy of motion. {canary}"},
            {"ref": "#/texts/1", "kind": "formula", "markdown": "$$\nE = kinetic + m c^2\n$$"},
            {"ref": "#/texts/2", "kind": "formula", "markdown": "$$\np = m v\n$$"},
            {"ref": "#/tables/0", "kind": "table", "markdown": "| mass | 42.7 |"},
        ],
        "enrichments": [
            item("#/texts/1", "disputed"),
            item("#/texts/2", "unverified"),
            item("#/tables/0", "disputed"),
            {**item("#", "disputed"), "target_refs": ["#"]},  # document scope: no block
        ],
    }


def serve_content(platform: Platform, crv: str, content: dict) -> None:
    async def answer(request: httpx.Request) -> httpx.Response | None:
        if request.url.path.endswith(f"/revisions/{crv}"):
            return httpx.Response(200, content=json.dumps(content).encode())
        return None

    platform.hooks.append(answer)


async def test_a_snippet_withholds_disputed_formulas_and_tables_but_the_search_matches_them(
    conn, platform, reader, client
):
    uid, srv = await document(conn)
    serve_content(platform, "crv_e1", enriched("crv_e1"))
    await accepted(conn, uid, srv, "crv_e1")
    await settle(reader)

    [hit] = (await search(client, "kinetic", limit=1)).json()["results"]

    assert hit["document_uid"] == uid
    assert "kinetic" not in hit["snippet"] and "42.7" not in hit["snippet"]
    assert "[withheld: disputed]" in hit["snippet"]
    [quoted] = (await search(client, "motion")).json()["results"]
    assert "p = m v" in quoted["snippet"]  # the unverified formula is quoted


async def test_no_canary_reaches_the_logs_or_the_metrics(conn, platform, reader, client, caplog):
    canary = "CANARY7f3a9c"
    uid, srv = await document(conn)
    content = enriched("crv_e1", canary)
    content["blocks"][1]["markdown"] = f"$$\n{canary} = 1\n$$"  # in the disputed block too
    serve_content(platform, "crv_e1", content)
    caplog.set_level(logging.DEBUG)

    await accepted(conn, uid, srv, "crv_e1")
    await settle(reader)
    served = await found(client, canary)
    platform.hooks.insert(0, refuse_authz)
    unavailable = await search(client, canary)
    platform.hooks[0] = unreachable_authz
    unreachable = await search(client, canary)

    assert (served, unavailable.status_code, unreachable.status_code) == ([uid], 503, 503)
    logged = "\n".join(f"{r.getMessage()} {r.exc_text or ''}" for r in caplog.records)
    assert caplog.records and canary not in logged
    assert canary not in generate_latest().decode()


@pytest.mark.parametrize("users", [None, "not json", '["alice"]'])
def test_the_query_process_exits_2_on_a_missing_or_malformed_setting(monkeypatch, users):
    for name, value in {"KP_PLATFORM_URL": "http://api", "KP_PROJECTION_CREDENTIAL": "c",
                        "KP_PROJECTION_DATABASE_URL": "postgresql://x"}.items():  # fmt: skip
        monkeypatch.setenv(name, value)
    if users is None:
        monkeypatch.delenv("KP_QUERY_USERS", raising=False)
    else:
        monkeypatch.setenv("KP_QUERY_USERS", users)

    assert cli.query_main() == 2
