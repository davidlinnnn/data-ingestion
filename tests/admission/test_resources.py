"""Resource registration over the platform API (#114, authorization design §6.1 and §7,
ADR-0013)."""

import asyncio
import hashlib
from urllib.parse import quote

import httpx
import pytest
from prometheus_client import REGISTRY
from psycopg_pool import AsyncConnectionPool

from kp_admission.api import ClientCredential, SourceCredential, app
from kp_admission.authz import AllowAll, Ref
from kp_admission.resources import resource_id, source_and_key
from tests.admission.authz_fake import FakeAuthorizer

pytestmark = pytest.mark.docker


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def source(credential_id: str, source_id: str, *scopes: str) -> SourceCredential:
    return SourceCredential.model_validate(
        {
            "credential_id": credential_id,
            "tenant_id": "t1",
            "source_id": source_id,
            "scopes": scopes or ("submit", "manage_relations"),
        }
    )


CREDENTIALS = {
    digest("km-1"): source("km-1", "km"),
    digest("km-2"): source("km-2", "km"),  # a rotation: both are valid at once
    digest("km-submit"): source("km-submit", "km", "submit"),
    digest("hr-1"): source("hr-1", "hr"),
    digest("agent-1"): ClientCredential(
        credential_id="agent-1", client_id="research-agent", delegate=True
    ),
}


@pytest.fixture
async def pool(dsn):
    async with AsyncConnectionPool(dsn, kwargs={"autocommit": True}) as pool:
        yield pool


@pytest.fixture
def api(pool):
    def connect(token: str | None = "km-1", authorizer=None) -> httpx.AsyncClient:
        headers = {"authorization": f"Bearer {token}"} if token else {}
        application = app(authorizer or FakeAuthorizer(), {}, CREDENTIALS, pool)
        transport = httpx.ASGITransport(application)
        return httpx.AsyncClient(transport=transport, base_url="http://api", headers=headers)

    return connect


async def changes(conn) -> list[tuple]:
    cursor = await conn.execute(
        "SELECT op, resource_id, actor_source_id, actor_credential_id FROM authz.relation_change"
        " ORDER BY at"
    )
    return await cursor.fetchall()


async def test_registering_a_key_twice_creates_it_once_and_returns_the_same_resource(api, conn):
    async with api() as km:
        first = await km.put("/v1/resources/hr-all", json={"name": "HR, everyone"})
        second = await km.put("/v1/resources/hr-all", json={"name": "HR, everyone"})

    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["change_id"].startswith("chg_") and "change_id" not in second.json()
    resource = {"key": "hr-all", "name": "HR, everyone", "created_at": first.json()["created_at"]}
    assert first.json() | {"change_id": None} == resource | {"change_id": None}
    assert second.json() == resource
    assert await changes(conn) == [("create_resource", "km/hr-all", "km", "km-1")]


async def test_simultaneous_first_registrations_create_the_resource_once(api, conn):
    async with api("km-1") as one, api("km-2") as two:
        responses = await asyncio.gather(
            *(c.put("/v1/resources/hr-all") for c in (one, two, one, two))
        )

    assert sorted(r.status_code for r in responses) == [200, 200, 200, 201]
    assert len(await changes(conn)) == 1


async def test_two_sources_with_the_same_key_each_reach_only_their_own_resource(api, conn):
    async with api("km-1") as km, api("hr-1") as hr:
        await km.put("/v1/resources/shared", json={"name": "km's"})
        await hr.put("/v1/resources/shared", json={"name": "hr's"})
        names = [(await c.get("/v1/resources/shared")).json()["name"] for c in (km, hr)]
        listed = [(await c.get("/v1/resources")).json()["resources"] for c in (km, hr)]
        deleted = await hr.delete("/v1/resources/shared")
        after = [(await c.get("/v1/resources/shared")).status_code for c in (km, hr)]

    assert names == ["km's", "hr's"]
    assert [[r["name"] for r in page] for page in listed] == [["km's"], ["hr's"]]
    assert (deleted.status_code, after) == (204, [200, 404])
    assert [change[:3] for change in await changes(conn)] == [
        ("create_resource", "km/shared", "km"),
        ("create_resource", "hr/shared", "hr"),
        ("delete_resource", "hr/shared", "hr"),
    ]


