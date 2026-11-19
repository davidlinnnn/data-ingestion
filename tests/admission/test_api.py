"""The internal authz API over HTTP (#113, authorization design Q12, §4.1)."""

import hashlib
import io
import json
import logging
import re

import httpx
import pytest
from prometheus_client import REGISTRY
from psycopg_pool import AsyncConnectionPool

from kp_admission.api import RequestLog, app
from kp_admission.authz import AllowAll
from kp_canonicalization.cli import JsonFormatter
from tests.admission.authz_fake import FakeAuthorizer
from tests.admission.support import INTAKE

TOKEN = "retrieval-credential-1"
PEPS = {hashlib.sha256(TOKEN.encode()).hexdigest(): "retrieval"}
CHECK = {
    "subject": {"type": "user", "id": "alice"},
    "actor": {"type": "client", "id": "research-agent"},
    "action": "read",
    "resource": {"type": "resource", "id": "res_01"},
}
LIST = {key: value for key, value in CHECK.items() if key != "resource"}


def client(authorizer=None, token: str | None = TOKEN) -> httpx.AsyncClient:
    headers = {"authorization": f"Bearer {token}"} if token else {}
    # The authz API reads no pool; an unopened one is enough.
    pool = AsyncConnectionPool("host=127.0.0.1 port=9", open=False)
    transport = httpx.ASGITransport(app(authorizer or FakeAuthorizer(), PEPS, {}, pool, INTAKE))
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
    ],
    ids=["subject-type", "actor-type", "action", "resource-type", "resource-id"],
)
async def test_an_invalid_check_is_rejected_without_a_decision(change):
    async with client() as api:
        response = await api.post("/authz/v1/check", json=CHECK | change)

    assert response.status_code == 400
    assert response.json()["error"]["status"] == "INVALID_ARGUMENT"


async def test_list_resources_returns_the_ids_and_no_cursor_on_the_last_page():
    async with client(FakeAuthorizer("allow", resource_ids=("res_01", "res_03"))) as api:
        response = await api.post("/authz/v1/list_resources", json=LIST)

    body = response.json()
    assert response.status_code == 200 and "outcome" not in body
    assert body["resource_ids"] == ["res_01", "res_03"]
    assert "next_cursor" not in body and "resource" not in body


async def test_no_decision_is_a_503_aip_193_error_with_the_trace_id():
    async with client(FakeAuthorizer("unavailable")) as api:
        responses = [
            await api.post("/authz/v1/check", json=CHECK),
            await api.post("/authz/v1/list_resources", json=LIST),
        ]

    for response in responses:
        body = response.json()
        assert (response.status_code, body["error"]["code"]) == (503, 503)
        assert body["error"]["status"] == body["error"]["details"][0]["reason"] == "UNAVAILABLE"
        assert body["trace_id"] == response.headers["x-trace-id"]
        assert "decision_id" not in body and "outcome" not in body


TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"


@pytest.mark.parametrize(
    "traceparent",
    [f"00-{TRACE}-00f067aa0ba902b7-01", f"cc-{TRACE}-00f067aa0ba902b7-01-later-field"],
    ids=["version-00", "later-version"],
)
async def test_the_trace_id_of_a_valid_traceparent_is_in_the_header_and_the_body(traceparent):
    async with client() as api:
        response = await api.post(
            "/authz/v1/check",
            json=CHECK | {"trace_id": "from-the-body"},
            headers={"traceparent": traceparent},
        )

    assert (response.headers["x-trace-id"], response.json()["trace_id"]) == (TRACE, TRACE)


@pytest.mark.parametrize(
    "traceparent",
    [
        None,
        f"00-{TRACE.upper()}-00f067aa0ba902b7-01",
        f"00-{'0' * 32}-00f067aa0ba902b7-01",
        f"00-{TRACE}-{'0' * 16}-01",
        f"ff-{TRACE}-00f067aa0ba902b7-01",
        f"00-{TRACE}-00f067aa0ba902b7-01-later-field",
        f"00-{TRACE[:-1]}-00f067aa0ba902b7-01",
    ],
    ids=["absent", "uppercase", "zero-trace", "zero-parent", "version-ff", "00-extra", "short"],
)
async def test_without_a_valid_traceparent_the_platform_generates_the_trace_id(traceparent):
    headers = {"traceparent": traceparent} if traceparent else {}
    async with client() as api:
        first, second = [
            await api.post("/authz/v1/check", json=CHECK, headers=headers) for _ in range(2)
        ]

    generated = first.headers["x-trace-id"]
    assert re.fullmatch("[0-9a-f]{32}", generated) and generated != "0" * 32
    assert generated != TRACE and generated != second.headers["x-trace-id"]
    assert first.json()["trace_id"] == generated


