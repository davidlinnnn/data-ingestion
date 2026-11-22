"""Status (#97, admission spec §5.5–§5.7, §7, §7.3): canonical processing's status reports, the
request and Document queries, readiness and attention, over the platform API with a real
database. A fake start stands in for Temporal: it gives each dispatched request the run ID
`run-a`, and the tests send the reports that run would."""

import hashlib
from typing import Any

import httpx
import pytest
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from kp_admission import feed, status
from kp_admission.api import SourceCredential, app
from kp_admission.dispatcher import dispatch_due
from kp_admission.reports import Pipeline
from kp_canonicalization.ports.status_reporter import HttpStatusReporter, Position
from tests.admission.authz_fake import FakeAuthorizer
from tests.admission.support import FILES, INTAKE, request
from tests.ports.test_status_reporter import report as sender_report

pytestmark = pytest.mark.docker

CANONICAL = "canonical-credential-1"
ROTATED = "canonical-credential-2"  # its successor, while the first is rotated out
PIPELINE = Pipeline(
    pipeline_id="kp-canonicalization",
    track="canonical",
    stages=["prepare", "parse", "enrich", "finalize"],
    start_deadline_s=1800,
    update_interval_s=1800,
)
REJECTED = {
    "domain": "kp-canonicalization",
    "reason": "PASSWORD_REQUIRED",
    "message": "PDF needs a password",
    "retryable": False,
    "metadata": {"cause": "source", "category": "source"},
    "support_ref": "temporal:req/run-a",
    "occurred_at": "2026-11-19T08:05:00Z",
}
PLATFORM = REJECTED | {
    "reason": "PLATFORM_ERROR",
    "message": "storage unavailable",
    "retryable": True,
    "metadata": {"cause": "platform", "category": "platform"},
}


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def credential(source_id: str) -> SourceCredential:
    return SourceCredential.model_validate(
        {"credential_id": f"{source_id}-1", "tenant_id": "t1", "source_id": source_id,
         "scopes": ["submit"]}
    )  # fmt: skip


@pytest.fixture
async def pool(dsn):
    async with AsyncConnectionPool(dsn, kwargs={"autocommit": True}) as connections:
        yield connections


@pytest.fixture
def api(pool):
    application = app(
        FakeAuthorizer(),
        {},
        {digest(s): credential(s) for s in ("s1", "s2")},
        pool,
        INTAKE,
        pipelines={digest(CANONICAL): PIPELINE, digest(ROTATED): PIPELINE},
    )

    def connect(token: str = "s1") -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(application),
            base_url="http://api",
            headers={"authorization": f"Bearer {token}"},
        )

    return connect


async def document(
    conn, document_id: str = "A", source_id: str = "s1", key: str = "hr-all", generation: int = 1
):
    """A Document of `source_id` with one Source Revision, its latest: (uid, srv)."""
    uid = f"doc_{source_id}_{document_id}" + (f"_{generation}" if generation > 1 else "")
    srv = uid.replace("doc_", "srv_", 1)
    await conn.execute(
        "INSERT INTO document (document_uid, tenant_id, source_id, document_id, resource_id,"
        " title, metadata) VALUES (%s, 't1', %s, %s, %s, 'Travel', '{\"km\": \"HR\"}')",
        (uid, source_id, document_id, f"{source_id}/{key}"),
    )
    await conn.execute(
        "INSERT INTO source_revision (source_revision_id, tenant_id, document_uid,"
        " source_version, files, sequence) VALUES (%s, 't1', %s, '1', %s, 1)",
        (srv, uid, Jsonb(FILES)),
    )
    await conn.execute(
        "UPDATE document SET latest_source_revision_id = %s WHERE document_uid = %s", (srv, uid)
    )
    return uid, srv


async def run_a(start_input: dict[str, Any]) -> str:
    return "run-a"


async def dispatched(conn, uid: str, srv: str, **fields: Any) -> str:
    request_id, _ = await request(conn, uid, srv, **fields)
    assert await dispatch_due(conn, run_a) == 1
    return request_id


