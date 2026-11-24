"""The reference projection (#127) end to end: the real api with a real admission database, the
projection on its own database, connected over HTTP by the consumer SDK. Canonical Acceptance
comes from a successful report with a candidate (#251's helper); the content reads, which #268
builds, answer from fixtures. Each test drives the reader and the workers step by step."""

import asyncio
import json
import logging
import os
import re
import signal
import socket
import sys
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx
import psycopg
import pytest
import uvicorn
from prometheus_client import REGISTRY, generate_latest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg_pool import AsyncConnectionPool

from kp_admission import deletion, feed, status
from kp_admission.api import app
from kp_admission.reports import Pipeline
from kp_reference_projection import SCHEMA, cli, query
from kp_reference_projection.projection import STAGES, Projection
from kp_sdk.projection import ProjectionClient
from tests.admission.authz_fake import FakeAuthorizer
from tests.admission.support import INTAKE
from tests.admission.test_serving import accepted, profile, revised
from tests.admission.test_status import credential, digest, document

pytestmark = pytest.mark.docker

PIPELINES = {
    "retrieval": Pipeline(
        pipeline_id="kp-retrieval",
        track="retrieval",
        stages=STAGES,
        start_deadline_s=600,
        update_interval_s=600,
    )
}
CONTENT = re.compile(r"/read/v1/documents/(?P<uid>[^/]+)/revisions/(?P<crv>[^/]+)")
Hook = Callable[[httpx.Request], Awaitable[httpx.Response | None]]


class Platform(httpx.AsyncBaseTransport):
    """The real api in process, except the content reads (#268, not built), which answer from
    `contents` by Canonical Revision. `hooks` run before each request, and the first answer one
    returns replaces the platform's; `sent` keeps the requests."""

    def __init__(self, application) -> None:
        self.asgi = httpx.ASGITransport(application)
        self.contents: dict[str, list[str]] = {}
        self.hooks: list[Hook] = []
        self.sent: list[httpx.Request] = []
        self.answered: list[httpx.Response] = []  # kept by a hook that asks for them

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await request.aread()
        self.sent.append(request)
        for hook in list(self.hooks):
            if (answer := await hook(request)) is not None:
                return answer
        if found := CONTENT.fullmatch(request.url.path):
            blocks = self.contents.get(found["crv"])
            if blocks is None:
                return httpx.Response(404, json={"error": {"status": "NOT_FOUND"}})
            body = {"canonical_revision_id": found["crv"], "blocks": [
                {"ref": f"#/texts/{i}", "kind": "text", "markdown": md}
                for i, md in enumerate(blocks)
            ]}  # fmt: skip
            return httpx.Response(200, content=json.dumps(body).encode())
        return await self.asgi.handle_async_request(request)

    def reads(self, crv: str) -> int:
        return sum(1 for r in self.sent if r.url.path.endswith(f"/revisions/{crv}"))


@pytest.fixture
async def pool(dsn):
    async with AsyncConnectionPool(dsn, kwargs={"autocommit": True}) as connections:
        yield connections


@pytest.fixture
async def store(postgres):
    """The projection's own database, on the same server, holding its SCHEMA."""
    name = f"projection_{uuid.uuid4().hex[:12]}"
    async with await psycopg.AsyncConnection.connect(postgres, autocommit=True) as conn:
        await conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = make_conninfo(postgres, dbname=name)
    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as conn:
        await conn.execute(SCHEMA)
    async with AsyncConnectionPool(url, kwargs={"autocommit": True}) as connections:
        yield connections


@pytest.fixture
def platform(pool) -> Platform:
    return Platform(
        app(
            FakeAuthorizer(),
            {digest("retrieval"): "retrieval"},  # one credential reads and reports (DR C1)
            {digest("s1"): credential("s1")},
            pool,
            INTAKE,
            pipelines={digest("retrieval"): PIPELINES["retrieval"]},
        )
    )


async def no_wait(_: float) -> None:
    pass


