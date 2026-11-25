"""The dispatcher on Testcontainers PostgreSQL and Temporal (#95, admission spec §9, §10). No
worker polls the queues, so started workflows stay running."""

import asyncio
import json
import subprocess
import sys
import uuid
from datetime import timedelta
from importlib.resources import files
from pathlib import Path

import psycopg
import pytest
from temporalio.common import WorkflowIDReusePolicy
from temporalio.service import RPCError, RPCStatusCode

from kp_admission.dispatcher import (
    BACKOFF_CAP_S,
    QUEUES,
    SEARCH_ATTRIBUTES,
    deployment_name,
    dispatch_due,
    priority,
    task_queue,
    temporal_start,
)
from tests.admission.crash import CRASHED
from tests.admission.support import FILES, queue, request, revision, runs

pytestmark = pytest.mark.docker
EXAMPLE = json.loads((files("kp_admission") / "workflow_start.json").read_text())


async def test_the_start_is_the_one_the_contract_example_describes(temporal):
    start_input = {**EXAMPLE["input"], "request_id": f"req_{uuid.uuid4().hex}"}

    await temporal_start(temporal, task_queue)(start_input)

    handle = temporal.get_workflow_handle(start_input["request_id"])
    described = await handle.describe()
    assert (described.workflow_type, described.task_queue) == (
        EXAMPLE["workflow"], EXAMPLE["task_queue"],
    )  # fmt: skip
    priority_key = EXAMPLE["priority_keys"][start_input["priority"]]
    assert described.raw_info.priority.priority_key == priority_key
    assert {key.name: described.typed_search_attributes.get(key)
            for key in SEARCH_ATTRIBUTES.values()} == EXAMPLE["search_attributes"]  # fmt: skip
    started = (await handle.fetch_history()).events[0].workflow_execution_started_event_attributes
    assert json.loads(started.input.payloads[0].data) == start_input


def test_the_gate_and_the_priorities_match_the_contract_example():
    assert deployment_name(EXAMPLE["input"]["adopted_version"]) == EXAMPLE["deployment"]
    assert list(QUEUES) == EXAMPLE["queues"]
    assert {p: priority(p).priority_key for p in EXAMPLE["priority_keys"]} == EXAMPLE[
        "priority_keys"
    ]


async def test_the_dispatcher_starts_the_canonical_workflow_with_the_start_input(conn, temporal):
    uid, srv = await revision(conn)
    request_id, _ = await request(conn, uid, srv, priority="low")

    assert await dispatch_due(conn, temporal_start(temporal, queue)) == 1

    handle = temporal.get_workflow_handle(request_id)
    described = await handle.describe()
    assert (described.workflow_type, described.task_queue) == ("paper-pdf", "test-paper-pdf-1")
    assert described.raw_info.priority.priority_key == 4  # admission priority low
    assert {key.name: described.typed_search_attributes.get(key)
            for key in SEARCH_ATTRIBUTES.values()} == {
        "DocumentUid": uid, "SourceRevisionId": srv, "TraceId": "4bf92f3577b34da6",
    }  # fmt: skip
    started = (await handle.fetch_history()).events[0].workflow_execution_started_event_attributes
    assert set(json.loads(started.input.payloads[0].data)) == set(EXAMPLE["input"])
    assert json.loads(started.input.payloads[0].data) == {
        "request_id": request_id,
        "document_uid": uid,
        "source_revision_id": srv,
        "files": FILES,
        "adopted_version": "paper-pdf@1",
        "adoption_sequence": 7,
        "initiator": "source",
        "priority": "low",
        "trace_id": "4bf92f3577b34da6",
    }
    cursor = await conn.execute(
        "SELECT attempts, dispatched_at IS NOT NULL, attempt_id FROM outbox JOIN request"
        " USING (request_id) WHERE request_id = %s",
        (request_id,),
    )
    assert await cursor.fetchone() == (1, True, described.run_id)
    assert await dispatch_due(conn, temporal_start(temporal, queue)) == 0
    assert await runs(temporal, request_id) == 1


