"""Projection report intake (#252, admission spec §7.4, canonical consumption DR §4–§5): Builds,
registrations, serving facts, heartbeats, attempts and backfill reports over the platform API
with a real database, and the readiness, serving and attention a Source then reads. The tests
send what a projection would (#127 is not built), accept through #251's acceptance, and set
what #98 and #205 will write."""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import psycopg
import pytest
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from kp_admission import adoption, feed, serving, status
from kp_admission.api import app
from kp_admission.batches import Intake
from kp_admission.reports import Pipeline
from kp_admission.requests import record_outcome
from kp_admission.storage import FakeObjectStore
from tests.admission.authz_fake import FakeAuthorizer
from tests.admission.support import FILES, INTAKE, candidate, resource
from tests.admission.test_batches import PDF, file, item, submit
from tests.admission.test_status import PLATFORM, REJECTED, credential, digest, document

pytestmark = pytest.mark.docker

PIPELINES = {
    name: Pipeline(
        pipeline_id=f"kp-{name}",
        track=name,
        stages=["read", "index"],
        start_deadline_s=600,
        update_interval_s=600,
    )
    for name in ("retrieval", "wiki", "canonical")
}
RESOURCE = "s1/hr-all"  # the Resource test_status.document binds its Documents to


@pytest.fixture
async def pool(dsn):
    async with AsyncConnectionPool(dsn, kwargs={"autocommit": True}) as connections:
        yield connections


@pytest.fixture
def api(pool):
    """A client per bearer token: `s1` is the Source, a pipeline's track its reporter."""
    application = app(
        FakeAuthorizer(),
        {digest(track): track for track in PIPELINES},  # one credential reads and reports (C1)
        {digest("s1"): credential("s1")},
        pool,
        INTAKE,
        pipelines={digest(track): p for track, p in PIPELINES.items()},
    )

    def connect(token: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(application),
            base_url="http://api",
            headers={"authorization": f"Bearer {token}"},
        )

    return connect


async def profile(conn, *projections: str) -> str:
    return await feed.set_profile(
        conn, tenant_id="t1", source_id="s1", projections=list(projections)
    )


async def accepted(conn, uid: str, srv: str, crv: str = "crv_1") -> None:
    """Canonical Acceptance (#251) of a run of Source Revision `srv` whose Canonical Revision is
    `crv`: it becomes the Document's current one."""
    request_id = "req_" + crv.removeprefix("crv_")
    await conn.execute(
        "INSERT INTO request (request_id, tenant_id, kind, document_uid, source_revision_id, state,"
        " initiator, priority, adopted_version, adoption_sequence, trace_id) VALUES"
        " (%s, 't1', 'process', %s, %s, 'processing', 'source', 'normal', 'paper-pdf@1', 7, 't')",
        (request_id, uid, srv),
    )
    assert await record_outcome(
        conn, request_id, "succeeded", None, None, candidate(uid, request_id)
    )


async def revised(conn, uid: str, srv: str, version: str = "2") -> None:
    """A newer Source Revision of the Document, its latest, as finalization leaves it."""
    await conn.execute(
        "INSERT INTO source_revision (source_revision_id, tenant_id, document_uid,"
        " source_version, files, sequence) SELECT %s, 't1', %s, %s, %s, max(sequence) + 1"
        " FROM source_revision WHERE document_uid = %s",
        (srv, uid, version, Jsonb(FILES), uid),
    )
    await conn.execute(
        "UPDATE document SET latest_source_revision_id = %s WHERE document_uid = %s", (srv, uid)
    )
    await status.refresh(conn, [uid])


def fact(uid: str, srv: str, version: int, **fields: Any) -> dict[str, Any]:
    return {
        "document_uid": uid,
        "resource_id": RESOURCE,
        "source_revision_id": srv,
        "canonical_revision_id": "crv_1",
        "fact_version": version,
        "issued_at": "2026-11-22T08:00:00Z",
    } | fields


async def build(
    api, projection: str, build_id: str = "b1", state: str = "serving", **fields: Any
) -> httpx.Response:
    """The projection's Build state report; a `serving` one is caught up with the feed."""
    body: dict[str, Any] = {"state": state}
    if state == "serving":
        async with api(projection) as reader:
            head = (await reader.get("/read/v1/feed")).json()["next_cursor"]
        body |= {"switch_seq": 1, "replaces": None, "feed_position": head}
    async with api(projection) as reporter:
        return await reporter.put(f"/report/v1/builds/{build_id}", json=body | fields)


async def post(api, projection: str, path: str, body: dict[str, Any]) -> httpx.Response:
    async with api(projection) as reporter:
        return await reporter.post(f"/report/v1/builds/{path}", json=body)


