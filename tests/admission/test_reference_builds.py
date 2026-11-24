"""The reference projection's Build lifecycle (#280) end to end, on #127's harness: the real api
with a real admission database, the projection on its own database. A test starts the process
asked to serve another Build (KP_PROJECTION_BUILD_ID, ruling A2) by making a new Projection on
the same store, as a restart with a changed setting would."""

# ruff: noqa: F811 (the fixtures of #127's harness are imported by name)

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from kp_admission import serving
from kp_reference_projection import cli, query
from tests.admission.test_reference_projection import (  # noqa: F401 (fixtures)
    PIPELINES,
    Platform,
    delete,
    enforce,
    found,
    mirror,
    platform,
    pool,
    projection,
    reader,
    readiness,
    ready_document,
    sample,
    settle,
    store,
)
from tests.admission.test_serving import accepted, profile, revised
from tests.admission.test_status import document

pytestmark = pytest.mark.docker


async def platform_builds(conn) -> dict[str, str]:
    rows = await conn.execute("SELECT build_id, state FROM build ORDER BY build_id")
    return dict(await rows.fetchall())


async def local(store, sql: str, *params) -> list[tuple]:
    async with store.connection() as conn:
        return await (await conn.execute(sql, params)).fetchall()


def build_reports(platform: Platform, build_id: str) -> list[httpx.Request]:
    return [r for r in platform.sent if f"/report/v1/builds/{build_id}" in r.url.path]


async def test_a_new_build_reads_everything_from_a_fixed_start_switches_and_readiness_follows_it(
    conn, platform, store, reader
):
    a, _ = await ready_document(conn, platform, reader, "A")
    [(cursor,)] = await local(store, "SELECT cursor FROM reader")
    b2 = projection(platform, store, "b2", approval_ref="chg-1", evidence_ref="ev-1")
    await b2.start()
    building = await platform_builds(conn)
    await revised(conn, a, "srv_a2")  # while b2 builds: both Builds take it
    platform.contents["crv_a2"] = ["# A2"]
    await accepted(conn, a, "srv_a2", "crv_a2")

    await settle(b2)

    assert building == {"b1": "serving", "b2": "building"}
    assert await platform_builds(conn) == {"b1": "retained", "b2": "serving"}
    assert await local(store, "SELECT start_position FROM build WHERE build_id = 'b2'") == [
        (cursor,)
    ]
    assert await local(
        store,
        "SELECT build_id, canonical_revision_id FROM entry WHERE markdown IS NOT NULL ORDER BY 1",
    ) == [("b1", "crv_a2"), ("b2", "crv_a2")]
    # The switch record (DR D2, review M5): both positions and the refs, sent and kept.
    [(replaces, evidence, at_switch, approval, ev, taken)] = await local(
        store,
        "SELECT replaces, evidence_position, feed_position, approval_ref, evidence_ref,"
        " taken_at IS NOT NULL FROM switch WHERE build_id = 'b2'",
    )
    assert (replaces, approval, ev, taken) == ("b1", "chg-1", "ev-1", True)
    assert evidence and at_switch and evidence <= at_switch
    assert await (
        await conn.execute("SELECT approval_ref, evidence_ref FROM build WHERE build_id = 'b2'")
    ).fetchall() == [("chg-1", "ev-1")]

    # Readiness counts the serving Build alone: b1 falls behind on a newer revision, and the
    # Document is `ready`, not `ready_stale`.
    async def b1_down(request: httpx.Request) -> httpx.Response | None:
        return httpx.Response(503) if "/builds/b1/registrations" in request.url.path else None

    platform.hooks.append(b1_down)
    b2.retry_s = 3600
    await revised(conn, a, "srv_a3", "3")
    platform.contents["crv_a3"] = ["# A3"]
    await accepted(conn, a, "srv_a3", "crv_a3")
    await settle(b2)

    served = {(b, crv) for b, _, _, crv in await mirror_by_build(conn)}
    assert served == {("b1", "crv_a2"), ("b2", "crv_a3")}
    assert await readiness(platform) == "ready"