async def test_a_row_one_dispatcher_holds_does_not_block_another(conn, dsn, temporal):
    request_ids = [(await request(conn, *await revision(conn)))[0] for _ in range(3)]
    real = temporal_start(temporal, queue)
    holding, release = asyncio.Event(), asyncio.Event()

    async def held_start(start_input):
        holding.set()
        await release.wait()
        return await real(start_input)

    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as other:
        first = asyncio.create_task(dispatch_due(conn, held_start))
        await holding.wait()
        assert await asyncio.wait_for(dispatch_due(other, real), timeout=10) == 2
        release.set()
        assert await first == 1

    assert [await runs(temporal, request_id) for request_id in request_ids] == [1, 1, 1]


@pytest.mark.parametrize("point", ["after_commit", "before_start", "after_start"])
async def test_a_process_killed_at_a_failpoint_leaves_one_workflow_per_request(
    conn, dsn, temporal, temporal_address, point
):
    crash = subprocess.run(
        [sys.executable, "-m", "tests.admission.crash", point, dsn, temporal_address],
        cwd=Path(__file__).parents[2],
        timeout=60,
    )

    assert crash.returncode == CRASHED
    cursor = await conn.execute("SELECT request_id, dispatched_at FROM outbox")
    [(request_id, dispatched_at)] = await cursor.fetchall()
    assert dispatched_at is None
    try:
        await temporal.get_workflow_handle(request_id).describe()
        started = True
    except RPCError as missing:
        assert missing.status == RPCStatusCode.NOT_FOUND
        started = False
    assert started == (point == "after_start")

    assert await dispatch_due(conn, temporal_start(temporal, queue)) == 1
    assert await runs(temporal, request_id) == 1


async def test_rows_wait_through_a_temporal_outage_and_all_start_once_after_it(
    conn, temporal, temporal_server
):
    request_ids = [(await request(conn, *await revision(conn)))[0] for _ in range(2)]
    start = temporal_start(temporal, queue, rpc_timeout=timedelta(seconds=2))

    temporal_server.get_wrapped_container().pause()
    try:
        request_ids.append((await request(conn, *await revision(conn)))[0])  # admission stays up
        assert await dispatch_due(conn, start) == 0
        assert await dispatch_due(conn, start) == 0
        # The backoff counts from the failure, not from the claim rpc_timeout before it.
        cursor = await conn.execute(
            "SELECT available_at - clock_timestamp() BETWEEN interval '0' AND interval '1 second'"
            " FROM outbox WHERE request_id = %s",
            (request_ids[1],),
        )
        assert await cursor.fetchone() == (True,)
    finally:
        temporal_server.get_wrapped_container().unpause()

    cursor = await conn.execute("SELECT request_id, attempts, dispatched_at FROM outbox")
    assert sorted(await cursor.fetchall()) == sorted(
        [(request_ids[0], 1, None), (request_ids[1], 1, None), (request_ids[2], 0, None)]
    )
    dispatched = 0
    for _ in range(50):  # the two retried rows are due again a second after they failed
        dispatched += await dispatch_due(conn, start)
        if dispatched == 3:
            break
        await asyncio.sleep(0.1)
    assert dispatched == 3
    assert [await runs(temporal, request_id) for request_id in request_ids] == [1, 1, 1]


async def test_redispatching_an_ended_workflow_starts_nothing_and_a_duplicate_would_show(
    conn, temporal
):
    request_id, _ = await request(conn, *await revision(conn))
    start = temporal_start(temporal, queue)
    assert await dispatch_due(conn, start) == 1
    handle = temporal.get_workflow_handle(request_id)
    await handle.terminate()

    await conn.execute(
        "UPDATE outbox SET dispatched_at = NULL WHERE request_id = %s", (request_id,)
    )
    await conn.execute("UPDATE request SET attempt_id = NULL WHERE request_id = %s", (request_id,))
    assert await dispatch_due(conn, start) == 1  # REJECT_DUPLICATE: already started counts
    assert await runs(temporal, request_id) == 1
    cursor = await conn.execute(
        "SELECT attempt_id FROM request WHERE request_id = %s", (request_id,)
    )
    assert await cursor.fetchone() == ((await handle.describe()).run_id,)  # the run it started

    # Negative control: runs() counts ended runs, so a second run under the ID shows as 2.
    await temporal.start_workflow(
        "paper-pdf", id=request_id, task_queue="test",
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
    )  # fmt: skip
    for _ in range(50):
        if await runs(temporal, request_id) == 2:
            break
        await asyncio.sleep(0.1)
    assert await runs(temporal, request_id) == 2