def report(request_id: str, seq: int, stage: str, state: str, **fields: Any) -> dict[str, Any]:
    """A status report with the twelve fields of #129."""
    return {
        "request_id": request_id,
        "attempt_id": "run-a",
        "seq": seq,
        "stages_version": "1",
        "stage": stage,
        "state": state,
        "progress": None,
        "message": "",
        "method_version": "paper-pdf@1",
        "manifest_ref": None,
        "observed_at": f"2026-11-19T08:0{seq % 10}:00Z",
        "error": None,
    } | fields


async def send(api, body: dict[str, Any]) -> httpx.Response:
    async with api(CANONICAL) as canonical:
        return await canonical.post(
            f"/report/v1/requests/{body['request_id']}/status-reports", json=body
        )


async def test_reports_move_a_request_to_processing_then_succeeded(api, conn):
    request_id = await dispatched(conn, *await document(conn))
    async with api() as source:
        assert (await source.get(f"/v1/requests/{request_id}")).json()["state"] == "queued"

        assert (await send(api, report(request_id, 1, "prepare", "running"))).status_code == 202
        processing = (await source.get(f"/v1/requests/{request_id}")).json()
        progress = {"done": 5, "total": 28, "unit": "pages"}
        parse = report(request_id, 2, "parse", "running", progress=progress)
        assert (await send(api, parse)).status_code == 202
        finalize = report(request_id, 3, "finalize", "succeeded", manifest_ref="requests/r.json")
        assert (await send(api, finalize)).status_code == 202
        succeeded = await source.get(f"/v1/requests/{request_id}")

    assert processing["state"] == "processing"
    assert processing["details"]["stage"] == "prepare"
    body = succeeded.json()
    assert succeeded.status_code == 200
    assert {k: body[k] for k in ("request_id", "kind", "state", "document_id", "initiator")} == {
        "request_id": request_id,
        "kind": "process",
        "state": "succeeded",
        "document_id": "A",
        "initiator": "source",
    }
    assert body["terminal_at"] == "2026-11-19T08:03:00Z"
    assert body["error"] is None
    assert body["details"] == {"attempt_id": "run-a", "seq": 3, "stage": "finalize",
                               "progress": None}  # fmt: skip


async def state_of(conn, request_id: str) -> tuple:
    cursor = await conn.execute(
        "SELECT r.state, r.last_report->>'seq', s.outcome FROM request r"
        " JOIN source_revision s USING (source_revision_id) WHERE request_id = %s",
        (request_id,),
    )
    return await cursor.fetchone()


async def test_reports_out_of_order_get_the_position_and_a_repeat_of_the_last_changes_nothing(
    api, conn
):
    request_id = await dispatched(conn, *await document(conn))
    assert (await send(api, report(request_id, 1, "prepare", "running"))).status_code == 202
    assert (await send(api, report(request_id, 3, "parse", "running"))).status_code == 202  # a gap

    repeat = await send(api, report(request_id, 3, "parse", "running"))
    behind = await send(api, report(request_id, 2, "prepare", "succeeded"))
    changed = await send(api, report(request_id, 3, "parse", "succeeded"))  # same seq, not a repeat

    assert repeat.status_code == 200
    assert (behind.status_code, behind.json()) == (409, {"attempt_id": "run-a", "seq": 3})
    assert (changed.status_code, changed.json()) == (409, {"attempt_id": "run-a", "seq": 3})
    assert await state_of(conn, request_id) == ("processing", "3", "pending")


async def test_both_credentials_of_a_pipeline_being_rotated_report(api, conn):
    request_id = await dispatched(conn, *await document(conn))
    assert (await send(api, report(request_id, 1, "prepare", "running"))).status_code == 202
    async with api(ROTATED) as successor:
        response = await successor.post(
            f"/report/v1/requests/{request_id}/status-reports",
            json=report(request_id, 2, "parse", "running"),
        )
    assert response.status_code == 202


async def test_only_the_current_attempt_changes_the_request(api, conn):
    request_id = await dispatched(conn, *await document(conn))

    other = await send(api, report(request_id, 1, "finalize", "succeeded", attempt_id="run-old"))

    assert (other.status_code, other.json()) == (409, {"attempt_id": "run-a", "seq": 0})
    assert await state_of(conn, request_id) == ("queued", None, "pending")