async def mirror_by_build(conn) -> list[tuple]:
    rows = await conn.execute(
        "SELECT build_id, document_uid, state, canonical_revision_id FROM serving_fact"
        " WHERE state = 'included' ORDER BY 1, 2"
    )
    return await rows.fetchall()


async def test_a_retained_build_follows_the_feed_and_a_rollback_serves_what_changed_meanwhile(
    conn, platform, store, reader
):
    a, _ = await ready_document(conn, platform, reader, "A")
    await ready_document(conn, platform, reader, "B")
    b2 = projection(platform, store, "b2")
    await b2.start()
    await settle(b2)
    await revised(conn, a, "srv_a2")  # while b1 is retained
    platform.contents["crv_a2"] = ["# A2 updated"]
    await accepted(conn, a, "srv_a2", "crv_a2")
    await delete(conn, "B")
    await settle(b2)
    assert await found(store, "body") == []  # b2 serves: B is gone, A was rewritten

    back = projection(platform, store, "b1")  # the setting names b1 again: a rollback
    await back.start()
    await settle(back)

    assert await platform_builds(conn) == {"b1": "serving", "b2": "retained"}
    assert await found(store, "updated") == [a]
    assert await found(store, "body") == []
    assert await enforce(conn) == {"enforced": 1}
    assert await readiness(platform, "A") == "ready"


async def test_a_second_candidate_replaces_the_first_whose_data_is_cleared_and_retired(
    conn, platform, store, reader
):
    await ready_document(conn, platform, reader, "A")
    b2 = projection(platform, store, "b2")
    await b2.start()
    await b2.read_once()
    while await b2.work_once():  # b2 writes A, and has not switched yet
        pass
    written = await local(store, "SELECT count(*) FROM entry WHERE build_id = 'b2'")

    b3 = projection(platform, store, "b3")
    await b3.start()
    retired = await platform_builds(conn)
    await settle(b3)

    assert written == [(1,)]
    assert retired == {"b1": "serving", "b2": "retired", "b3": "building"}
    for table in ("entry", "work", "source_work", "attempt"):
        assert await local(store, f"SELECT count(*) FROM {table} WHERE build_id = 'b2'") == [(0,)]
    assert await platform_builds(conn) == {"b1": "retained", "b2": "retired", "b3": "serving"}


async def test_a_retained_build_is_retired_when_its_retention_ends_and_is_never_reported_again(
    conn, platform, store, reader
):
    await ready_document(conn, platform, reader, "A")
    b2 = projection(platform, store, "b2", retention_s=3600)
    await b2.start()
    await settle(b2)
    await b2.retire_expired()
    kept = await platform_builds(conn)

    b2.retention_s = 0
    await b2.retire_expired()
    sent = len(build_reports(platform, "b1"))
    b, srv = await document(conn, "B")  # after the retirement: nothing goes to b1
    platform.contents["crv_b1"] = ["# B"]
    await accepted(conn, b, srv, "crv_b1")
    await settle(b2)
    await b2.heartbeat()

    assert kept["b1"] == "retained"
    assert await platform_builds(conn) == {"b1": "retired", "b2": "serving"}
    assert await local(store, "SELECT count(*) FROM entry WHERE build_id = 'b1'") == [(0,)]
    assert len(build_reports(platform, "b1")) == sent
    assert await found(store, "B") == [b]


async def test_every_build_not_retired_sends_a_heartbeat_while_building_and_retained(
    conn, platform, store, reader
):
    await ready_document(conn, platform, reader, "A")
    b2 = projection(platform, store, "b2")
    await b2.start()
    building = await b2.heartbeat()
    await settle(b2)

    retained = await b2.heartbeat()
    now = datetime.now(UTC)
    interval = timedelta(seconds=PIPELINES["retrieval"].update_interval_s)

    assert {b: a["repair_requested"] for b, a in building.items()} == {"b1": None, "b2": None}
    assert {b: a["repair_requested"] for b, a in retained.items()} == {"b1": None, "b2": None}
    assert await serving.silent(conn, PIPELINES, now + interval - timedelta(seconds=5)) == []
    # Control: past the interval without a report, both would read as silent.
    later = now + interval + timedelta(seconds=5)
    assert await serving.silent(conn, PIPELINES, later) == [
        ("retrieval", "b1"),
        ("retrieval", "b2"),
    ]