async def included(api, projection: str, *facts: dict[str, Any], build_id: str = "b1"):
    body = {"facts": [f | {"state": f.get("state", "included")} for f in facts]}
    return await post(api, projection, f"{build_id}/facts", body)


async def seen(api, document_id: str = "A") -> dict[str, Any]:
    async with api("s1") as source:
        return (await source.get(f"/v1/documents/{document_id}")).json()


def states(view: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(s["projection"], s["state"], s["source_version"]) for s in view["serving"]]


async def test_readiness_follows_the_included_facts_of_every_required_projection(api, conn):
    uid, srv = await document(conn)
    await profile(conn, "retrieval", "wiki")
    assert (await build(api, "retrieval")).status_code == 200
    assert (await build(api, "wiki")).status_code == 200
    before = await seen(api)

    first = await included(api, "retrieval", fact(uid, srv, 1))
    one = await seen(api)
    await included(api, "wiki", fact(uid, srv, 1))
    both = await seen(api)
    await revised(conn, uid, "srv_2")
    stale = await seen(api)
    await included(api, "retrieval", fact(uid, "srv_2", 2))
    behind = await seen(api)
    await included(api, "wiki", fact(uid, "srv_2", 2))
    caught_up = await seen(api)

    assert first.status_code == 200
    assert first.json() == {"fenced": [], "repair_requested": None}
    assert (before["readiness"], before["serving"]) == ("not_ready", [])
    assert (one["readiness"], states(one)) == ("not_ready", [("retrieval", "ready", "1")])
    assert both["readiness"] == "ready"
    assert both["serving"] == [
        {"projection": "retrieval", "state": "ready", "source_revision_id": srv,
         "source_version": "1"},
        {"projection": "wiki", "state": "ready", "source_revision_id": srv, "source_version": "1"},
    ]  # fmt: skip
    assert stale["readiness"] == "ready_stale"
    assert states(stale) == [("retrieval", "stale", "1"), ("wiki", "stale", "1")]
    assert behind["readiness"] == "ready_stale"
    assert states(behind) == [("retrieval", "ready", "2"), ("wiki", "stale", "1")]
    assert (caught_up["readiness"], caught_up["latest"]["source_version"]) == ("ready", "2")


async def test_since_is_when_readiness_last_changed(api, conn):
    uid, srv = await document(conn)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    created = (await seen(api))["since"]

    await included(api, "retrieval", fact(uid, srv, 1))
    ready = await seen(api)
    await included(api, "retrieval", fact(uid, srv, 1))  # a resend changes nothing
    resent = await seen(api)
    await revised(conn, uid, "srv_2")
    stale = await seen(api)

    assert created < ready["since"] < stale["since"]
    assert (ready["readiness"], stale["readiness"]) == ("ready", "ready_stale")
    assert resent["since"] == ready["since"]


async def test_the_highest_fact_version_wins_and_a_removed_fact_ends_serving(api, conn):
    uid, srv = await document(conn)
    await profile(conn, "retrieval")
    await build(api, "retrieval")

    await included(api, "retrieval", fact(uid, srv, 5))
    removed = await included(api, "retrieval", fact(uid, srv, 7, state="removed"))
    late = await included(api, "retrieval", fact(uid, srv, 6))  # issued before the removal
    after = await seen(api)

    assert (removed.status_code, late.status_code) == (200, 200)
    assert late.json()["fenced"] == []
    assert (after["readiness"], after["serving"]) == ("not_ready", [])


async def test_only_a_serving_build_counts_and_a_switch_moves_readiness(api, conn):
    uid, srv = await document(conn)
    await profile(conn, "retrieval")
    await build(api, "retrieval", "b1")
    await included(api, "retrieval", fact(uid, srv, 1))
    await build(api, "retrieval", "b2", state="building")
    await revised(conn, uid, "srv_2")
    await included(api, "retrieval", fact(uid, "srv_2", 1), build_id="b2")
    candidate = await seen(api)

    switched = await build(api, "retrieval", "b2", switch_seq=2, replaces="b1")
    after = await seen(api)
    late = await build(api, "retrieval", "b1")  # the first switch's report, delivered again
    retired = await build(api, "retrieval", "b1", state="retired")

    assert (candidate["readiness"], states(candidate)) == (
        "ready_stale",
        [("retrieval", "stale", "1")],
    )
    assert (switched.status_code, switched.json()["state"]) == (200, "serving")
    assert (after["readiness"], states(after)) == ("ready", [("retrieval", "ready", "2")])
    assert after["since"] > candidate["since"]
    assert (late.status_code, late.json()["state"]) == (200, "retained")
    assert (retired.status_code, retired.json()["state"]) == (200, "retired")
    assert (await seen(api))["readiness"] == "ready"