async def test_a_report_before_the_dispatcher_records_the_attempt_is_retried(api, conn):
    request_id, _ = await request(conn, *await document(conn))  # started, not yet recorded

    early = await send(api, report(request_id, 1, "prepare", "running"))

    assert early.status_code == 503
    assert early.headers["Retry-After"]
    assert early.json()["error"]["details"][0]["reason"] == "ATTEMPT_NOT_RECORDED"
    assert await state_of(conn, request_id) == ("queued", None, "pending")


@pytest.mark.parametrize(
    "change",
    [
        {"progress": "5 of 28"},  # not an object
        {"error": PLATFORM},  # an error without a failure
        {"stage": "publish"},  # a stage canonical processing did not register
        {"request_id": "req_other"},  # not the request of the path
        {"observed_at": "2026-11-19T08:00:00"},  # no time zone
    ],
)
async def test_a_report_that_breaks_the_contract_is_400_and_changes_nothing(api, conn, change):
    request_id = await dispatched(conn, *await document(conn))
    body = report(request_id, 1, "prepare", "running") | change
    async with api(CANONICAL) as canonical:
        response = await canonical.post(
            f"/report/v1/requests/{request_id}/status-reports", json=body
        )

    assert response.status_code == 400
    assert await state_of(conn, request_id) == ("queued", None, "pending")


async def test_a_report_missing_a_field_or_without_a_pipeline_credential_is_refused(api, conn):
    request_id = await dispatched(conn, *await document(conn))
    body = report(request_id, 1, "prepare", "running")
    del body["message"]
    async with api(CANONICAL) as canonical, api() as source:
        missing = await canonical.post(
            f"/report/v1/requests/{request_id}/status-reports", json=body
        )
        as_source = await source.post(
            f"/report/v1/requests/{request_id}/status-reports",
            json=report(request_id, 1, "prepare", "running"),
        )
        unknown = await canonical.post(
            "/report/v1/requests/req_none/status-reports",
            json=report("req_none", 1, "prepare", "running"),
        )

    assert (missing.status_code, as_source.status_code, unknown.status_code) == (400, 401, 404)


async def fail(api, request_id: str, error: dict[str, Any]) -> None:
    response = await send(api, report(request_id, 1, "prepare", "failed", error=error))
    assert response.status_code == 202


async def test_a_source_cause_rejects_the_revision_and_the_document_says_so(api, conn):
    request_id = await dispatched(conn, *await document(conn))

    await fail(api, request_id, REJECTED)

    assert await state_of(conn, request_id) == ("failed", "1", "rejected")
    async with api() as source:
        failed = (await source.get(f"/v1/requests/{request_id}")).json()
        doc = (await source.get("/v1/documents/A")).json()
    assert failed["error"] == REJECTED
    assert doc["attention"] == [
        {"kind": "source_revision_rejected", "action_owner": "source", "source_version": "1",
         "message": "PDF needs a password", "since": "2026-11-19T08:01:00Z"}
    ]  # fmt: skip


async def test_a_platform_failure_without_an_active_request_is_processing_failed(api, conn):
    uid, srv = await document(conn)
    first = await dispatched(conn, uid, srv)
    await fail(api, first, PLATFORM)
    async with api() as source:
        failed = (await source.get("/v1/documents/A")).json()
        shown_error = (await source.get(f"/v1/requests/{first}")).json()["error"]

        retry = await dispatched(conn, uid, srv, retry_of=first)
        retrying = (await source.get("/v1/documents/A")).json()
        done = report(retry, 1, "finalize", "succeeded")
        assert (await send(api, done)).status_code == 202

    assert failed["attention"] == [
        {"kind": "processing_failed", "action_owner": "platform", "track": "canonical",
         "source_version": "1", "message": status.PLATFORM_FAILURE,
         "since": "2026-11-19T08:01:00Z"}
    ]  # fmt: skip
    # The message of a platform failure can be exception text: the Source sees a fixed one.
    assert shown_error == PLATFORM | {"message": status.PLATFORM_FAILURE}
    assert retrying["attention"] == []
    # The retry succeeded: the revision waits for acceptance (#251), and is no longer failed.
    assert await state_of(conn, retry) == ("succeeded", "1", "pending")