def switches(platform: Platform, build_id: str) -> list[int]:
    """The status codes the platform answered to the Build's `serving` reports, in order."""
    return [
        r.status_code
        for r in platform.answered
        if r.request.method == "PUT"
        and r.request.url.path.endswith(f"/builds/{build_id}")
        and json.loads(r.request.content)["state"] == "serving"
    ]


@pytest.fixture
def answered(platform):
    """Keeps the answers to Build state reports in `platform.answered`."""

    async def keep(request: httpx.Request) -> httpx.Response:
        response = await platform.asgi.handle_async_request(request)
        await response.aread()
        platform.answered.append(response)
        return response

    async def hook(request: httpx.Request) -> httpx.Response | None:
        if "/report/v1/builds/" in request.url.path and request.method == "PUT":
            return await keep(request)
        return None

    platform.hooks.append(hook)
    return platform


async def test_a_switch_refused_for_a_document_deleted_meanwhile_is_tried_again_and_succeeds(
    conn, platform, store, reader, answered
):
    await ready_document(conn, platform, reader, "A")
    await ready_document(conn, platform, reader, "B")
    b2 = projection(platform, store, "b2")
    await b2.start()
    refused = sample("kp_projection_failures_total", step="switch", reason="GATE_FAILED")

    async def delete_first(request: httpx.Request) -> None:
        if request.url.path.endswith("/builds/b2") and b"serving" in request.content:
            if not switches(platform, "b2"):
                await delete(conn, "B")  # committed after b2's own checks, before the gates

    platform.hooks.insert(0, delete_first)
    await settle(b2)
    await settle(b2)  # the reader reads again after a refusal: the deletion, then the switch

    assert switches(platform, "b2") == [409, 200]
    assert sample("kp_projection_failures_total", step="switch", reason="GATE_FAILED") == (
        refused + 1
    )
    assert await platform_builds(conn) == {"b1": "retained", "b2": "serving"}
    assert await enforce(conn) == {"enforced": 1}


async def test_a_switch_refused_as_behind_the_feed_is_tried_again_once_caught_up(
    conn, platform, store, reader, answered, monkeypatch
):
    await ready_document(conn, platform, reader, "A")
    b2 = projection(platform, store, "b2")
    await b2.start()
    monkeypatch.setattr(serving, "SWITCH_LAG_MAX_S", 0)

    async def accept_first(request: httpx.Request) -> None:
        if request.url.path.endswith("/builds/b2") and b"serving" in request.content:
            if not switches(platform, "b2"):
                b, srv = await document(conn, "B")  # a feed entry after the position sent
                platform.contents["crv_b1"] = ["# B"]
                await accepted(conn, b, srv, "crv_b1")

    platform.hooks.insert(0, accept_first)
    await settle(b2)
    await settle(b2)

    assert switches(platform, "b2") == [409, 200]
    assert await platform_builds(conn) == {"b1": "retained", "b2": "serving"}
    assert len(await found(store, "B")) == 1


async def test_a_switch_refused_for_less_coverage_than_the_serving_build_waits_for_it(
    conn, platform, store, reader, answered
):
    await ready_document(conn, platform, reader, "A")
    await ready_document(conn, platform, reader, "B")
    b2 = projection(platform, store, "b2", retry_s=3600)
    await b2.start()
    await settle(b2)  # b2 serves; b3 below is the candidate
    b3 = projection(platform, store, "b3", retry_s=3600)
    await b3.start()
    await b3.read_once()
    while await b3.work_once():
        pass

    # b2, serving, is behind on a deletion: its removal is not taken yet, so the platform counts
    # two Documents for it and one for b3.
    async def b2_down(request: httpx.Request) -> httpx.Response | None:
        return httpx.Response(503) if "/builds/b2/facts" in request.url.path else None

    platform.hooks.insert(0, b2_down)
    await delete(conn, "B")
    await settle(b3)
    first = switches(platform, "b3")
    platform.hooks.remove(b2_down)
    async with store.connection() as projection_conn:  # b2's retry comes due
        await projection_conn.execute("UPDATE work SET not_before = now()")
    await settle(b3)

    *refused, taken = switches(platform, "b3")
    assert first == [409]
    assert set(refused) == {409} and taken == 200
    assert (await platform_builds(conn))["b3"] == "serving"


