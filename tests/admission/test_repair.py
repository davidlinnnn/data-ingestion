"""Repair of a Build's serving facts (#260, admission spec §7.4, canonical consumption DR §5.4,
§5.6): the projection sends a repair view in pages and the platform replaces the Build's mirror
in one step. The tests send what a projection would (#127 is not built)."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from prometheus_client import REGISTRY

from kp_admission import serving
from tests.admission import test_serving
from tests.admission.test_serving import (
    RESOURCE,
    accepted,
    aged,
    beat,
    build,
    document,
    fact,
    included,
    profile,
    registered,
    seen,
)

api, pool = test_serving.api, test_serving.pool  # its fixtures

pytestmark = pytest.mark.docker
LABELS = {"projection": "retrieval"}


def entry(uid: str, srv: str, version: int, state: str = "included", **fields: Any):
    """A view's entry: a store entry (`included`) or an unfinished registration (`pending`) with
    the fact_version last reported for it."""
    return {
        "document_uid": uid,
        "resource_id": RESOURCE,
        "state": state,
        "source_revision_id": srv,
        "canonical_revision_id": "crv_1",
        "fact_version": version,
    } | fields


async def page(
    api,
    projection: str,
    number: int,
    pages: int,
    watermark: int,
    *entries: dict[str, Any],
    view_id: str = "v1",
    captured_at: datetime | None = None,
    build_id: str = "b1",
):
    body = {
        "captured_at": (captured_at or datetime.now(UTC)).isoformat(),
        "watermark": watermark,
        "pages": pages,
        "entries": list(entries),
    }
    async with api(projection) as reporter:
        return await reporter.put(
            f"/report/v1/builds/{build_id}/repair-views/{view_id}/pages/{number}", json=body
        )


async def test_a_complete_view_replaces_the_mirror_and_ends_the_request(api, conn):
    """SC20u, second half: the mirror drifted, a heartbeat asked for a repair, the view lands."""
    uid, srv = await document(conn, "A")
    other, srv_other = await document(conn, "B")
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 1), fact(other, srv_other, 2))
    stored = [(uid, RESOURCE, "crv_1"), (other, RESOURCE, "crv_1")]
    await conn.execute("UPDATE serving_fact SET canonical_revision_id = 'crv_0'")  # silent drift
    asked = (await beat(api, "retrieval", *stored)).json()["repair_requested"]
    captured = datetime.now(UTC)

    timed = REGISTRY.get_sample_value("kp_serving_repair_seconds_count", LABELS) or 0.0
    last = await page(api, "retrieval", 2, 2, 2, entry(other, srv_other, 2), captured_at=captured)
    first = await page(api, "retrieval", 1, 2, 2, entry(uid, srv, 1), captured_at=captured)
    after = await beat(api, "retrieval", *stored)

    assert asked["reason"] == "heartbeat_mismatch"
    assert last.status_code == 200
    assert last.json() == {"view": "incomplete", "repair_requested": asked}
    assert first.json() == {"view": "installed", "repair_requested": None}
    assert after.json() == {"repair_requested": None}
    assert REGISTRY.get_sample_value("kp_serving_repair_seconds_count", LABELS) == timed + 1


async def test_a_pending_fact_whose_confirmation_was_lost_is_repaired_to_included(api, conn):
    """SC22, second half: the write succeeded and its confirmation was lost in a crash."""
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "wiki")
    await build(api, "wiki")
    await registered(api, "wiki", fact(uid, srv, 1))
    await aged(conn, uid, "31 minutes")
    stored = (uid, RESOURCE, "crv_1")
    asked = (await beat(api, "wiki", stored)).json()["repair_requested"]
    pending = await seen(api)

    installed = await page(api, "wiki", 1, 1, 1, entry(uid, srv, 1))
    repaired = await seen(api)

    assert asked["reason"] == "pending_expired"
    assert pending["readiness"] == "not_ready"
    assert installed.json() == {"view": "installed", "repair_requested": None}
    assert await serving.held(conn, uid) == [("wiki", "b1", RESOURCE, "included")]
    assert repaired["readiness"] == "ready"
    assert repaired["since"] > pending["since"]
    assert (await beat(api, "wiki", stored)).json() == {"repair_requested": None}


async def test_pages_out_of_order_or_repeated_install_the_same_mirror(api, conn):
    a, srv_a = await document(conn, "A")
    b, srv_b = await document(conn, "B")
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    captured = datetime.now(UTC)
    one, two = entry(a, srv_a, 1), entry(b, srv_b, 2)

    second = await page(api, "retrieval", 2, 2, 2, two, captured_at=captured)
    again = await page(api, "retrieval", 2, 2, 2, two, captured_at=captured)
    first = await page(api, "retrieval", 1, 2, 2, one, captured_at=captured)
    resent = await page(api, "retrieval", 1, 2, 2, one, captured_at=captured)
    unlike = await page(api, "retrieval", 1, 2, 3, one, captured_at=captured)
    beyond = await page(api, "retrieval", 3, 2, 2, one, captured_at=captured)

    assert [r.json()["view"] for r in (second, again, first, resent)] == [
        "incomplete", "incomplete", "installed", "installed"
    ]  # fmt: skip
    assert (unlike.status_code, beyond.status_code) == (400, 400)
    agrees = await beat(api, "retrieval", (a, RESOURCE, "crv_1"), (b, RESOURCE, "crv_1"))
    assert agrees.json() == {"repair_requested": None}


async def test_a_write_retried_across_a_repair_converges(api, conn):
    """SC21: a registration's write is delayed and another key's report passes it; the view is
    captured before the write lands, and the write's confirmation, at a fresh version, arrives
    while the view is in transfer."""
    a, srv_a = await document(conn, "A")
    b, srv_b = await document(conn, "B")
    await accepted(conn, a, srv_a)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await registered(api, "retrieval", fact(a, srv_a, 27))
    await included(api, "retrieval", fact(b, srv_b, 28))
    captured = datetime.now(UTC)

    await page(api, "retrieval", 1, 2, 28, entry(a, srv_a, 27, "pending"), captured_at=captured)
    landed = await included(api, "retrieval", fact(a, srv_a, 29))  # the confirmation, fresh
    last = await page(api, "retrieval", 2, 2, 28, entry(b, srv_b, 28), captured_at=captured)
    stale = await included(api, "retrieval", fact(a, srv_a, 27))  # the registration's version

    assert landed.json() == {"fenced": [], "repair_requested": None}
    assert last.json()["view"] == "installed"
    assert stale.json() == {"fenced": [], "repair_requested": None}
    assert await serving.held(conn, a) == [("retrieval", "b1", RESOURCE, "included")]
    stored = [(a, RESOURCE, "crv_1"), (b, RESOURCE, "crv_1")]
    assert (await beat(api, "retrieval", *stored)).json() == {"repair_requested": None}


async def test_a_write_captured_in_flight_keeps_a_deleted_document_held(api, conn):
    """SC23: the view is taken during a write; the Document is deleted; the write lands later."""
    uid, srv = await document(conn)
    await accepted(conn, uid, srv)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await registered(api, "retrieval", fact(uid, srv, 8))

    await page(api, "retrieval", 1, 1, 8, entry(uid, srv, 8, "pending"))
    in_flight = await serving.held(conn, uid)
    await conn.execute("UPDATE document SET deleted_at = now() WHERE document_uid = %s", (uid,))
    await included(api, "retrieval", fact(uid, srv, 9))  # the write lands after the view
    landed = await serving.held(conn, uid)
    await included(api, "retrieval", fact(uid, srv, 10, state="removed"))

    assert in_flight == [("retrieval", "b1", RESOURCE, "pending")]
    assert landed == [("retrieval", "b1", RESOURCE, "included")]
    assert await serving.held(conn, uid) == []


async def test_a_lost_removal_is_restated_by_the_view_and_an_old_include_stays_out(api, conn):
    """NC2: the removal report was lost; the repair view, which lacks the key, makes it a
    tombstone stamped with the watermark; an old `included` arrives after."""
    uid, srv = await document(conn)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 99))  # the removal at 100 never arrives

    installed = await page(api, "retrieval", 1, 1, 100)
    removed = await serving.held(conn, uid)
    old = await included(api, "retrieval", fact(uid, srv, 1))

    assert installed.json()["view"] == "installed"
    assert removed == []
    assert old.json() == {"fenced": [], "repair_requested": None}
    assert await serving.held(conn, uid) == []
    assert (await seen(api))["readiness"] == "not_ready"


def refusal(response) -> tuple[int, str, dict[str, str]]:
    detail = response.json()["error"]["details"][0]
    return response.status_code, detail["reason"], detail.get("metadata", {})


async def test_a_view_past_its_lifetime_is_discarded_and_a_fresh_one_asked(api, conn):
    """SC24: the view is captured; the Document is deleted and its removal reported; the view's
    last page arrives a day later. Installing it would resurrect the deleted fact."""
    uid, srv = await document(conn)
    other, srv_other = await document(conn, "B")
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 1), fact(other, srv_other, 2))
    captured = datetime.now(UTC) - serving.VIEW_LIFETIME + timedelta(seconds=5)
    first = await page(api, "retrieval", 1, 2, 2, entry(uid, srv, 1), captured_at=captured)
    await conn.execute("UPDATE document SET deleted_at = now() WHERE document_uid = %s", (uid,))
    await included(api, "retrieval", fact(uid, srv, 3, state="removed"))
    await conn.execute(  # the last page comes a day after the capture
        "UPDATE build SET view_captured_at = view_captured_at - interval '5 seconds'"
    )
    late = captured - timedelta(seconds=5)

    last = await page(api, "retrieval", 2, 2, 2, entry(other, srv_other, 2), captured_at=late)
    again = await page(api, "retrieval", 1, 2, 2, entry(uid, srv, 1), captured_at=late)
    fresh = await page(api, "retrieval", 1, 1, 3, entry(other, srv_other, 2), view_id="v2")

    assert first.json() == {"view": "incomplete", "repair_requested": None}
    assert refusal(last) == (409, "VIEW_DISCARDED", {"reason": "expired"})
    assert refusal(again) == (409, "VIEW_DISCARDED", {"reason": "expired"})
    assert await serving.held(conn, uid) == []
    assert fresh.json() == {"view": "installed", "repair_requested": None}
    assert await serving.held(conn, uid) == []


async def test_a_view_the_expiry_fence_stops_is_discarded_whole(api, conn):
    """DR §5.4 step 3: a tombstone expired after the view was captured; the view's entry of that
    key, at or below the tombstone's version, would resurrect it."""
    uid, srv = await document(conn)
    other, srv_other = await document(conn, "B")
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 5, state="removed"), fact(other, srv_other, 6))
    await aged(conn, uid, "30 days 1 minute")  # expired a minute ago
    captured = datetime.now(UTC) - timedelta(minutes=5)  # before it expired
    view = (entry(uid, srv, 4), entry(other, srv_other, 6))

    fenced = await page(api, "retrieval", 1, 1, 6, *view, captured_at=captured)
    asked = await beat(api, "retrieval", (other, RESOURCE, "crv_1"))

    assert refusal(fenced) == (409, "VIEW_DISCARDED", {"reason": "fenced"})
    assert refusal(await page(api, "retrieval", 1, 1, 6, *view, captured_at=captured)) == (
        409, "VIEW_DISCARDED", {"reason": "fenced"}
    )  # fmt: skip
    assert await serving.held(conn, uid) == []
    assert asked.json()["repair_requested"]["reason"] == "view_fenced"