def projection(platform: Platform, store, build_id: str = "b1", **options: Any) -> Projection:
    """The projection process asked to serve `build_id` (KP_PROJECTION_BUILD_ID)."""
    sdk = ProjectionClient(
        "http://api", "retrieval", "retrieval", transport=platform, sleep=no_wait, attempts=2
    )
    options.setdefault("retry_s", 0)
    return Projection(sdk, store, build_id, **options)


@pytest.fixture
async def reader(conn, platform, store) -> Projection:
    """A projection in Source s1's first Knowledge Profile, started and switched to serving."""
    await profile(conn, "retrieval")
    started = projection(platform, store)
    await started.start()
    await settle(started)
    return started


async def settle(p: Projection) -> None:
    """Reads the feed and runs the work until neither has anything left."""
    while True:
        read = await p.read_once()
        worked = False
        while await p.work_once():
            worked = True
        if not read and not worked:
            return


async def readiness(platform: Platform, document_id: str = "A") -> str:
    async with httpx.AsyncClient(
        transport=platform.asgi,
        base_url="http://api",
        headers={"authorization": "Bearer s1"},
    ) as source:
        return (await source.get(f"/v1/documents/{document_id}")).json()["readiness"]


async def entries(store) -> list[tuple]:
    async with store.connection() as conn:
        rows = await conn.execute(
            "SELECT document_uid, resource_id, canonical_revision_id, markdown FROM entry"
            " WHERE markdown IS NOT NULL ORDER BY document_uid, resource_id"
        )
        return await rows.fetchall()


async def mirror(conn) -> list[tuple]:
    rows = await conn.execute(
        "SELECT document_uid, resource_id, state, canonical_revision_id FROM serving_fact"
        " ORDER BY document_uid, resource_id"
    )
    return await rows.fetchall()


async def enforce(conn) -> dict[str, int]:
    return await deletion.enforce(conn, PIPELINES, datetime.now(UTC))


async def delete(conn, document_id: str = "A") -> None:
    await deletion.delete(
        conn, tenant_id="t1", source_id="s1", document_id=document_id, trace_id="t"
    )


def sample(name: str, **labels: str) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


async def ready_document(conn, platform, reader, document_id: str = "A") -> tuple[str, str]:
    uid, srv = await document(conn, document_id)
    platform.contents[f"crv_{document_id.lower()}1"] = [f"# {document_id}", "body"]
    await accepted(conn, uid, srv, f"crv_{document_id.lower()}1")
    await settle(reader)
    return uid, srv


async def test_an_accepted_document_is_written_confirmed_and_ready(conn, platform, store, reader):
    uid, srv = await document(conn)
    platform.contents["crv_1"] = ["# Travel", "Rules for trips."]
    before = await readiness(platform)
    writes = sample("kp_projection_write_seconds_count")

    await accepted(conn, uid, srv, "crv_1")
    await settle(reader)

    assert (before, await readiness(platform)) == ("not_ready", "ready")
    assert sample("kp_projection_write_seconds_count") - writes == 1
    assert await entries(store) == [(uid, "s1/hr-all", "crv_1", "# Travel\n\nRules for trips.")]
    assert await mirror(conn) == [(uid, "s1/hr-all", "included", "crv_1")]
    assert (await reader.heartbeat())["b1"]["repair_requested"] is None


async def test_an_update_reads_ready_stale_while_it_is_written_then_ready(
    conn, platform, store, reader
):
    uid, _ = await ready_document(conn, platform, reader)
    await revised(conn, uid, "srv_2")
    platform.contents["crv_2"] = ["# Travel v2"]
    during: list[str] = []

    async def look(request: httpx.Request) -> None:
        if request.url.path.endswith("/revisions/crv_2"):
            during.append(await readiness(platform))

    platform.hooks.append(look)
    await accepted(conn, uid, "srv_2", "crv_2")
    await settle(reader)

    assert (during, await readiness(platform)) == (["ready_stale"], "ready")
    assert await entries(store) == [(uid, "s1/hr-all", "crv_2", "# Travel v2")]
    assert (await reader.heartbeat())["b1"]["repair_requested"] is None