async def test_serving_shows_a_source_version_overwritten_after_the_fact(api, conn):
    """#258: the same content sent again with a higher source_version rewrites the Source
    Revision's version, and serving reads it when it answers."""
    uid, srv = await document(conn)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 1))

    await conn.execute("UPDATE source_revision SET source_version = '9'")
    after = await seen(api)

    assert states(after) == [("retrieval", "ready", "9")]
    assert after["latest"]["source_version"] == "9"


async def test_the_projection_filter_lists_the_documents_it_serves(api, conn):
    uid, srv = await document(conn, "A")
    await document(conn, "B")
    await profile(conn, "retrieval", "wiki")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 1))

    async with api("s1") as source:
        served = (await source.get("/v1/documents", params={"projection": "retrieval"})).json()
        by_wiki = (await source.get("/v1/documents", params={"projection": "wiki"})).json()

    assert [d["document_id"] for d in served["documents"]] == ["A"]
    assert by_wiki["documents"] == []


async def test_reports_come_from_a_registered_projection_about_a_build_it_reported(api, conn):
    uid, srv = await document(conn)
    body = {"facts": [fact(uid, srv, 1) | {"state": "included"}]}

    unknown = await post(api, "retrieval", "b1/facts", body)
    by_canonical = await post(api, "canonical", "b1/facts", body)
    by_a_source = await post(api, "s1", "b1/facts", body)
    invalid = await post(api, "retrieval", "b1/facts", {"facts": [fact(uid, srv, 0)]})

    assert (unknown.status_code, unknown.json()["error"]["details"][0]["reason"]) == (
        404,
        "NOT_FOUND",
    )
    assert (by_canonical.status_code, by_a_source.status_code) == (403, 401)
    assert invalid.status_code == 400


async def backfilled(api, projection: str, profile_seq: str, source_id: str = "s1"):
    async with api(projection) as reporter:
        body = {"profile_seq": profile_seq}
        return await reporter.put(f"/report/v1/sources/{source_id}/backfill", json=body)


async def test_an_added_projection_counts_once_its_backfill_is_reported(api, conn):
    """Prototype scenario 17 (admission design, acceptance row 20)."""
    uid, srv = await document(conn)
    first = await profile(conn, "retrieval")
    await build(api, "retrieval")
    await revised(conn, uid, "srv_2")
    await included(api, "retrieval", fact(uid, "srv_2", 1))
    added = await profile(conn, "retrieval", "wiki")
    await build(api, "wiki")
    await included(api, "wiki", fact(uid, srv, 1))
    backfilling = await seen(api)

    early = await backfilled(api, "wiki", first)  # before the profile that added it
    still = await seen(api)
    done = await backfilled(api, "wiki", added)
    counted = await seen(api)
    ahead = await backfilled(api, "wiki", "f" * 32)
    unknown = await backfilled(api, "wiki", added, source_id="s9")

    assert backfilling["readiness"] == "ready"
    assert states(backfilling) == [("retrieval", "ready", "2"), ("wiki", "building", "1")]
    assert (early.status_code, still["readiness"]) == (204, "ready")
    assert done.status_code == 204
    assert counted["readiness"] == "ready_stale"
    assert states(counted) == [("retrieval", "ready", "2"), ("wiki", "stale", "1")]
    assert counted["since"] > backfilling["since"]
    assert (ahead.status_code, unknown.status_code) == (400, 404)


async def test_a_projection_dropped_from_the_profile_stops_counting(api, conn):
    uid, srv = await document(conn)
    await profile(conn, "retrieval", "wiki")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 1))
    before = await seen(api)

    await profile(conn, "retrieval")
    await status.refresh_source(conn, "s1")  # what the set-profile command runs after it
    after = await seen(api)

    assert (before["readiness"], after["readiness"]) == ("not_ready", "ready")
    assert after["since"] > before["since"]


async def registered(api, projection: str, *facts: dict[str, Any], build_id: str = "b1"):
    return await post(api, projection, f"{build_id}/registrations", {"facts": list(facts)})