async def test_a_key_stored_and_registered_is_pending_and_keeps_serving(api, conn):
    """DR §5.4: the registration wins; the stored revision still counts for readiness."""
    uid, srv = await document(conn)
    await profile(conn, "retrieval")
    await build(api, "retrieval")

    await page(api, "retrieval", 1, 1, 2, entry(uid, srv, 1), entry(uid, srv, 2, "pending"))

    assert await serving.held(conn, uid) == [("retrieval", "b1", RESOURCE, "pending")]
    assert (await seen(api))["readiness"] == "ready"


async def test_a_query_during_the_replacement_sees_it_whole(api, conn, pool):
    """The replacement is one step: a reader sees every fact of the Build before it or after."""
    uids = [(await document(conn, f"D{i}"))[0] for i in range(40)]
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", *(fact(uid, "srv", 1) for uid in uids))
    seen_counts: set[int] = set()
    done = asyncio.Event()

    async def watch() -> None:
        async with pool.connection() as reader:
            while not done.is_set():
                seen_counts.add(len(await serving.served(reader, uids)))  # one statement

    watcher = asyncio.create_task(watch())
    await asyncio.sleep(0.05)
    installed = await page(api, "retrieval", 1, 1, 1)  # the store holds nothing
    done.set()
    await watcher

    assert installed.json()["view"] == "installed"
    assert seen_counts <= {40, 0}
    assert 40 in seen_counts