async def test_a_deletion_is_removed_and_then_judged_enforced(conn, platform, store, reader):
    await ready_document(conn, platform, reader)
    await delete(conn)
    held = await enforce(conn)
    removals = sample("kp_projection_removal_seconds_count")

    await settle(reader)

    assert held == {"held": 1}
    assert sample("kp_projection_removal_seconds_count") - removals == 1
    assert await enforce(conn) == {"enforced": 1}
    assert await entries(store) == []
    assert (await reader.heartbeat())["b1"]["repair_requested"] is None


async def test_a_rebind_removes_the_old_resource_and_includes_the_new(
    conn, platform, store, reader
):
    uid, _ = await ready_document(conn, platform, reader)
    async with conn.transaction():  # as the rebind of #205 will record it
        await conn.execute(
            "UPDATE document SET resource_id = 's1/legal' WHERE document_uid = %s", (uid,)
        )
        await feed.append(
            conn,
            "inclusion_changed",
            tenant_id="t1",
            source_id="s1",
            document_uid=uid,
            priority="narrowing",
        )
    await status.refresh(conn, [uid])

    await settle(reader)

    assert await mirror(conn) == [
        (uid, "s1/hr-all", "removed", "crv_a1"),
        (uid, "s1/legal", "included", "crv_a1"),
    ]
    assert await entries(store) == [(uid, "s1/legal", "crv_a1", "# A\n\nbody")]
    assert await readiness(platform) == "ready"


async def test_a_superseded_registration_writes_nothing_and_converges_on_the_new_state(
    conn, platform, store, reader
):
    uid, srv = await document(conn)
    platform.contents |= {"crv_1": ["# old"], "crv_2": ["# new"]}
    moved = asyncio.Event()

    async def overtake(request: httpx.Request) -> None:
        if request.url.path.endswith("/registrations") and not moved.is_set():
            moved.set()  # a newer revision is accepted between the state read and the check
            await revised(conn, uid, "srv_2")
            await accepted(conn, uid, "srv_2", "crv_2")

    platform.hooks.append(overtake)
    await accepted(conn, uid, srv, "crv_1")
    await settle(reader)

    assert platform.reads("crv_1") == 0  # dropped before any write
    assert await entries(store) == [(uid, "s1/hr-all", "crv_2", "# new")]
    assert await mirror(conn) == [(uid, "s1/hr-all", "included", "crv_2")]
    assert await readiness(platform) == "ready"
    assert (await reader.heartbeat())["b1"]["repair_requested"] is None


async def test_a_registration_recorded_before_a_deletion_is_reported_removed_after_superseded(
    conn, platform, store, reader
):
    uid, srv = await document(conn)
    platform.contents["crv_1"] = ["# A"]
    lost = asyncio.Event()

    async def lose_answer(request: httpx.Request) -> httpx.Response | None:
        if request.url.path.endswith("/registrations") and not lost.is_set():
            lost.set()
            await platform.asgi.handle_async_request(request)  # recorded `pending`
            await delete(conn)
            return httpx.Response(503)  # the answer is lost; the resend is SUPERSEDED
        return None

    platform.hooks.append(lose_answer)
    await accepted(conn, uid, srv, "crv_1")
    await settle(reader)

    assert await mirror(conn) == [(uid, "s1/hr-all", "removed", "crv_1")]
    assert await enforce(conn) == {"enforced": 1}
    assert (await entries(store), platform.reads("crv_1")) == ([], 0)


async def test_a_heartbeat_waits_for_a_report_in_flight(conn, platform, store, reader):
    uid, srv = await document(conn)
    platform.contents["crv_1"] = ["# A"]
    entered, release = asyncio.Event(), asyncio.Event()

    async def hold(request: httpx.Request) -> None:
        if request.url.path.endswith("/registrations"):
            entered.set()
            await release.wait()

    platform.hooks.append(hold)
    await accepted(conn, uid, srv, "crv_1")
    await reader.read_once()
    run = asyncio.create_task(reader.work_once())
    await entered.wait()
    beat = asyncio.create_task(reader.heartbeat())
    await asyncio.sleep(0.2)
    waited = not beat.done()
    release.set()
    await run

    assert waited
    assert (await beat)["b1"]["repair_requested"] is None
    assert (await reader.heartbeat())["b1"]["repair_requested"] is None