async def test_a_registration_passes_the_check_or_records_nothing(api, conn):
    """DR §5.2, K1: a Wiki page registers one fact per source, all or none."""
    a, srv_a = await document(conn, "A")
    b, srv_b = await document(conn, "B")
    gone, srv_gone = await document(conn, "C")
    moved, srv_moved = await document(conn, "D")
    for i, (uid, srv) in enumerate(((a, srv_a), (b, srv_b), (gone, srv_gone), (moved, srv_moved))):
        await accepted(conn, uid, srv, f"crv_{i + 1}")
    await conn.execute("UPDATE document SET deleted_at = now() WHERE document_uid = %s", (gone,))
    await conn.execute(
        "UPDATE document SET resource_id = 's1/finance' WHERE document_uid = %s", (moved,)
    )
    await profile(conn, "wiki")
    await build(api, "wiki")

    older = await registered(
        api, "wiki", fact(a, srv_a, 1), fact(b, srv_b, 1, canonical_revision_id="crv_0")
    )
    deleted = await registered(api, "wiki", fact(gone, srv_gone, 2, canonical_revision_id="crv_3"))
    out = await registered(api, "wiki", fact(moved, srv_moved, 3, canonical_revision_id="crv_4"))
    nothing = [await serving.held(conn, uid) for uid in (a, b, gone, moved)]
    page = await registered(
        api, "wiki", fact(a, srv_a, 4), fact(b, srv_b, 4, canonical_revision_id="crv_2")
    )
    pending = await seen(api, "A")

    for refused, uid in ((older, b), (deleted, gone), (out, moved)):
        assert refused.status_code == 409
        detail = refused.json()["error"]["details"][0]
        assert (detail["reason"], detail["metadata"]) == ("SUPERSEDED", {"document_uid": uid})
    assert nothing == [[], [], [], []]
    assert (page.status_code, page.json()) == (200, {"repair_requested": None})
    assert await serving.held(conn, a) == [("wiki", "b1", RESOURCE, "pending")]
    assert (pending["readiness"], pending["serving"]) == ("not_ready", [])  # pending serves nothing


async def test_a_write_confirmed_after_the_deletion_stays_held_until_removed(api, conn):
    """SC15: the write is done and its confirmation in flight when the Document is deleted."""
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await registered(api, "retrieval", fact(uid, srv, 1))

    await conn.execute("UPDATE document SET deleted_at = now() WHERE document_uid = %s", (uid,))
    during = await serving.held(conn, uid)
    await included(api, "retrieval", fact(uid, srv, 2))  # the confirmation, a fresh version
    landed = await serving.held(conn, uid)
    again = await registered(api, "retrieval", fact(uid, srv, 3))
    await included(api, "retrieval", fact(uid, srv, 4, state="removed"))

    assert during == [("retrieval", "b1", RESOURCE, "pending")]
    assert landed == [("retrieval", "b1", RESOURCE, "included")]
    assert again.status_code == 409  # no new write of a deleted Document
    assert await serving.held(conn, uid) == []


async def test_serving_counts_only_within_the_documents_current_resource(api, conn):
    """Prototype scenario 16 (admission design, acceptance row 19): after a rebind the Document
    is not_ready until the projection includes it in its new Resource."""
    uid, srv = await document(conn)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 1))
    before = await seen(api)

    await conn.execute(
        "UPDATE document SET resource_id = 's1/finance' WHERE document_uid = %s", (uid,)
    )
    await status.refresh(conn, [uid])  # what #205's rebind runs after it
    moved = await seen(api)
    await included(api, "retrieval", fact(uid, srv, 2, resource_id="s1/finance"))
    after = await seen(api)

    assert before["readiness"] == "ready"
    assert (moved["readiness"], moved["serving"]) == ("not_ready", [])
    assert (after["readiness"], states(after)) == ("ready", [("retrieval", "ready", "1")])
    assert await serving.held(conn, uid) == [
        ("retrieval", "b1", "s1/finance", "included"),
        ("retrieval", "b1", RESOURCE, "included"),  # the move out is not complete (C3)
    ]


async def beat(api, projection: str, *entries: tuple[str, str, str], build_id: str = "b1"):
    body = {"count": len(entries), "digest": serving.digest(entries)}
    return await post(api, projection, f"{build_id}/heartbeats", body)


async def aged(conn, uid: str, interval: str) -> None:
    """The Document's facts as if recorded `interval` ago."""
    await conn.execute(
        "UPDATE serving_fact SET recorded_at = now() - %s::interval WHERE document_uid = %s",
        (interval, uid),
    )


def test_the_heartbeat_digest_is_the_xor_of_each_entrys_sha256():
    entry = ("doc_1", "s1/hr-all", "crv_1")
    other = ("doc_2", "s1/hr-all", "crv_1")
    one = hashlib.sha256(b"doc_1\x1fs1/hr-all\x1fcrv_1").hexdigest()

    assert serving.digest([]) == "0" * 64
    assert serving.digest([entry]) == one
    assert serving.digest([entry, other]) == serving.digest([other, entry])
    assert serving.digest([entry, other, other]) == one