async def test_after_lost_writes_only_a_view_captured_later_ends_the_repair(api, conn):
    """DR §5.6, K2: operations declare that the database lost committed writes. Every Build is
    asked for a repair; a view in transfer, or captured before, does not end it."""
    a, srv_a = await document(conn, "A")
    b, srv_b = await document(conn, "B")
    await profile(conn, "retrieval", "wiki")
    await build(api, "retrieval")
    await build(api, "wiki")
    await build(api, "wiki", "b2", state="building")
    await build(api, "wiki", "b2", state="retired")
    await included(api, "retrieval", fact(a, srv_a, 1), fact(b, srv_b, 2))
    stored = [(a, RESOURCE, "crv_1"), (b, RESOURCE, "crv_1")]
    await conn.execute("UPDATE serving_fact SET canonical_revision_id = 'crv_0'")
    await beat(api, "retrieval", *stored)  # a heartbeat_mismatch request, then the loss
    before = datetime.now(UTC) - timedelta(minutes=1)  # the database has its own clock
    await page(api, "retrieval", 1, 2, 2, entry(a, srv_a, 1), captured_at=before)

    asked = await serving.lose_writes(conn, 1)
    repeated = await serving.lose_writes(conn, 1)
    unrepaired = await serving.writes_unrepaired(conn)
    old_view = await page(api, "retrieval", 2, 2, 2, entry(b, srv_b, 2), captured_at=before)
    earlier = await page(api, "retrieval", 1, 1, 2, *(entry(a, srv_a, 1), entry(b, srv_b, 2)),
                         view_id="v0", captured_at=before)  # fmt: skip
    request = (await beat(api, "retrieval", *stored)).json()["repair_requested"]
    after = await page(api, "retrieval", 1, 1, 2, entry(a, srv_a, 1), entry(b, srv_b, 2),
                       view_id="v2")  # fmt: skip

    assert (asked, repeated) == (2, None)
    assert unrepaired == [("retrieval", "b1"), ("wiki", "b1")]
    assert refusal(old_view) == (409, "VIEW_DISCARDED", {"reason": "writes_lost"})
    assert refusal(earlier) == (409, "VIEW_DISCARDED", {"reason": "writes_lost"})
    assert request["reason"] == "writes_lost"
    assert after.json() == {"view": "installed", "repair_requested": None}
    assert await serving.writes_unrepaired(conn) == [("wiki", "b1")]
    erased = await build(api, "retrieval", "b3", state="building")  # one the loss erased, say
    assert erased.json()["repair_requested"]["reason"] == "writes_lost"
    with pytest.raises(ValueError):
        await serving.lose_writes(conn, 0)
    assert await serving.lose_writes(conn, 2) == 3