@pytest.mark.parametrize(
    "token, body, status",
    [(None, CHECK, 401), (TOKEN, {"action": "read"}, 400)],
    ids=["401", "400"],
)
async def test_an_error_carries_the_trace_id_in_its_header_and_body(token, body, status):
    traceparent = f"00-{TRACE}-00f067aa0ba902b7-01"
    async with client(token=token) as api:
        response = await api.post(
            "/authz/v1/check", json=body, headers={"traceparent": traceparent}
        )

    assert response.status_code == status
    assert (response.headers["x-trace-id"], response.json()["trace_id"]) == (TRACE, TRACE)


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
        # 400 and 401, and 503; never a 422
        assert set(operation["responses"]) == {"200", "4XX", "503"}
        for response in operation["responses"].values():
            assert response["headers"]["X-Trace-Id"]["schema"] == {"type": "string"}
        [traceparent] = [p for p in operation["parameters"] if p["name"] == "traceparent"]
        assert (traceparent["in"], traceparent["required"]) == ("header", False)
        [scheme] = operation["security"][0]
        assert document["components"]["securitySchemes"][scheme] == {
            "type": "http",
            "scheme": "bearer",
        }
    assert schemas["ErrorBody"]["properties"]["status"]["enum"] == [
        "INVALID_ARGUMENT",
        "UNAUTHENTICATED",
        "PERMISSION_DENIED",
        "NOT_FOUND",
        "FAILED_PRECONDITION",
        "RESOURCE_EXHAUSTED",
        "UNAVAILABLE",
    ]
    assert schemas["CheckResponse"]["properties"]["outcome"]["enum"] == ["allow", "deny"]
    assert "outcome" not in schemas["ResourcePage"]["properties"]
    # Left out when they do not apply, never null: optional and not nullable.
    for decision in (schemas["CheckResponse"], schemas["ResourcePage"]):
        for field in ("actor", "resource", "reason", "resource_ids", "next_cursor"):
            assert field not in decision["required"]
            assert "null" not in json.dumps(decision["properties"][field])


def schema_of(document: dict, path: str, status: str) -> dict:
    ref = document["paths"][path]["post"]["responses"][status]["content"]["application/json"]
    return document["components"]["schemas"][ref["schema"]["$ref"].rsplit("/", 1)[1]]


@pytest.mark.parametrize("outcome", ["allow", "deny", "unavailable"])
async def test_each_response_has_the_fields_its_openapi_schema_names(outcome):
    async with client(FakeAuthorizer(outcome, resource_ids=("res_01",))) as api:
        document = (await api.get("/openapi.json")).json()
        responses = {
            path: await api.post(path, json=body)
            for path, body in [("/authz/v1/check", CHECK), ("/authz/v1/list_resources", LIST)]
        }

    for path, response in responses.items():
        schema = schema_of(document, path, str(response.status_code))
        body = response.json()
        assert set(schema["required"]) <= set(body) <= set(schema["properties"])


@pytest.mark.parametrize("path", ["/docs", "/redoc"])
async def test_no_page_that_loads_scripts_from_another_site_is_served(path):
    async with client(token=None) as api:
        assert (await api.get(path)).status_code == 404


async def test_healthz_answers_200_without_a_credential_or_the_database():
    async with AsyncConnectionPool("host=127.0.0.1 port=9", open=False) as pool:
        async with client(AllowAll(pool), token=None) as api:
            response = await api.get("/healthz")

    assert response.status_code == 200
    assert re.fullmatch("[0-9a-f]{32}", response.headers["x-trace-id"])


def sample(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.mark.parametrize("outcome", ["allow", "deny", "unavailable"])
async def test_each_decision_is_counted_by_operation_outcome_and_pep_and_timed(outcome):
    operations = {"check": CHECK, "list_resources": LIST}
    counted = {op: dict(operation=op, outcome=outcome, pep="retrieval") for op in operations}
    if outcome == "deny":  # list_resources answers a deny with an empty list
        counted["list_resources"]["outcome"] = "allow"
    before = {op: sample("kp_authz_decisions_total", **counted[op]) for op in operations}
    timed = {
        op: sample("kp_authz_decision_duration_seconds_count", operation=op) for op in operations
    }

    async with client(FakeAuthorizer(outcome)) as api:
        for op, body in operations.items():
            await api.post(f"/authz/v1/{op}", json=body)

    for op in operations:
        assert sample("kp_authz_decisions_total", **counted[op]) - before[op] == 1
        assert sample("kp_authz_decision_duration_seconds_count", operation=op) - timed[op] == 1


@pytest.fixture
def json_log():
    """The JSON lines the root logger writes, set up as kp-admission api sets it up."""
    stream, root = io.StringIO(), logging.getLogger()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestLog())
    level = root.level
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    yield lambda: [json.loads(line) for line in stream.getvalue().splitlines()]
    root.removeHandler(handler)
    root.setLevel(level)


