"""Source Deletion (#98, admission spec §5.8, §8): the admission rules prototype's scenarios 14, 15
and 19 as acceptance tests over the platform API, and the enforcement judgment (C3) with the #55
handoff's SC15, SC16 and SC20r.

Where the prototype differs from the current spec, the spec wins: since ADR-0014 there is no
serving-time block, so the call applies the deletion and the Document reads `deleted` at once
(scenario 14's "still ready after received" step has no counterpart), and the delete request's
last stage is `enforced`, not `succeeded`. Scenario 19's batch 404 is #250's retention."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from prometheus_client import REGISTRY
from psycopg_pool import AsyncConnectionPool

from kp_admission import adoption, deletion, feed, gauges, serving
from kp_admission.api import app
from kp_admission.authz import AllowAll
from kp_admission.batches import Intake
from kp_admission.dispatcher import dispatch_due
from kp_admission.requests import record_outcome
from kp_admission.storage import FakeObjectStore
from tests.admission.support import candidate
from tests.admission.test_batches import (
    C1,
    CREDENTIALS,
    PDF,
    SOURCES,
    A,
    file,
    of,
    processed,
    submit,
    upload,
)
from tests.admission.test_serving import (
    PIPELINES,
    accepted,
    build,
    fact,
    included,
    registered,
)
from tests.admission.test_status import credential, digest, document

pytestmark = pytest.mark.docker


@pytest.fixture
async def pool(dsn):
    async with AsyncConnectionPool(dsn, kwargs={"autocommit": True}) as connections:
        yield connections


@pytest.fixture
def store() -> FakeObjectStore:
    return FakeObjectStore()


@pytest.fixture
def api(pool, store):
    """A client per bearer token: hr-km and s1 are Sources, a pipeline's track its reporter."""
    application = app(
        AllowAll(pool),
        {digest(track): track for track in PIPELINES},
        CREDENTIALS | {digest("s1"): credential("s1")},
        pool,
        Intake(store, SOURCES),
        pipelines={digest(track): p for track, p in PIPELINES.items()},
    )

    def connect(token: str = "hr-km") -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(application),
            base_url="http://api",
            headers={"authorization": f"Bearer {token}"},
        )

    return connect


@pytest.fixture
async def platform(api, conn):
    async with api() as hr:
        assert (await hr.put("/v1/resources/hr-all")).status_code == 201
    await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@1")


async def enforce(conn, now: datetime | None = None):
    return await deletion.enforce(conn, PIPELINES, now or datetime.now(UTC))


async def started(start_input: dict) -> str:
    return f"run-{start_input['request_id']}"


async def test_14_a_deletion_applies_at_once_repeats_and_a_new_c_is_a_new_generation(
    platform, api, store, conn
):
    async with api() as hr:
        _, first = await submit(hr, store, [C1])
        await processed(conn, of(first.json(), "C")["request_id"], "accepted")
        c2 = C1 | {"source_version": "2", "files": [file("c.pdf", "c-2", PDF)]}
        before = (await hr.post("/v1/batches", json={"items": [c2]})).json()
        upload(store, before, [c2])
        old_uid = of(before, "C")["document_uid"]

        deleted = await hr.delete("/v1/documents/C")
        seen = (await hr.get("/v1/documents/C")).json()
        again = await hr.delete("/v1/documents/C")
        rejected = await hr.post(f"/v1/batches/{before['batch_id']}/finalize")
        judged = await enforce(conn)
        request = (await hr.get(f"/v1/requests/{deleted.json()['request_id']}")).json()

        declared, finalized = await submit(hr, store, [C1 | {"title": "New C"}])
        current = (await hr.get("/v1/documents/C")).json()
        listed = (await hr.get("/v1/documents", params={"readiness": "deleted"})).json()

    assert deleted.status_code == 202
    assert deleted.json() == {
        "request_id": deleted.json()["request_id"], "kind": "delete", "state": "applied"
    }  # fmt: skip
    assert (seen["readiness"], seen["title"], seen["metadata"]) == ("deleted", None, None)
    assert again.status_code == 202 and again.json() == deleted.json()
    assert rejected.json()["items"][0]["error"]["reason"] == "DOCUMENT_DELETED"
    assert judged == {"enforced": 1}
    assert (request["kind"], request["state"], request["document_uid"]) == (
        "delete", "enforced", old_uid
    )  # fmt: skip
    new_uid = of(declared, "C")["document_uid"]
    assert new_uid != old_uid and of(finalized.json(), "C")["status"] == "queued"
    assert current["document_uid"] == new_uid
    assert [d["document_uid"] for d in listed["documents"]] == [old_uid]


async def test_a_deletion_appends_its_event_and_reads_deleted_on_the_read_plane(
    platform, api, store, conn
):
    """SC16's platform side: a projection that bootstraps after the deletion lists no such
    Document and reads it deleted (A4 R-a)."""
    async with api() as hr:
        declared, _ = await submit(hr, store, [A])
        uid = of(declared, "A")["document_uid"]
        async with api("retrieval") as reader:
            listed = (await reader.get("/read/v1/sources/hr-km/documents")).json()
            start = (await reader.get("/read/v1/feed")).json()["next_cursor"]
            await hr.delete("/v1/documents/A")
            state = (await reader.get(f"/read/v1/documents/{uid}/state")).json()
            bootstrap = (await reader.get("/read/v1/sources/hr-km/documents")).json()
    events, _ = await feed.read(conn, start, 100)

    assert state["status"] == "deleted" and state["current"] is None
    assert listed["document_uids"] == [uid] and bootstrap["document_uids"] == []
    assert [(e.kind, e.priority, e.document_uid) for e in events] == [
        ("document_deleted", "narrowing", uid)
    ]