async def test_a_source_profile_change_read_from_the_feed_starts_one_pass_over_the_source(
    conn, platform, reader
):
    await profile(conn, "retrieval", "wiki")  # after the reader started: an event without a uid
    listed = len([r for r in platform.sent if r.url.path.endswith("/sources/s1/documents")])

    read = await reader.read_once()
    await settle(reader)

    pages = len([r for r in platform.sent if r.url.path.endswith("/sources/s1/documents")])
    assert (read, pages - listed, await reader.read_once()) == (1, 1, 0)


async def test_an_unknown_kind_with_a_document_is_reconciled_and_one_without_is_skipped(
    conn, platform, store, reader
):
    uid, srv = await document(conn)
    platform.contents["crv_1"] = ["# A"]
    await accepted(conn, uid, srv, "crv_1")
    head = (await reader.sdk.feed(None))["next_cursor"]
    unknown = {"source_id": "s1", "priority": "normal", "occurred_at": datetime.now(UTC)}

    await reader.enqueue(
        [
            unknown | {"position": head, "kind": "document_renamed", "document_uid": uid},
            unknown | {"position": head, "kind": "tenant_settings_changed"},
        ],
        head,
    )
    runs = [await reader.work_once(), await reader.work_once()]

    assert runs == [True, False]
    assert await entries(store) == [(uid, "s1/hr-all", "crv_1", "# A")]
    assert (await reader.read_once()) == 0  # the cursor moved past both


async def test_a_backlog_of_one_document_runs_once_whatever_the_order_of_its_events(
    conn, platform, store, reader
):
    uid, srv = await document(conn)
    platform.contents |= {"crv_1": ["# one"], "crv_2": ["# two"]}
    await accepted(conn, uid, srv, "crv_1")
    await revised(conn, uid, "srv_2")
    await accepted(conn, uid, "srv_2", "crv_2")
    events = (await reader.sdk.feed(await _cursor(store)))["events"]

    await reader.enqueue(events[::-1] + events, events[-1]["position"])  # reversed, then repeated
    await settle(reader)

    assert len(events) == 2
    assert (platform.reads("crv_1"), platform.reads("crv_2")) == (0, 1)
    assert await entries(store) == [(uid, "s1/hr-all", "crv_2", "# two")]


async def test_coalescing_never_loses_a_deletion_and_an_event_during_a_run_runs_again(
    conn, platform, store, reader
):
    gone, srv = await document(conn, "A")
    platform.contents["crv_a1"] = ["# A"]
    await accepted(conn, gone, srv, "crv_a1")
    await delete(conn, "A")  # queued with the acceptance: one narrowing run
    await settle(reader)
    assert (platform.reads("crv_a1"), await entries(store)) == (0, [])

    uid, _ = await ready_document(conn, platform, reader, "B")
    await revised(conn, uid, "srv_b2")
    platform.contents["crv_b2"] = ["# B2"]
    platform.contents["crv_b3"] = ["# B3"]
    newer = asyncio.Event()

    async def meanwhile(request: httpx.Request) -> None:
        if request.url.path.endswith("/revisions/crv_b2") and not newer.is_set():
            newer.set()  # a newer revision and its event arrive while crv_b2 is being written
            await revised(conn, uid, "srv_b3", "3")
            await accepted(conn, uid, "srv_b3", "crv_b3")
            await reader.read_once()

    platform.hooks.append(meanwhile)
    await accepted(conn, uid, "srv_b2", "crv_b2")
    await settle(reader)

    assert await entries(store) == [(uid, "s1/hr-all", "crv_b3", "# B3")]
    assert await enforce(conn) == {"enforced": 1}