async def test_a_registered_key_is_placeable_by_its_full_identifier_and_an_unregistered_one_is_not(
    api, pool
):
    async with api() as km:
        await km.put("/v1/resources/hr-all")

    decide = AllowAll(pool).check
    km_source = Ref(type="source", id="km")
    registered = await decide(km_source, "place", resource_id("km", "hr-all"), trace_id="t")
    unregistered = await decide(km_source, "place", resource_id("km", "eng"), trace_id="t")
    assert (registered.outcome, unregistered.outcome) == ("allow", "deny")


KEYS = ["hr/policies", "two words", "人資-全體", "a%2Fb", "/", "x/"]
SOURCES = ["km", "k/m", "100%", "人資"]


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("source_id", SOURCES)
def test_the_full_identifier_splits_back_into_its_source_and_key(source_id, key):
    assert source_and_key(resource_id(source_id, key)) == (source_id, key)


def test_two_different_pairs_never_share_a_full_identifier():
    pairs = [(s, k) for s in SOURCES for k in KEYS] + [("k", "m/x"), ("k/m", "x")]
    assert len({resource_id(*pair) for pair in pairs}) == len(pairs)


@pytest.mark.parametrize("text", ["", "km", "/key"])
def test_a_string_no_source_and_key_make_is_refused(text):
    with pytest.raises(ValueError):
        source_and_key(text)


@pytest.mark.parametrize("key", KEYS)
async def test_a_key_with_slashes_spaces_or_other_scripts_names_one_resource(api, conn, key):
    path = f"/v1/resources/{quote(key, safe='')}"
    async with api() as km:
        registered = await km.put(path)
        got = await km.get(path)
        listed = (await km.get("/v1/resources")).json()["resources"]
        deleted = await km.delete(path)
        gone = await km.get(path)

    assert (registered.status_code, got.status_code) == (201, 200)
    assert registered.json()["key"] == got.json()["key"] == listed[0]["key"] == key
    assert (deleted.status_code, gone.status_code) == (204, 404)
    assert {change[1] for change in await changes(conn)} == {resource_id("km", key)}


@pytest.mark.parametrize("length, status", [(200, 201), (201, 400)])
async def test_a_key_is_at_most_200_characters(api, length, status):
    async with api() as km:
        response = await km.put(f"/v1/resources/{quote('鍵' * length)}")

    assert response.status_code == status


async def test_a_repeated_registration_with_another_name_replaces_it_and_without_one_keeps_it(api):
    async with api() as km:
        unnamed = await km.put("/v1/resources/hr-all")
        named = await km.put("/v1/resources/hr-all", json={"name": "HR"})
        kept = await km.put("/v1/resources/hr-all")

    assert "name" not in unnamed.json()
    assert (named.status_code, named.json()["name"], kept.json()["name"]) == (200, "HR", "HR")


async def test_a_key_the_source_did_not_register_is_not_found(api):
    async with api() as km:
        responses = [await km.get("/v1/resources/nope"), await km.delete("/v1/resources/nope")]

    for response in responses:
        error = response.json()["error"]
        assert (response.status_code, error["status"]) == (404, "NOT_FOUND")
        assert error["details"][0] == {
            "@type": "type.googleapis.com/google.rpc.ErrorInfo",
            "reason": "RESOURCE_NOT_FOUND",
            "domain": "admission.knowledge-platform",
        }
        assert response.json()["trace_id"] == response.headers["x-trace-id"]


async def test_a_write_needs_a_manage_relations_credential_and_a_read_any_source_credential(api):
    async with api() as km:
        await km.put("/v1/resources/hr-all")
    async with api("km-submit") as submit, api("agent-1") as agent:
        writes = [
            await submit.put("/v1/resources/new"),
            await submit.delete("/v1/resources/hr-all"),
        ]
        reads = [await submit.get("/v1/resources"), await submit.get("/v1/resources/hr-all")]
        by_client = [await agent.get("/v1/resources"), await agent.put("/v1/resources/new")]

    assert [r.status_code for r in writes + reads + by_client] == [403, 403, 200, 200, 403, 403]
    for response in writes + by_client:
        assert response.json()["error"]["status"] == "PERMISSION_DENIED"


