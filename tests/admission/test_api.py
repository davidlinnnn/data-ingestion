"""The internal authz API over HTTP (#113, authorization design Q12, §4.1)."""

import hashlib
import json

import httpx
import pytest

from kp_admission.api import app
from tests.admission.authz_fake import FakeAuthorizer

TOKEN = "retrieval-credential-1"
PEPS = {hashlib.sha256(TOKEN.encode()).hexdigest(): "retrieval"}
CHECK = {
    "subject": {"type": "user", "id": "alice"},
    "actor": {"type": "client", "id": "research-agent"},
    "action": "read",
    "resource": {"type": "resource", "id": "res_01"},
    "trace_id": "4bf92f3577b34da6",
}
LIST = {key: value for key, value in CHECK.items() if key != "resource"}


def client(authorizer=None, token: str | None = TOKEN) -> httpx.AsyncClient:
    headers = {"authorization": f"Bearer {token}"} if token else {}
    transport = httpx.ASGITransport(app(authorizer or FakeAuthorizer(), PEPS))
    return httpx.AsyncClient(transport=transport, base_url="http://api", headers=headers)


@pytest.mark.parametrize("token", [None, "another-credential"])
async def test_a_caller_without_a_registered_pep_credential_is_rejected(token):
    async with client(token=token) as api:
        responses = [
            await api.post("/authz/v1/check", json=CHECK),
            await api.post("/authz/v1/list_resources", json=LIST),
        ]

    for response in responses:
        assert response.status_code == 401
        assert response.json()["error"]["status"] == "UNAUTHENTICATED"
        assert "outcome" not in response.json()


async def test_a_registered_pep_gets_the_decision_with_its_request_and_reason():
    async with client(FakeAuthorizer("deny", "resource_not_found")) as api:
        response = await api.post("/authz/v1/check", json=CHECK)

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "deny"
    assert body["reason"] == "resource_not_found"
    assert {key: body[key] for key in CHECK} == CHECK
    assert body["actor_verified"] is False
    assert body["decision_id"].startswith("dec_")
    assert body["valid_until"] == body["evaluated_at"]
    assert body["decided_by"] == "fake/model-1"


@pytest.mark.parametrize(
    "change",
    [
        {"subject": {"type": "resource", "id": "res_02"}},
        {"actor": {"type": "user", "id": "bob"}},
        {"action": "write"},
        {"resource": {"type": "user", "id": "alice"}},
        {"resource": {"type": "resource", "id": ""}},
        {"trace_id": ""},
    ],
    ids=["subject-type", "actor-type", "action", "resource-type", "resource-id", "trace-id"],
)
async def test_an_invalid_check_is_rejected_without_a_decision(change):
    async with client() as api:
        response = await api.post("/authz/v1/check", json=CHECK | change)

    assert response.status_code == 400
    assert response.json()["error"]["status"] == "INVALID_ARGUMENT"


async def test_list_resources_returns_the_ids_and_no_cursor_on_the_last_page():
    async with client(FakeAuthorizer("allow", resource_ids=("res_01", "res_03"))) as api:
        response = await api.post("/authz/v1/list_resources", json=LIST | {"cursor": "res_00"})

    body = response.json()
    assert (response.status_code, body["outcome"]) == (200, "allow")
    assert body["resource_ids"] == ["res_01", "res_03"]
    assert "next_cursor" not in body and "resource" not in body


async def test_an_unavailable_decision_is_returned_without_resource_ids():
    async with client(FakeAuthorizer("unavailable")) as api:
        checked = await api.post("/authz/v1/check", json=CHECK)
        listed = await api.post("/authz/v1/list_resources", json=LIST)

    assert [(r.status_code, r.json()["outcome"]) for r in (checked, listed)] == [
        (200, "unavailable"),
        (200, "unavailable"),
    ]
    assert "resource_ids" not in listed.json()


@pytest.mark.parametrize("path", ["/authz/v1/check", "/authz/v1/unknown"])
async def test_a_caller_without_a_credential_is_rejected_before_its_body_is_read(path):
    async with client(token=None) as api:
        response = await api.post(
            path, content=b"{not json", headers={"content-type": "application/json"}
        )

    assert response.status_code == 401
    assert response.json()["error"]["status"] == "UNAUTHENTICATED"


@pytest.mark.parametrize(
    "content, content_type",
    [
        (b"{not json", "application/json"),
        (b'{"subject": "\xff"}', "application/json"),
        (json.dumps(CHECK).encode(), "text/plain"),
    ],
    ids=["malformed-json", "not-utf-8", "not-declared-as-json"],
)
async def test_a_body_that_cannot_be_read_as_json_is_an_aip_193_error(content, content_type):
    async with client() as api:
        response = await api.post(
            "/authz/v1/check", content=content, headers={"content-type": content_type}
        )

    error = response.json()["error"]
    assert (response.status_code, error["code"], error["status"]) == (400, 400, "INVALID_ARGUMENT")
    assert error["details"][0]["reason"] == "INVALID_ARGUMENT"


async def test_the_openapi_document_describes_both_operations_with_bearer_and_their_errors():
    async with client(token=None) as api:
        document = (await api.get("/openapi.json")).json()

    schemas = document["components"]["schemas"]
    for path in ("/authz/v1/check", "/authz/v1/list_resources"):
        operation = document["paths"][path]["post"]
        assert set(operation["responses"]) == {"200", "4XX"}  # 400 and 401; never a 422
        [scheme] = operation["security"][0]
        assert document["components"]["securitySchemes"][scheme] == {
            "type": "http",
            "scheme": "bearer",
        }
    assert schemas["ErrorBody"]["properties"]["status"]["enum"] == [
        "INVALID_ARGUMENT",
        "UNAUTHENTICATED",
    ]
    # Left out when they do not apply, never null: optional and not nullable.
    decision = schemas["Decision"]
    for field in ("actor", "resource", "reason", "resource_ids", "next_cursor"):
        assert field not in decision["required"]
        assert "null" not in json.dumps(decision["properties"][field])


@pytest.mark.parametrize("path", ["/docs", "/redoc"])
async def test_no_page_that_loads_scripts_from_another_site_is_served(path):
    async with client(token=None) as api:
        assert (await api.get(path)).status_code == 404