async def test_a_deletion_is_handled_while_an_update_holds_the_only_general_worker(
    conn, platform, store, reader
):
    busy, _ = await ready_document(conn, platform, reader, "A")
    await ready_document(conn, platform, reader, "B")
    await revised(conn, busy, "srv_a2")
    platform.contents["crv_a2"] = ["# A2"]
    entered, release = asyncio.Event(), asyncio.Event()

    async def hold(request: httpx.Request) -> None:
        if request.url.path.endswith("/revisions/crv_a2"):
            entered.set()
            await release.wait()

    platform.hooks.append(hold)
    await accepted(conn, busy, "srv_a2", "crv_a2")
    await reader.read_once()
    general = asyncio.create_task(reader.work_once())
    await entered.wait()
    await delete(conn, "B")
    await reader.read_once()

    assert await reader.work_once(narrowing_only=True)
    enforced = await enforce(conn)
    release.set()
    await general

    assert enforced == {"enforced": 1}
    assert [e[2] for e in await entries(store)] == ["crv_a2"]


async def test_a_general_worker_takes_a_deletion_before_the_updates_queued_ahead_of_it(
    conn, platform, store, reader
):
    a, _ = await ready_document(conn, platform, reader, "A")
    b, _ = await ready_document(conn, platform, reader, "B")
    await revised(conn, a, "srv_a2")
    platform.contents["crv_a2"] = ["# A2"]
    await accepted(conn, a, "srv_a2", "crv_a2")
    await delete(conn, "B")
    await reader.read_once()

    assert await reader.work_once()

    assert await enforce(conn) == {"enforced": 1}  # B first
    assert [e[2] for e in await entries(store)] == ["crv_a1"]


async def test_the_heartbeat_at_rest_matches_the_mirror_and_a_tampered_store_does_not(
    conn, platform, store, reader
):
    await ready_document(conn, platform, reader, "A")
    await ready_document(conn, platform, reader, "B")
    at_rest = await reader.heartbeat()
    async with store.connection() as projection_conn:
        await projection_conn.execute("UPDATE entry SET canonical_revision_id = 'crv_x'")

    tampered = await reader.heartbeat()

    assert at_rest["b1"]["repair_requested"] is None
    assert tampered["b1"]["repair_requested"]["reason"] == "heartbeat_mismatch"


async def test_the_cursor_is_reported_without_new_events_and_lag_is_measured(
    conn, platform, reader
):
    cursors = [r for r in platform.sent if r.url.path.endswith("/consumers/retrieval/cursor")]

    assert await reader.read_once() == 0

    after = [r for r in platform.sent if r.url.path.endswith("/consumers/retrieval/cursor")]
    assert len(after) == len(cursors) + 1
    await feed.observe(conn)
    assert (
        REGISTRY.get_sample_value("kp_feed_consumer_lag_seconds", {"projection": "retrieval"}) == 0
    )


async def test_a_restarted_reader_continues_from_its_saved_position(conn, platform, store, reader):
    uid, srv = await document(conn, "A")
    platform.contents["crv_a1"] = ["# A"]
    entered = asyncio.Event()

    async def crash_point(request: httpx.Request) -> None:
        if request.url.path.endswith("/registrations"):
            entered.set()
            await asyncio.Event().wait()  # the process dies here

    platform.hooks.append(crash_point)
    await accepted(conn, uid, srv, "crv_a1")
    await reader.read_once()
    run = asyncio.create_task(reader.work_once())
    await entered.wait()
    run.cancel()
    platform.hooks.clear()
    later, later_srv = await document(conn, "B")  # while the reader is down
    platform.contents["crv_b1"] = ["# B"]
    await accepted(conn, later, later_srv, "crv_b1")

    restarted = projection(platform, store)
    await restarted.start()
    await settle(restarted)

    assert [e[0] for e in await entries(store)] == sorted([uid, later])
    assert (await readiness(platform, "A"), await readiness(platform, "B")) == ("ready", "ready")
    assert (await restarted.heartbeat())["b1"]["repair_requested"] is None


async def test_a_canary_in_the_content_stays_out_of_logs_reports_and_metrics(
    conn, platform, store, reader, caplog
):
    canary = f"CANARY-{uuid.uuid4().hex}"
    caplog.set_level(logging.DEBUG)
    uid, srv = await document(conn)
    platform.contents["crv_1"] = [f"# {canary}", canary]
    await accepted(conn, uid, srv, "crv_1")
    await settle(reader)
    stored = await entries(store)
    await delete(conn)
    await settle(reader)
    await reader.heartbeat()

    sent = b"".join(r.content for r in platform.sent)
    assert canary not in caplog.text
    assert canary.encode() not in sent
    assert canary.encode() not in generate_latest(REGISTRY)
    assert canary in stored[0][3]  # it did pass through the projection
    assert uid in caplog.text and uid.encode() in sent  # and each sink sees what it is given