async def test_an_old_report_after_a_tombstone_expired_is_fenced(api, conn):
    """SC19: a removal's tombstone expired; an `included` issued before it expired comes late."""
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 100, state="removed"))
    before_expiry = await included(api, "retrieval", fact(uid, srv, 99))  # a control: just older

    await aged(conn, uid, "31 days")
    issued = (datetime.now(UTC) - timedelta(days=40)).isoformat()  # before the removal, even
    late = await included(api, "retrieval", fact(uid, srv, 99, issued_at=issued))
    late_write = await registered(api, "retrieval", fact(uid, srv, 98, issued_at=issued))
    held = await serving.held(conn, uid)
    asked = await beat(api, "retrieval")
    fresh = await included(api, "retrieval", fact(uid, srv, 101))

    assert before_expiry.json() == {"fenced": [], "repair_requested": None}
    assert late.status_code == 200
    assert late.json()["fenced"] == [{"document_uid": uid, "resource_id": RESOURCE}]
    assert late.json()["repair_requested"]["reason"] == "fenced"
    assert gate(late_write) == (409, "FENCED", {"document_uid": uid})
    assert held == []
    assert asked.json()["repair_requested"]["reason"] == "fenced"  # until #260 repairs
    assert await serving.held(conn, uid) == [("retrieval", "b1", RESOURCE, "included")]
    assert fresh.json()["fenced"] == []


async def test_a_heartbeat_that_disagrees_with_the_mirror_requests_a_repair(api, conn):
    """SC20u: the mirror drifts silently, with the same count."""
    uid, srv = await document(conn)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 1))
    entry = (uid, RESOURCE, "crv_1")
    agrees = await beat(api, "retrieval", entry)

    await conn.execute("UPDATE serving_fact SET canonical_revision_id = 'crv_0'")
    drifted = await beat(api, "retrieval", entry)
    next_report = await included(api, "retrieval", fact(uid, srv, 2))

    assert (agrees.status_code, agrees.json()) == (200, {"repair_requested": None})
    asked = drifted.json()["repair_requested"]
    assert asked["reason"] == "heartbeat_mismatch"
    assert next_report.json()["repair_requested"] == asked


async def test_a_pending_fact_past_pending_max_requests_a_repair(api, conn):
    """SC22: the write succeeded, and its confirmation was lost in a crash."""
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "wiki")
    await build(api, "wiki")
    await registered(api, "wiki", fact(uid, srv, 1))
    entry = (uid, RESOURCE, "crv_1")
    young = await beat(api, "wiki", entry)

    await aged(conn, uid, "31 minutes")
    old = await beat(api, "wiki", entry)

    assert young.json() == {"repair_requested": None}
    assert old.json()["repair_requested"]["reason"] == "pending_expired"


def attempt(uid: str, srv: str, attempt_no: int, seq: int, state: str, **fields: Any):
    """A projection's status report for the Document's Canonical Revision crv_1."""
    return {
        "document_uid": uid,
        "source_revision_id": srv,
        "canonical_revision_id": "crv_1",
        "attempt_no": attempt_no,
        "attempt_id": f"run-{attempt_no}",
        "seq": seq,
        "stages_version": "1",
        "stage": "index",
        "state": state,
        "progress": None,
        "message": "",
        "method_version": "retrieval@3",
        "manifest_ref": None,
        "observed_at": "2026-11-22T08:00:00Z",
        "error": None,
    } | fields


async def tried(api, projection: str, body: dict[str, Any], build_id: str = "b1"):
    return await post(api, projection, f"{build_id}/status-reports", body)


def kinds(view: dict[str, Any]) -> list[tuple[str, str, str | None]]:
    return [(a["kind"], a["action_owner"], a.get("track")) for a in view["attention"]]


async def test_a_unit_takes_the_reports_of_its_highest_attempt_in_seq_order(api, conn):
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "retrieval")
    await build(api, "retrieval")

    first = await tried(api, "retrieval", attempt(uid, srv, 1, 1, "running"))
    retry = await tried(api, "retrieval", attempt(uid, srv, 2, 1, "pending"))
    gap = await tried(api, "retrieval", attempt(uid, srv, 2, 3, "running"))
    resent = await tried(api, "retrieval", attempt(uid, srv, 2, 3, "running"))
    behind = await tried(api, "retrieval", attempt(uid, srv, 2, 2, "running"))
    older = await tried(api, "retrieval", attempt(uid, srv, 1, 2, "succeeded"))
    bad = await tried(api, "retrieval", attempt(uid, srv, 2, 4, "running", stage="parse"))
    no_error = await tried(api, "retrieval", attempt(uid, srv, 2, 4, "failed"))

    assert [r.status_code for r in (first, retry, gap, resent)] == [202, 202, 202, 200]
    assert behind.status_code == older.status_code == 409
    assert behind.json() == older.json() == {"attempt_no": 2, "seq": 3}
    assert bad.status_code == no_error.status_code == 400