async def test_a_failed_platform_refresh_changes_neither_outcome_nor_attention(api, conn):
    """Scenario 13, its status part: the refresh is made as #98's command will make it."""
    uid, srv = await document(conn)
    await conn.execute("UPDATE source_revision SET outcome = 'accepted'")  # #251's write
    async with api() as source:
        before = (await source.get("/v1/documents/A")).json()
        refresh = await dispatched(conn, uid, srv, initiator="platform", priority="low")
        await fail(api, refresh, PLATFORM)
        after = (await source.get("/v1/documents/A")).json()

    assert await state_of(conn, refresh) == ("failed", "1", "accepted")
    assert (after["readiness"], after["attention"]) == (before["readiness"], [])


async def test_an_attempt_past_its_deadline_is_progress_stalled(api, conn):
    uid, srv = await document(conn)
    request_id = await dispatched(conn, uid, srv)
    async with api() as source:
        fresh = (await source.get("/v1/documents/A")).json()
        await conn.execute("UPDATE outbox SET dispatched_at = now() - interval '31 minutes'")
        not_started = (await source.get("/v1/documents/A")).json()
        assert (await send(api, report(request_id, 1, "prepare", "running"))).status_code == 202
        reporting = (await source.get("/v1/documents/A")).json()
        await conn.execute("UPDATE request SET reported_at = now() - interval '31 minutes'")
        silent = (await source.get("/v1/documents/A")).json()

    assert fresh["attention"] == reporting["attention"] == []
    for stalled in (not_started, silent):
        assert [(a["kind"], a["action_owner"]) for a in stalled["attention"]] == [
            ("progress_stalled", "platform")
        ]


@pytest.mark.parametrize(("ended_days_ago", "status"), [(29, 200), (30, 404)])
async def test_a_request_is_404_30_days_after_its_terminal_outcome(
    api, conn, ended_days_ago, status
):
    request_id = await dispatched(conn, *await document(conn))
    await fail(api, request_id, PLATFORM)
    await conn.execute(
        "UPDATE request SET terminal_at = now() - %s * interval '1 day'", (ended_days_ago,)
    )
    async with api() as source:
        assert (await source.get(f"/v1/requests/{request_id}")).status_code == status


async def test_an_active_request_never_expires(api, conn):
    request_id = await dispatched(conn, *await document(conn))
    await conn.execute("UPDATE request SET created_at = now() - interval '400 days'")
    async with api() as source:
        assert (await source.get(f"/v1/requests/{request_id}")).status_code == 200


async def test_another_sources_document_and_request_are_404(api, conn):
    request_id = await dispatched(conn, *await document(conn, "A", source_id="s2"))
    async with api("s1") as s1, api("s2") as s2:
        theirs = [await s1.get(f"/v1/requests/{request_id}"), await s1.get("/v1/documents/A")]
        own = [await s2.get(f"/v1/requests/{request_id}"), await s2.get("/v1/documents/A")]
        listed = (await s1.get("/v1/documents")).json()

    assert [r.status_code for r in theirs] == [404, 404]
    assert [r.status_code for r in own] == [200, 200]
    assert listed == {"documents": [], "next_page_token": ""}


async def test_a_deleted_document_is_shown_as_deleted_until_a_new_generation_exists(api, conn):
    await document(conn, "A")
    await conn.execute("UPDATE document SET deleted_at = now()")  # as #98 will apply it
    async with api() as source:
        deleted = (await source.get("/v1/documents/A")).json()
        await document(conn, "A", key="hr-mgr", generation=2)  # declared again: a new generation
        current = (await source.get("/v1/documents/A")).json()
        listed = (await source.get("/v1/documents")).json()["documents"]

    assert (deleted["readiness"], deleted["attention"]) == ("deleted", [])
    assert deleted["since"] == deleted["deleted_at"]
    assert (current["readiness"], current["resource_id"], current["deleted_at"]) == (
        "not_ready", "hr-mgr", None,
    )  # fmt: skip
    assert sorted(d["readiness"] for d in listed) == ["deleted", "not_ready"]