async def test_a_repair_restates_live_tombstones_and_leaves_expired_ones_fencing(api, conn):
    """A key the view lacks becomes a tombstone stamped with the watermark, so a report it
    reflected stays out; an expired tombstone keeps fencing as it did (DR §5.3, #264)."""
    live, srv_live = await document(conn, "A")
    old, srv_old = await document(conn, "B")
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(live, srv_live, 5, state="removed"),
                   fact(old, srv_old, 6, state="removed"))  # fmt: skip
    await aged(conn, old, "31 days")
    long_ago = (datetime.now(UTC) - timedelta(days=40)).isoformat()

    await page(api, "retrieval", 1, 1, 10)
    behind = await included(api, "retrieval", fact(live, srv_live, 7))
    fenced = await included(api, "retrieval", fact(old, srv_old, 6, issued_at=long_ago))

    assert behind.json()["fenced"] == []
    assert await serving.held(conn, live) == []
    assert fenced.json()["fenced"] == [{"document_uid": old, "resource_id": RESOURCE}]


async def test_a_view_whose_pages_stopped_is_discarded_by_the_next_report(api, conn):
    """DR §5.4 step 2: the owner crashed after a page; its next heartbeat past the lifetime
    learns the view is gone and a fresh one is asked."""
    uid, srv = await document(conn)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    captured = datetime.now(UTC) - serving.VIEW_LIFETIME + timedelta(minutes=5)
    await page(api, "retrieval", 1, 2, 1, entry(uid, srv, 1), captured_at=captured)
    await conn.execute(  # ten minutes later
        "UPDATE build SET view_captured_at = view_captured_at - interval '10 minutes'"
    )

    asked = await beat(api, "retrieval")
    rest = await page(api, "retrieval", 2, 2, 1, captured_at=captured)

    assert asked.json()["repair_requested"]["reason"] == "view_expired"
    assert refusal(rest) == (409, "VIEW_DISCARDED", {"reason": "expired"})