async def test_a_projection_failure_shows_until_the_latest_revision_is_served(api, conn):
    """DR C4: only the serving Build's attempt for the current Canonical Revision counts, and a
    failure is suppressed while the latest Source Revision is served."""
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await build(api, "retrieval", "b2", state="building")
    await tried(api, "retrieval", attempt(uid, srv, 1, 1, "failed", error=PLATFORM), "b2")
    building = await seen(api)

    await tried(api, "retrieval", attempt(uid, srv, 1, 1, "failed", error=PLATFORM))
    failed = await seen(api)
    await included(api, "retrieval", fact(uid, srv, 1))
    served = await seen(api)

    assert building["attention"] == []
    assert kinds(failed) == [("processing_failed", "platform", "retrieval")]
    assert failed["attention"][0]["message"] == status.PLATFORM_FAILURE
    assert failed["attention"][0]["source_version"] == "1"
    assert served["attention"] == []


async def test_a_skip_names_who_acts_from_its_cause(api, conn):
    a, srv_a = await document(conn, "A")
    b, srv_b = await document(conn, "B")
    await accepted(conn, a, srv_a)
    await accepted(conn, b, srv_b, "crv_2")
    await profile(conn, "wiki")
    await build(api, "wiki")

    await tried(api, "wiki", attempt(a, srv_a, 1, 1, "skipped", error=REJECTED))
    await tried(
        api,
        "wiki",
        attempt(b, srv_b, 1, 1, "skipped", error=PLATFORM, canonical_revision_id="crv_2"),
    )
    by_source, by_platform = await seen(api, "A"), await seen(api, "B")

    assert kinds(by_source) == [("skipped", "source", "wiki")]
    assert by_source["attention"][0]["message"] == REJECTED["message"]
    assert kinds(by_platform) == [("skipped", "platform", "wiki")]
    assert by_platform["attention"][0]["message"] == status.PLATFORM_FAILURE


async def test_a_silent_attempt_is_stalled_and_a_silent_build_unverified(api, conn):
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    # A stage that is not the pipeline's last one succeeded: the attempt goes on.
    await tried(api, "retrieval", attempt(uid, srv, 1, 1, "succeeded", stage="read"))
    reporting = await seen(api)

    await conn.execute("UPDATE projection_attempt SET reported_at = now() - interval '11 minutes'")
    stalled = await seen(api)
    await conn.execute("UPDATE build SET reported_at = now() - interval '11 minutes'")
    unverified = await seen(api)
    now = datetime.now(UTC)
    lost = await serving.silent(conn, {p.track: p for p in PIPELINES.values()}, now)
    await tried(api, "retrieval", attempt(uid, srv, 1, 2, "succeeded"))  # the last stage
    ended = await seen(api)

    assert reporting["attention"] == []
    assert ended["attention"] == []  # the attempt ended, and the report is a liveness signal
    assert kinds(stalled) == [("progress_stalled", "platform", "retrieval")]
    assert kinds(unverified) == [
        ("progress_stalled", "platform", "retrieval"),
        ("status_unverified", "platform", "retrieval"),
    ]
    assert lost == [("retrieval", "b1")]


def gate(response: httpx.Response) -> tuple[int, str, dict[str, str]]:
    detail = response.json()["error"]["details"][0]
    return response.status_code, detail["reason"], detail.get("metadata", {})


async def test_a_switch_that_fails_a_gate_changes_nothing(api, conn):
    """DR D2: the platform re-runs the mechanical gates on `serving`."""
    a, srv_a = await document(conn, "A")
    b, srv_b = await document(conn, "B")
    await profile(conn, "retrieval")
    await build(api, "retrieval", "b1")
    await included(api, "retrieval", fact(a, srv_a, 1), fact(b, srv_b, 1))
    await build(api, "retrieval", "b2", state="building")
    await included(api, "retrieval", fact(a, srv_a, 1), build_id="b2")

    async with api("retrieval") as reader:
        behind = (await reader.get("/read/v1/feed")).json()["next_cursor"]
    await profile(conn, "retrieval", "wiki")  # an event the candidate has not read
    await conn.execute("UPDATE change_feed SET occurred_at = now() - interval '6 minutes'")
    lagging = await build(api, "retrieval", "b2", switch_seq=2, replaces="b1", feed_position=behind)
    wrong = await build(api, "retrieval", "b2", switch_seq=2, replaces="b9")
    short = await build(api, "retrieval", "b2", switch_seq=2, replaces="b1")
    await included(api, "retrieval", fact(b, srv_b, 2), build_id="b2")
    await conn.execute("UPDATE document SET deleted_at = now() WHERE document_uid = %s", (b,))
    stray = await build(api, "retrieval", "b2", switch_seq=2, replaces="b1")
    garbled = await build(api, "retrieval", "b2", switch_seq=2, replaces="b1", feed_position="x")
    ahead = await build(api, "retrieval", "b2", switch_seq=2, replaces="b1", feed_position="f" * 32)
    after = await seen(api, "A")

    assert gate(lagging) == (409, "GATE_FAILED", {"gate": "caught_up"})
    assert gate(wrong) == (409, "GATE_FAILED", {"gate": "replaces"})
    assert gate(short) == (409, "GATE_FAILED", {"gate": "coverage"})
    assert gate(stray) == (409, "GATE_FAILED", {"gate": "removed_documents"})
    assert garbled.status_code == ahead.status_code == 400
    assert states(after) == [("retrieval", "ready", "1")]  # b1 still serves