async def found(store, text: str) -> list[str]:
    """The Documents #279's search finds for `text` in the serving Build, in Resource s1/hr-all."""
    return [hit.document_uid for hit in await query.search(store, text, ["s1/hr-all"], False, 10)]


async def test_a_first_build_reads_the_documents_accepted_before_it_started(conn, platform, store):
    await profile(conn, "retrieval")
    uid, srv = await document(conn)
    platform.contents["crv_1"] = ["# Before"]
    await accepted(conn, uid, srv, "crv_1")
    started = projection(platform, store)

    await started.start()
    await started.read_once()  # nothing new on the feed, but the Sources are not read yet
    early = await (await conn.execute("SELECT state FROM build")).fetchall()
    await settle(started)

    assert early == [("building",)]
    assert await readiness(platform) == "ready"
    assert await found(store, "Before") == [uid]


async def _cursor(store) -> str:
    async with store.connection() as conn:
        [(cursor,)] = await (await conn.execute("SELECT cursor FROM reader")).fetchall()
    return cursor


async def test_the_process_refuses_to_start_beside_another_on_the_same_database(store):
    url = store.conninfo
    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as other:
        await other.execute("SELECT pg_advisory_lock(%s)", (cli.LOCK,))
        code = await cli.run("http://api", "c", url, "retrieval", "b1", 1, 1, 60, 0)

    assert code == 3


def test_a_missing_setting_exits_2(monkeypatch, root_logging):
    monkeypatch.delenv("KP_PLATFORM_URL", raising=False)
    httpx_log = logging.getLogger("httpx")
    level = httpx_log.level
    try:
        assert cli.main() == 2
    finally:
        httpx_log.setLevel(level)  # main() quiets httpx for the whole process


async def test_the_running_process_serves_a_document_and_stops_on_its_signal(conn, platform, store):
    await profile(conn, "retrieval")
    running = projection(platform, store)
    running.poll_s = 0.05
    stop = asyncio.Event()
    task = asyncio.create_task(running.run(stop, workers=2, narrowing_workers=1, heartbeat_s=0.1))
    uid, srv = await document(conn)
    platform.contents["crv_1"] = ["# A"]
    await accepted(conn, uid, srv, "crv_1")
    for _ in range(100):
        if await readiness(platform) == "ready":
            break
        await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, 5)

    assert await readiness(platform) == "ready"
    beats = [r for r in platform.sent if r.url.path.endswith("/heartbeats")]
    assert beats and (await running.heartbeat())["b1"]["repair_requested"] is None


async def test_a_content_outage_keeps_the_entry_and_a_refused_read_reports_the_stored_revision(
    conn, platform, store, reader
):
    uid, _ = await ready_document(conn, platform, reader)
    await revised(conn, uid, "srv_2")
    platform.contents["crv_2"] = ["# A2"]
    error = {"code": 503, "status": "UNAVAILABLE", "message": "m"}
    reason = [{"reason": "STORAGE_UNAVAILABLE"}]  # #268 names its reasons
    answer = httpx.Response(503, json={"error": error | {"details": reason}})

    async def storage(request: httpx.Request) -> httpx.Response | None:
        return answer if request.url.path.endswith("/revisions/crv_2") else None

    platform.hooks.append(storage)
    await accepted(conn, uid, "srv_2", "crv_2")
    await reader.read_once()
    failed = sample("kp_projection_failures_total", step="reconcile", reason="STORAGE_UNAVAILABLE")
    assert await reader.work_once()  # the run fails and is retried
    outage = (await entries(store), await mirror(conn))
    counted = sample("kp_projection_failures_total", step="reconcile", reason="STORAGE_UNAVAILABLE")
    assert counted - failed == 1
    answer = httpx.Response(410, json={"error": {"status": "FAILED_PRECONDITION"}})
    assert await reader.work_once()  # the read is refused: the write is dropped
    refused = await mirror(conn)

    assert outage == (
        [(uid, "s1/hr-all", "crv_a1", "# A\n\nbody")],
        [(uid, "s1/hr-all", "pending", "crv_2")],
    )
    assert refused == [(uid, "s1/hr-all", "included", "crv_a1")]  # what the store holds