async def test_a_row_that_failed_many_times_waits_the_cap_and_no_longer(conn):
    request_id, _ = await request(conn, *await revision(conn))
    await conn.execute("UPDATE outbox SET attempts = 5000 WHERE request_id = %s", (request_id,))

    async def temporal_down(start_input):
        raise RuntimeError("Temporal is down")

    assert await dispatch_due(conn, temporal_down) == 0

    cursor = await conn.execute(
        "SELECT attempts, available_at - clock_timestamp() FROM outbox WHERE request_id = %s",
        (request_id,),
    )
    attempts, wait = await cursor.fetchone()
    assert attempts == 5001
    assert timedelta(seconds=BACKOFF_CAP_S - 1) <= wait <= timedelta(seconds=BACKOFF_CAP_S)


async def dispatch_order(conn) -> list[str]:
    cursor = await conn.execute(
        "SELECT request_id FROM outbox WHERE dispatched_at IS NOT NULL ORDER BY dispatched_at"
    )
    return [request_id for (request_id,) in await cursor.fetchall()]


async def test_sources_take_turns_and_one_at_its_budget_waits(conn, temporal):
    a1, a2, a3 = [(await request(conn, *await revision(conn, "a")))[0] for _ in range(3)]
    (b1, _) = await request(conn, *await revision(conn, "b"))
    start = temporal_start(temporal, queue)

    assert await dispatch_due(conn, start, per_source=2) == 3

    assert await dispatch_order(conn) == [a1, b1, a2]  # b1 is newer than a2 and a3
    await conn.execute("UPDATE request SET state = 'succeeded' WHERE request_id = %s", (a1,))
    assert await dispatch_due(conn, start, per_source=2) == 1
    assert (await dispatch_order(conn))[-1] == a3


async def test_normal_priority_goes_before_low_and_the_global_budget_holds(conn, temporal):
    (low, _) = await request(conn, *await revision(conn, "a"), priority="low")
    normal = [(await request(conn, *await revision(conn, source)))[0] for source in "bc"]

    assert await dispatch_due(conn, temporal_start(temporal, queue), in_flight=2) == 2

    assert await dispatch_order(conn) == normal
    assert low not in await dispatch_order(conn)


async def test_a_queued_request_of_a_withdrawn_version_ends_instead_of_starting(conn, temporal):
    """#98: VERSION_WITHDRAWN, the revision's outcome left as it was, so the scan reruns it."""
    withdrawn = await request(conn, *await revision(conn), adopted_version="paper-pdf@2")
    kept = await request(conn, *await revision(conn))
    await conn.execute(
        "INSERT INTO withdrawn_version (tenant_id, media_type, version)"
        " VALUES ('t1', 'application/pdf', 'paper-pdf@2')"
    )

    assert await dispatch_due(conn, temporal_start(temporal, queue)) == 1

    cursor = await conn.execute(
        "SELECT request_id, state, error ->> 'reason', outcome, terminal_at IS NOT NULL"
        " FROM request JOIN source_revision USING (source_revision_id)"
    )
    by_id = {row[0]: row[1:] for row in await cursor.fetchall()}
    assert by_id[withdrawn[0]] == ("failed", "VERSION_WITHDRAWN", "pending", True)
    assert by_id[kept[0]][:2] == ("queued", None)
    assert await runs(temporal, withdrawn[0]) == 0
    assert await dispatch_due(conn, temporal_start(temporal, queue)) == 0