async def test_a_deletion_ends_its_requests_not_dispatched_and_leaves_a_dispatched_one(
    platform, api, store, conn
):
    async with api() as hr:
        _, waiting = await submit(hr, store, [A])
        await hr.delete("/v1/documents/A")
        ended = (await hr.get(f"/v1/requests/{of(waiting.json(), 'A')['request_id']}")).json()
    starts = await dispatch_due(conn, started)

    assert (ended["state"], ended["error"]["reason"]) == ("failed", "DOCUMENT_DELETED")
    assert ended["error"]["message"] == deletion.DOCUMENT_DELETED["message"]
    assert starts == 0  # nothing of the deleted Document is started


async def test_15_a_late_success_of_a_deleted_document_does_not_restore_it(
    platform, api, store, conn
):
    async with api() as hr:
        declared, finalized = await submit(hr, store, [A])
        uid, request_id = of(declared, "A")["document_uid"], of(finalized.json(), "A")["request_id"]
        assert await dispatch_due(conn, started) == 1
        await hr.delete("/v1/documents/A")
        running = (await hr.get(f"/v1/requests/{request_id}")).json()
        late = await record_outcome(
            conn, request_id, "succeeded", None, None, candidate(uid, request_id)
        )
        seen = (await hr.get("/v1/documents/A")).json()
    await build(api, "retrieval")
    publish = await registered(api, "retrieval", fact(uid, "srv", 1, canonical_revision_id="crv"))
    state = await feed.document_state(conn, uid, None)

    assert running["state"] == "queued"  # dispatched before the deletion: it runs on
    assert late  # the result is recorded
    assert seen["readiness"] == "deleted"
    assert state and state.current is None
    assert publish.status_code == 409


async def test_19_a_deleted_document_and_its_delete_request_are_404_after_30_days(
    platform, api, store, conn
):
    async with api() as hr:
        await submit(hr, store, [A])
        deleted = (await hr.delete("/v1/documents/A")).json()
        await conn.execute("UPDATE document SET deleted_at = deleted_at - interval '31 days'")
        document = await hr.get("/v1/documents/A")
        request = await hr.get(f"/v1/requests/{deleted['request_id']}")
        again = await hr.delete("/v1/documents/A")
        unknown = await hr.delete("/v1/documents/nothing")
    async with api("fin-km") as other:
        theirs = await other.delete("/v1/documents/A")

    assert [r.status_code for r in (document, request, again, unknown, theirs)] == [404] * 5


async def test_sc15_a_registered_write_holds_the_deletion_until_it_is_removed(api, conn):
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await build(api, "retrieval")
    assert (await registered(api, "retrieval", fact(uid, srv, 1))).status_code == 200
    async with api("s1") as source:
        await source.delete("/v1/documents/A")

    pending = await enforce(conn)
    await included(api, "retrieval", fact(uid, srv, 2))  # the write confirmed after the deletion
    landed = await enforce(conn)
    await included(api, "retrieval", fact(uid, srv, 3, state="removed"))
    removed = await enforce(conn)

    assert (pending, landed, removed) == ({"held": 1}, {"held": 1}, {"enforced": 1})


async def test_no_judgment_while_a_build_has_no_liveness(api, conn):
    uid, srv = await document(conn)
    await build(api, "retrieval")
    async with api("s1") as source:
        await source.delete("/v1/documents/A")
    later = datetime.now(UTC) + timedelta(seconds=PIPELINES["retrieval"].update_interval_s + 1)

    assert await enforce(conn, later) == {"suspended_liveness": 1}
    assert await enforce(conn) == {"enforced": 1}  # the Build reported within its interval


async def test_sc20r_no_judgment_after_lost_writes_until_repaired_and_an_interval_passed(api, conn):
    uid, srv = await document(conn)
    await build(api, "retrieval")
    async with api("s1") as source:
        await source.delete("/v1/documents/A")
    await serving.lose_writes(conn, 1)

    unrepaired = await enforce(conn)
    # The repair #260 installs when the owner's view arrives.
    await conn.execute("UPDATE build SET repair_reason = NULL, repair_requested_at = NULL")
    within = await enforce(conn)
    interval = PIPELINES["retrieval"].update_interval_s + 1
    await conn.execute(
        "UPDATE writes_lost SET applied_at = applied_at - %s * interval '1 second'", (interval,)
    )
    after = await enforce(conn)

    assert unrepaired == within == {"suspended_writes_lost": 1}
    assert after == {"enforced": 1}


async def test_deletions_past_the_target_are_measured_by_why_they_wait(api, conn):
    held, srv = await document(conn)
    await accepted(conn, held, srv)
    await build(api, "retrieval")
    await included(api, "retrieval", fact(held, srv, 1))
    await document(conn, "B")
    async with api("s1") as source:
        await source.delete("/v1/documents/A")
        await source.delete("/v1/documents/B")
    await conn.execute("UPDATE document SET deleted_at = deleted_at - interval '11 minutes'")

    await enforce(conn)
    await gauges.observe(conn)
    held_now = REGISTRY.get_sample_value("kp_admission_deletions_unenforced", {"reason": "held"})
    later = datetime.now(UTC) + timedelta(seconds=PIPELINES["retrieval"].update_interval_s + 1)
    await enforce(conn, later)
    await gauges.observe(conn)
    labels = {"reason": "liveness"}

    assert held_now == 1  # B, held by nothing, was enforced
    assert REGISTRY.get_sample_value("kp_admission_deletions_unenforced", labels) == 1
    assert REGISTRY.get_sample_value(
        "kp_admission_job_last_run_timestamp_seconds", {"job": "enforce"}
    )
