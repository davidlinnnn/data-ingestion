"""The internal authz API over HTTP (#113, authorization design Q12, §4.1)."""

import hashlib

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


async def test_the_openapi_document_describes_both_operations_with_bearer_and_their_errors():
    async with client(token=None) as api:
        document = (await api.get("/openapi.json")).json()

    for path in ("/authz/v1/check", "/authz/v1/list_resources"):
        operation = document["paths"][path]["post"]
        assert set(operation["responses"]) == {"200", "4XX"}  # 400 and 401; never a 422
        assert operation["security"] == [{"HTTPBearer": []}]
    # Left out when null, as in a check without an actor or any list_resources answer.
    assert not {"actor", "resource"} & set(
        document["components"]["schemas"]["Decision"]["required"]
    )