@pytest.mark.parametrize("path, body", [("check", CHECK), ("list_resources", LIST)])
async def test_no_decision_is_logged_once_with_its_ids_the_pep_and_the_error_type(
    json_log, path, body
):
    headers = {"traceparent": f"00-{TRACE}-00f067aa0ba902b7-01", "x-request-id": "mesh-1"}
    async with AsyncConnectionPool("host=127.0.0.1 port=9", open=False) as pool:
        async with client(AllowAll(pool)) as api:
            response = await api.post(f"/authz/v1/{path}", json=body, headers=headers)

    assert response.status_code == 503
    [line] = [line for line in json_log() if line["message"] == "no decision"]
    assert (line["trace_id"], line["x_request_id"], line["pep"]) == (TRACE, "mesh-1", "retrieval")
    assert (line["operation"], line["error"]) == (path, "TimeoutError")
    assert line["decision_id"].startswith("dec_")
    assert TOKEN not in json.dumps(json_log()) and "alice" not in json.dumps(json_log())


async def test_a_generated_trace_id_is_the_one_in_the_header_the_body_and_the_log(json_log):
    async with AsyncConnectionPool("host=127.0.0.1 port=9", open=False) as pool:
        async with client(AllowAll(pool)) as api:
            response = await api.post("/authz/v1/check", json=CHECK)

    [line] = [line for line in json_log() if line["message"] == "no decision"]
    assert response.headers["x-trace-id"] == response.json()["trace_id"] == line["trace_id"]


class Failing:
    async def check(self, *args, **kwargs):
        raise RuntimeError("a bug")


async def test_an_unhandled_error_is_a_500_whose_trace_id_is_in_the_header_and_the_log(json_log):
    headers = {"traceparent": f"00-{TRACE}-00f067aa0ba902b7-01"}
    async with client(Failing()) as api:
        response = await api.post("/authz/v1/check", json=CHECK, headers=headers)

    assert (response.status_code, response.headers["x-trace-id"]) == (500, TRACE)
    [line] = [line for line in json_log() if line["message"] == "unhandled error"]
    assert line["trace_id"] == TRACE and "RuntimeError" in line["exception"]


async def test_a_pep_reads_every_page_by_sending_back_each_next_cursor():
    ids = tuple(f"res_{i:02}" for i in range(1, 6))
    pages, cursor = [], None
    async with client(FakeAuthorizer("allow", resource_ids=ids, page_size=2)) as api:
        while True:
            body = (
                await api.post("/authz/v1/list_resources", json=LIST | {"cursor": cursor})
            ).json()
            pages.append(body["resource_ids"])
            if not (cursor := body.get("next_cursor")):
                break

    assert pages == [["res_01", "res_02"], ["res_03", "res_04"], ["res_05"]]


async def test_an_empty_page_with_a_next_cursor_is_not_the_end_of_the_list():
    pages, cursor = [], None
    async with client(FakeAuthorizer("allow", pages=(("res_01",), (), ("res_02",)))) as api:
        while True:
            body = (
                await api.post("/authz/v1/list_resources", json=LIST | {"cursor": cursor})
            ).json()
            pages.append((body["resource_ids"], "next_cursor" in body))
            if not (cursor := body.get("next_cursor")):
                break

    assert pages == [(["res_01"], True), ([], True), (["res_02"], False)]


def test_an_upload_access_line_leaves_out_the_file_path(json_log):
    access = logging.getLogger("uvicorn.access")
    path = "/v1/batches/bat_1/items/0/files/hr/salaries-2026.pdf"
    access.info('%s - "%s %s HTTP/%s" %d', "10.0.0.7:5100", "PUT", path, "1.1", 204)
    access.info('%s - "%s %s HTTP/%s" %d', "10.0.0.7:5100", "GET", "/v1/batches/bat_1", "1.1", 200)

    lines = [line["message"] for line in json_log()]
    assert lines == [
        '10.0.0.7:5100 - "PUT /v1/batches/bat_1/items/0/files/… HTTP/1.1" 204',
        '10.0.0.7:5100 - "GET /v1/batches/bat_1 HTTP/1.1" 200',
    ]