async def test_a_build_moves_only_forward_and_its_owner_retires_it(api, conn):
    await profile(conn, "retrieval")
    first = await build(api, "retrieval", "b1", state="building")
    back = await build(api, "retrieval", "b1", state="retained")  # the platform retains it
    await build(api, "retrieval", "b1")
    rebuilt = await build(api, "retrieval", "b1", state="building")
    retired = await build(api, "retrieval", "b1", state="retired")
    revived = await build(api, "retrieval", "b1", switch_seq=5)
    no_switch = await build(api, "retrieval", "b2", state="building")
    unnumbered = await build(api, "retrieval", "b2", state="serving", switch_seq=None)

    assert (first.status_code, first.json()) == (
        200,
        {"state": "building", "repair_requested": None},
    )
    for refused, was in ((back, "building"), (rebuilt, "serving"), (revived, "retired")):
        assert gate(refused) == (409, "BUILD_STATE", {"state": was})
    assert retired.json()["state"] == "retired"
    assert no_switch.status_code == 200
    assert unnumbered.status_code == 400


async def test_a_finalized_revision_makes_a_ready_document_stale_from_that_moment(pool, conn):
    store = FakeObjectStore()
    application = app(
        FakeAuthorizer(),
        {digest("retrieval"): "retrieval"},
        {digest("s1"): credential("s1")},
        pool,
        Intake(store),
        pipelines={digest("retrieval"): PIPELINES["retrieval"]},
    )

    def api(token: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(application),
            base_url="http://api",
            headers={"authorization": f"Bearer {token}"},
        )

    await resource(conn, RESOURCE)
    await adoption.adopt(conn, tenant_id="t1", media_type=PDF, version="paper-pdf@1")
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    async with api("s1") as source:
        _, first = await submit(source, store, [item("A", "1", file("a.pdf", "a-1", PDF))])
    uid = first.json()["items"][0]["document_uid"]
    srv = (await seen(api))["latest"]["source_revision_id"]
    await included(api, "retrieval", fact(uid, srv, 1))
    ready = await seen(api)

    async with api("s1") as source:
        _, second = await submit(source, store, [item("A", "2", file("a.pdf", "a-2", PDF))])
    stale = await seen(api)

    assert second.status_code == 202
    assert (ready["readiness"], stale["readiness"]) == ("ready", "ready_stale")
    assert stale["since"] > ready["since"]
    assert states(stale) == [("retrieval", "stale", "1")]


async def test_a_document_written_over_keeps_its_served_revision_until_confirmed(api, conn):
    """User ruling 2026-11-22: while a projection writes a new revision over the one it serves,
    the old one still counts, so readiness is ready_stale, not not_ready, until the write is
    confirmed; the `pending` fact still blocks a deletion's judgment."""
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 1))
    ready = await seen(api)

    await revised(conn, uid, "srv_2")
    await accepted(conn, uid, "srv_2", "crv_2")
    stale = await seen(api)
    await registered(api, "retrieval", fact(uid, "srv_2", 2, canonical_revision_id="crv_2"))
    writing = await seen(api)
    held = await serving.held(conn, uid)
    await included(api, "retrieval", fact(uid, "srv_2", 3, canonical_revision_id="crv_2"))
    written = await seen(api)

    assert [v["readiness"] for v in (ready, stale, writing, written)] == [
        "ready", "ready_stale", "ready_stale", "ready"
    ]  # fmt: skip
    assert states(writing) == [("retrieval", "stale", "1")]
    assert held == [("retrieval", "b1", RESOURCE, "pending")]
    assert ready["since"] < stale["since"] == writing["since"] < written["since"]