async def listing(source, **params: Any) -> list[str]:
    """Every page of the list, followed to its end: the document_ids."""
    found, token = [], ""
    while True:
        page = (await source.get("/v1/documents", params=params | {"page_token": token})).json()
        found += [d["document_id"] for d in page["documents"]]
        if not (token := page["next_page_token"]):
            return found


async def test_the_list_filters_and_pages_and_a_first_page_alone_misses_matches(api, conn):
    await feed.set_profile(conn, tenant_id="t1", source_id="s1", projections=["retrieval"])
    for document_id, key in [("A", "hr-all"), ("B", "hr-all"), ("C", "fin"), ("D", "hr-all")]:
        await document(conn, document_id, key=key)
    await conn.execute("UPDATE document SET deleted_at = now() WHERE document_id = 'B'")
    await conn.execute(
        "UPDATE document SET deleted_at = now() - interval '31 days' WHERE document_id = 'C'"
    )
    async with api() as source:
        first = (await source.get("/v1/documents", params={"page_size": 1})).json()
        all_ = await listing(source, page_size=1)
        in_hr = await listing(source, page_size=1, resource_id="hr-all")
        not_ready_first = (
            await source.get("/v1/documents", params={"page_size": 2, "readiness": "not_ready"})
        ).json()
        not_ready = await listing(source, page_size=2, readiness="not_ready")
        served = await listing(source, projection="retrieval")
        bad = await source.get("/v1/documents", params={"page_token": "no-separator"})

    assert first["documents"][0] == {
        "document_id": "A", "document_uid": "doc_s1_A", "latest": {"source_version": "1"},
        "readiness": "not_ready", "metadata": {"km": "HR"},
    }  # fmt: skip
    assert all_ == ["A", "B", "D"]  # C left retention
    assert in_hr == ["A", "B", "D"]
    assert [d["document_id"] for d in not_ready_first["documents"]] == ["A"]  # B is deleted
    assert not_ready == ["A", "D"]  # D is only on the second page
    assert served == []  # no serving facts before #252
    assert bad.status_code == 400


@pytest.mark.parametrize(
    ("deleted", "required", "serving", "expected"),
    [
        (True, ["retrieval"], {"retrieval": "srv_2"}, "deleted"),
        (False, [], {}, "not_ready"),
        (False, ["retrieval", "llm-wiki"], {"retrieval": "srv_2"}, "not_ready"),
        (
            False,
            ["retrieval", "llm-wiki"],
            {"retrieval": "srv_2", "llm-wiki": "srv_1"},
            "ready_stale",
        ),
        (False, ["retrieval"], {"retrieval": "srv_2", "graph": "srv_1"}, "ready"),
    ],
)
def test_readiness_is_the_first_match_of_section_7_1(deleted, required, serving, expected):
    assert status.readiness(deleted, required, serving, latest="srv_2") == expected


async def test_the_sender_and_the_receiver_agree_on_delivery_and_position(api, conn):
    """The contract test of canonical processing's HttpStatusReporter against this receiver."""
    request_id = await dispatched(conn, *await document(conn))
    async with api(CANONICAL) as client, api("unregistered") as stranger:
        reporter = HttpStatusReporter(client, "http://api")

        async def sent(seq: int, attempt_id: str = "run-a", via=reporter):
            return await via.report(
                sender_report(seq, request_id=request_id, attempt_id=attempt_id)
            )

        first, gap, repeat, stale = [await sent(seq) for seq in (1, 3, 3, 2)]
        other = await sent(1, attempt_id="run-b")
        refused = await sent(4, via=HttpStatusReporter(stranger, "http://api"))

    assert (first.delivered, gap.delivered, repeat.delivered) == (True, True, True)
    assert (stale.delivered, stale.position) == (False, Position("run-a", 3))
    assert (other.delivered, other.position) == (False, Position("run-a", 3))
    assert (refused.delivered, refused.position, refused.error) == (False, None, "HTTP 401")
    assert await state_of(conn, request_id) == ("processing", "3", "pending")