async def test_a_projection_added_to_a_profile_later_backfills_and_counts_only_after_its_report(
    conn, platform, store
):
    await profile(conn)  # the Source's first profile lists no projection
    uid, srv = await document(conn)
    platform.contents["crv_1"] = ["# Later"]
    await accepted(conn, uid, srv, "crv_1")
    p = projection(platform, store)
    await p.start()
    await settle(p)
    unlisted = (await found(store, "Later"), await readiness(platform))
    registered = [r for r in platform.sent if r.url.path.endswith("/registrations")]
    seen = []

    async def look(request: httpx.Request) -> None:
        if request.url.path.endswith("/sources/s1/backfill"):
            seen.append((await readiness(platform), await mirror(conn)))

    platform.hooks.append(look)
    pages = len([r for r in platform.sent if r.url.path.endswith("/sources/s1/documents")])
    await profile(conn, "retrieval")  # two requests for the same Source: one pass
    await profile(conn, "retrieval", "wiki")
    await settle(p)

    assert unlisted == ([], "not_ready") and registered == []
    assert len([r for r in platform.sent if r.url.path.endswith("/sources/s1/documents")]) == (
        pages + 1
    )
    assert seen == [("not_ready", [(uid, "s1/hr-all", "included", "crv_1")])]
    assert await readiness(platform) == "ready"
    assert await found(store, "Later") == [uid]


async def test_a_source_that_stops_listing_the_projection_has_its_documents_removed(
    conn, platform, store, reader
):
    uid, _ = await ready_document(conn, platform, reader)

    await profile(conn, "wiki")
    await settle(reader)

    assert await found(store, "body") == []
    assert await mirror(conn) == [(uid, "s1/hr-all", "removed", "crv_a1")]
    await delete(conn)
    assert await enforce(conn) == {"enforced": 1}


async def test_the_process_refuses_a_retired_build_with_exit_1(conn, platform, store, reader):
    await ready_document(conn, platform, reader)
    b2 = projection(platform, store, "b2", retention_s=0)
    await b2.start()
    await settle(b2)
    await b2.retire_expired()

    code = await cli.run("http://api", "c", store.conninfo, "retrieval", "b1", 1, 1, 60, 0)

    assert code == 1


async def test_a_candidates_backlog_does_not_make_the_serving_builds_results_stale(
    conn, platform, store, reader
):
    uid, _ = await ready_document(conn, platform, reader)
    b2 = projection(platform, store, "b2")
    await b2.start()
    await b2.read_once()
    await b2.work_once()  # b2's pass queues A for b2 alone
    queued = await local(store, "SELECT build_id FROM work")

    hits = await query.search(store, "body", ["s1/hr-all"], True, 10)

    assert queued == [("b2",)]
    assert [(h.document_uid, h.stale) for h in hits] == [(uid, False)]


async def test_a_retirement_waits_for_the_run_in_progress_of_that_build(
    conn, platform, store, reader
):
    a, _ = await ready_document(conn, platform, reader)
    b2 = projection(platform, store, "b2", retention_s=0)
    await b2.start()
    await settle(b2)
    await revised(conn, a, "srv_a2")
    platform.contents["crv_a2"] = ["# A2"]
    entered, release = asyncio.Event(), asyncio.Event()

    async def hold(request: httpx.Request) -> None:
        if "/builds/b1/registrations" in request.url.path:
            entered.set()
            await release.wait()

    platform.hooks.append(hold)
    await accepted(conn, a, "srv_a2", "crv_a2")
    await b2.read_once()
    runs = [asyncio.create_task(b2.work_once()) for _ in range(2)]
    await entered.wait()
    await b2.retire_expired()
    during = await platform_builds(conn)
    release.set()
    await asyncio.gather(*runs)
    await b2.retire_expired()

    assert during["b1"] == "retained"
    assert await platform_builds(conn) == {"b1": "retired", "b2": "serving"}
    assert await local(store, "SELECT count(*) FROM entry WHERE build_id = 'b1'") == [(0,)]