async def test_an_abandoned_write_over_a_served_revision_reports_what_the_store_holds(api, conn):
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 1))
    await revised(conn, uid, "srv_2")
    await accepted(conn, uid, "srv_2", "crv_2")
    await registered(api, "retrieval", fact(uid, "srv_2", 2, canonical_revision_id="crv_2"))

    await included(api, "retrieval", fact(uid, srv, 3))  # the write failed; srv_1 is stored
    after = await seen(api)

    assert (after["readiness"], states(after)) == ("ready_stale", [("retrieval", "stale", "1")])
    assert await serving.held(conn, uid) == [("retrieval", "b1", RESOURCE, "included")]


async def test_a_build_writing_over_served_revisions_keeps_its_coverage(api, conn):
    """The coverage gate counts what a Build serves, so a rewrite under way does not fail it."""
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "retrieval")
    await build(api, "retrieval", "b1")
    await included(api, "retrieval", fact(uid, srv, 1))
    await build(api, "retrieval", "b2", state="building")
    await included(api, "retrieval", fact(uid, srv, 1), build_id="b2")
    await registered(api, "retrieval", fact(uid, srv, 2), build_id="b2")

    switched = await build(api, "retrieval", "b2", switch_seq=2, replaces="b1")

    assert (switched.status_code, switched.json()["state"]) == (200, "serving")
    assert (await seen(api))["readiness"] == "ready"


async def test_a_resent_switch_finishes_the_refresh_a_crash_cut_short(api, conn):
    a, srv_a = await document(conn, "A")  # only the replaced Build holds it
    b, srv_b = await document(conn, "B")  # only the new one
    await profile(conn, "retrieval")
    await build(api, "retrieval", "b1")
    await included(api, "retrieval", fact(a, srv_a, 1))
    await build(api, "retrieval", "b2", state="building")
    await included(api, "retrieval", fact(b, srv_b, 1), build_id="b2")
    async with api("retrieval") as reader:
        head = (await reader.get("/read/v1/feed")).json()["next_cursor"]
    switch = {"state": "serving", "switch_seq": 2, "replaces": "b1", "feed_position": head}

    # The switch commits and the api stops before it recomputed the Documents.
    await serving.report_build(conn, "retrieval", "b2", serving.BuildReport(**switch), 600)
    cut = await seen(api, "A"), await seen(api, "B")
    resent = await build(api, "retrieval", "b2", **switch)
    done = await seen(api, "A"), await seen(api, "B")

    assert resent.status_code == 200
    assert [v["readiness"] for v in cut] == [v["readiness"] for v in done] == ["not_ready", "ready"]
    assert done[0]["since"] > cut[0]["since"]
    assert done[1]["since"] > cut[1]["since"]


async def test_two_switches_racing_leave_one_serving_build(api, conn, dsn):
    """Two first switches of a projection, of different Builds, neither seeing the other's row:
    the one that commits second is refused as a retry of it would be."""
    await profile(conn, "retrieval")
    async with await psycopg.AsyncConnection.connect(dsn) as other:  # a transaction, held open
        await other.execute(
            "INSERT INTO build (projection, build_id, state, switch_seq)"
            " VALUES ('retrieval', 'b0', 'serving', 1)"
        )
        racing = asyncio.create_task(build(api, "retrieval", "b1", switch_seq=2))
        await asyncio.sleep(0.3)  # b1's switch now waits for b0's to commit
        await other.commit()
        raced = await racing
    after = await build(api, "retrieval", "b1", state="building")

    assert gate(raced) == (409, "GATE_FAILED", {"gate": "replaces"})
    assert after.json()["state"] == "building"  # 409 BUILD_STATE were b1 serving


async def test_a_registration_naming_a_key_twice_keeps_its_highest_version(api, conn):
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "retrieval")
    await build(api, "retrieval")

    await registered(api, "retrieval", fact(uid, srv, 2), fact(uid, srv, 1))
    await included(api, "retrieval", fact(uid, srv, 2))  # not above the registration: older

    assert (await seen(api))["readiness"] == "not_ready"


async def test_a_retired_build_takes_no_more_reports(api, conn):
    """A registration's 200 permits a store write, and deletion's judgment skips retired Builds."""
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await build(api, "retrieval", state="retired")

    refused = [
        await registered(api, "retrieval", fact(uid, srv, 1)),
        await included(api, "retrieval", fact(uid, srv, 2)),
        await beat(api, "retrieval"),
        await tried(api, "retrieval", attempt(uid, srv, 1, 1, "running")),
    ]

    assert [gate(r) for r in refused] == [(409, "BUILD_STATE", {"state": "retired"})] * 4
    assert await serving.held(conn, uid) == []