async def test_a_view_captured_ahead_of_the_clock_or_past_its_lifetime_is_refused(api, conn):
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    ahead = datetime.now(UTC) + serving.CLOCK_SKEW + timedelta(seconds=30)

    refused = await page(api, "retrieval", 1, 1, 0, captured_at=ahead)
    long_ago = datetime.now(UTC) - serving.VIEW_LIFETIME - timedelta(minutes=1)
    stale = await page(api, "retrieval", 1, 1, 0, view_id="v0", captured_at=long_ago)

    assert refused.status_code == 400
    assert refusal(stale) == (409, "VIEW_DISCARDED", {"reason": "expired"})
    assert (await page(api, "retrieval", 1, 1, 0)).json()["view"] == "installed"


async def test_a_build_reported_soon_after_lost_writes_may_be_an_erased_one(api, conn):
    """DR §5.6, K2: the loss erased a Build; its owner reports it again within its pipeline's
    update interval of the declaration. It is asked for a view captured after the declaration,
    even when no surviving Build is left to repair; a Build reported later is not."""
    uid, srv = await document(conn)
    await profile(conn, "retrieval")
    before = datetime.now(UTC) - timedelta(minutes=1)  # the database's clock is another one
    assert await serving.lose_writes(conn, 1) == 0  # every Build was erased

    again = await build(api, "retrieval", "b1", state="building")
    stale = await page(api, "retrieval", 1, 1, 1, entry(uid, srv, 1), captured_at=before)
    unrepaired = await serving.writes_unrepaired(conn)
    fresh = await page(api, "retrieval", 1, 1, 1, entry(uid, srv, 1), view_id="v2")
    await conn.execute("UPDATE writes_lost SET applied_at = now() - interval '601 seconds'")
    later = await build(api, "retrieval", "b2", state="building")

    assert again.json()["repair_requested"]["reason"] == "writes_lost"
    assert refusal(stale) == (409, "VIEW_DISCARDED", {"reason": "writes_lost"})
    assert unrepaired == [("retrieval", "b1")]
    assert fresh.json() == {"view": "installed", "repair_requested": None}
    assert later.json()["repair_requested"] is None
    assert await serving.writes_unrepaired(conn) == []


async def test_an_owner_puts_an_erased_serving_build_back_in_order(api, conn):
    """Spec §7.4 Lost writes: the loss erased the serving Build and its facts. Its owner reports
    it `building`, sends its view, then the switch again, which passes the gates."""
    uid, srv = await document(conn)
    await profile(conn, "retrieval")
    await build(api, "retrieval")
    await included(api, "retrieval", fact(uid, srv, 1))
    for table in ("serving_fact", "build"):  # the restore point is before the Build existed
        await conn.execute(f"DELETE FROM {table}")
    await serving.lose_writes(conn, 1)

    unknown = await beat(api, "retrieval", (uid, RESOURCE, "crv_1"))
    created = await build(api, "retrieval", state="building")
    viewed = await page(api, "retrieval", 1, 1, 1, entry(uid, srv, 1))
    switched = await build(api, "retrieval")  # switch_seq 1, a feed position read now

    assert unknown.status_code == 404
    assert created.json()["repair_requested"]["reason"] == "writes_lost"
    assert viewed.json() == {"view": "installed", "repair_requested": None}
    assert switched.json() == {"state": "serving", "repair_requested": None}
    assert await serving.held(conn, uid) == [("retrieval", "b1", RESOURCE, "included")]
    assert (await seen(api))["readiness"] == "ready"
    assert await serving.writes_unrepaired(conn) == []