@pytest.mark.parametrize("token", [None, "unregistered"])
async def test_a_call_without_a_registered_credential_is_unauthenticated(api, token):
    async with api(token) as caller:
        response = await caller.put("/v1/resources/hr-all", content=b"not read")

    error = response.json()["error"]
    assert (response.status_code, error["status"]) == (401, "UNAUTHENTICATED")
    assert error["details"][0]["domain"] == "admission.knowledge-platform"


async def test_two_credentials_of_one_source_are_valid_at_once(api):
    async with api("km-1") as old, api("km-2") as new:
        registered = await old.put("/v1/resources/hr-all")
        got = await new.get("/v1/resources/hr-all")
        again = await new.put("/v1/resources/hr-all")

    assert (registered.status_code, got.status_code, again.status_code) == (201, 200, 200)


@pytest.mark.parametrize(
    "outcome, status, reason",
    [("deny", 403, "PERMISSION_DENIED"), ("unavailable", 503, "AUTHZ_UNAVAILABLE")],
)
async def test_a_delete_without_manage_is_refused_and_leaves_the_resource(
    api, conn, outcome, status, reason
):
    async with api() as km:
        await km.put("/v1/resources/hr-all")
    async with api(authorizer=FakeAuthorizer(outcome)) as km:
        response = await km.delete("/v1/resources/hr-all")
        still = await km.get("/v1/resources/hr-all")

    assert response.status_code == status
    assert response.json()["error"]["details"][0]["reason"] == reason
    assert still.status_code == 200
    assert [change[0] for change in await changes(conn)] == ["create_resource"]


async def bind(conn, resource: str, deleted: bool) -> None:
    await conn.execute(
        "INSERT INTO document (document_uid, tenant_id, source_id, document_id, resource_id,"
        " deleted_at) VALUES (%s, 't1', 'km', %s, %s, %s)",
        (f"doc_{resource}_{deleted}", f"d-{deleted}", resource, "now()" if deleted else None),
    )


async def test_a_resource_with_a_live_document_is_not_deleted_and_a_deleted_one_does_not_count(
    api, conn
):
    async with api() as km:
        await km.put("/v1/resources/hr-all")
        await bind(conn, resource_id("km", "hr-all"), deleted=True)
        await km.put("/v1/resources/eng")
        await bind(conn, resource_id("km", "eng"), deleted=False)
        emptied = await km.delete("/v1/resources/hr-all")
        bound = await km.delete("/v1/resources/eng")

    assert emptied.status_code == 204
    error = bound.json()["error"]
    assert (bound.status_code, error["status"]) == (409, "FAILED_PRECONDITION")
    assert error["details"][0]["reason"] == "RESOURCE_NOT_EMPTY"


async def test_a_source_reads_every_key_by_sending_back_each_next_page_token(api):
    async with api() as km:
        for key in ("c", "a", "b"):
            await km.put(f"/v1/resources/{key}")
        pages, token = [], None
        while True:
            params = {"page_size": 2} | ({"page_token": token} if token else {})
            body = (await km.get("/v1/resources", params=params)).json()
            pages.append([r["key"] for r in body["resources"]])
            if not (token := body.get("next_page_token")):
                break

    assert pages == [["a", "b"], ["c"]]


def sample(**labels: str) -> float:
    return REGISTRY.get_sample_value("kp_api_calls_total", labels) or 0.0


async def test_each_call_is_counted_by_operation_and_status(api):
    before = [
        sample(operation="register_resource", status="201"),
        sample(operation="get_resource", status="404"),
    ]
    async with api() as km:
        await km.put("/v1/resources/hr-all")
        await km.get("/v1/resources/nope")

    after = [
        sample(operation="register_resource", status="201"),
        sample(operation="get_resource", status="404"),
    ]
    assert [b - a for a, b in zip(before, after, strict=True)] == [1, 1]


async def test_the_openapi_document_names_bearer_and_the_trace_headers_on_each_operation(api):
    async with api(None) as anyone:
        document = (await anyone.get("/openapi.json")).json()

    operations = [
        document["paths"]["/v1/resources/{key}"][method] for method in ("put", "get", "delete")
    ] + [document["paths"]["/v1/resources"]["get"]]
    for operation in operations:
        assert {"200", "4XX", "503"} <= set(operation["responses"])
        assert any(p["name"] == "traceparent" for p in operation["parameters"])
        assert operation["security"]
    assert "201" in document["paths"]["/v1/resources/{key}"]["put"]["responses"]