async def test_an_active_document_without_a_current_revision_is_removed(
    conn, platform, store, reader
):
    uid, _ = await ready_document(conn, platform, reader)
    async with conn.transaction():  # DR §6: invalidated after acceptance
        await conn.execute(
            "UPDATE document SET current_source_revision_id = NULL,"
            " current_canonical_revision_id = NULL WHERE document_uid = %s",
            (uid,),
        )
        await feed.append(
            conn,
            "current_revision_changed",
            tenant_id="t1",
            source_id="s1",
            document_uid=uid,
            priority="narrowing",
        )

    await settle(reader)

    assert await entries(store) == []
    assert await mirror(conn) == [(uid, "s1/hr-all", "removed", "crv_a1")]


async def test_a_switch_sent_but_not_recorded_before_a_crash_is_sent_again_with_its_number(
    conn, platform, store, reader
):
    async with store.connection() as projection_conn:  # the platform took it; the crash came first
        await projection_conn.execute("UPDATE build SET state = 'building'")
        await projection_conn.execute("UPDATE switch SET taken_at = NULL")
    restarted = projection(platform, store)

    await restarted.start()
    await settle(restarted)

    builds = [r for r in platform.sent if r.method == "PUT" and "/builds/" in r.url.path]
    assert [json.loads(r.content)["state"] for r in builds] == ["building", "serving", "serving"]
    assert len({json.loads(r.content)["switch_seq"] for r in builds[1:]}) == 1
    async with store.connection() as projection_conn:
        [(state,)] = await (await projection_conn.execute("SELECT state FROM build")).fetchall()
    assert state == "serving"


@pytest.mark.network
async def test_the_process_switches_its_build_reports_its_cursor_and_ends_0_on_sigterm(
    conn, pool, store
):
    await profile(conn, "retrieval")
    ports = []
    for _ in range(2):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            ports.append(probe.getsockname()[1])
    api_port, metrics_port = ports
    application = app(
        FakeAuthorizer(),
        {digest("retrieval"): "retrieval"},
        {},
        pool,
        INTAKE,
        pipelines={digest("retrieval"): PIPELINES["retrieval"]},
    )
    server = uvicorn.Server(uvicorn.Config(application, port=api_port, log_config=None))
    serving = asyncio.create_task(server.serve())
    while not server.started and not serving.done():
        await asyncio.sleep(0.05)
    env = os.environ | {
        "KP_PLATFORM_URL": f"http://127.0.0.1:{api_port}",
        "KP_PROJECTION_CREDENTIAL": "retrieval",
        "KP_PROJECTION_DATABASE_URL": store.conninfo,
        "KP_PROJECTION_WORKERS": "1",
        "KP_PROJECTION_NARROWING_WORKERS": "0",
        "KP_PROJECTION_HEARTBEAT_S": "1",
        "KP_PROJECTION_METRICS_PORT": str(metrics_port),
    }
    code = "import sys; from kp_reference_projection.cli import main; sys.exit(main())"
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", code, env=env, stderr=asyncio.subprocess.PIPE
    )
    try:
        state = None
        for _ in range(100):
            row = await (await conn.execute("SELECT state FROM build")).fetchone()
            if (state := row and row[0]) == "serving":
                break
            await asyncio.sleep(0.1)
        async with httpx.AsyncClient() as scraper:
            metrics = (await scraper.get(f"http://127.0.0.1:{metrics_port}/metrics")).text
        cursor = await (await conn.execute("SELECT 1 FROM consumer_cursor")).fetchone()
    finally:
        process.send_signal(signal.SIGTERM)
        _, stderr = await asyncio.wait_for(process.communicate(), 10)
        server.should_exit = True
        await serving

    assert (state, cursor) == ("serving", (1,))
    assert "kp_projection_backlog" in metrics
    assert process.returncode == 0, stderr.decode()[-2000:]
