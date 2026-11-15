"""The reconciler on Testcontainers PostgreSQL and Temporal (#95, admission spec §9)."""

import asyncio
from collections import Counter

import pytest
from temporalio import workflow
from temporalio.api.common.v1 import WorkflowExecution
from temporalio.api.workflowservice.v1 import DeleteWorkflowExecutionRequest
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import UnsandboxedWorkflowRunner, Worker

from kp_admission.dispatcher import dispatch_due, temporal_start
from kp_admission.reconciler import reconcile
from tests.admission.support import queue, request, revision, runs

pytestmark = pytest.mark.docker

ERROR = {"domain": "kp-canonicalization", "reason": "PASSWORD_REQUIRED", "retryable": False}


@workflow.defn(name="paper-pdf")
class CannedWorkflow:
    """Ends as its start input's trace_id says, as the paper-pdf workflow returns."""

    @workflow.run
    async def run(self, start: dict) -> dict:
        ref = f"requests/{start['request_id']}/result.json"
        if start["trace_id"] == "complete":
            return {"outcome": "complete", "manifest_ref": ref}
        return {"outcome": "failed", "manifest_ref": ref, "error": ERROR}


async def test_the_reconciler_records_ended_workflows_and_leaves_running_ones(conn, temporal):
    ids = {
        trace: (await request(conn, *await revision(conn), trace_id=trace))[0]
        for trace in ("complete", "failed")
    }
    for name in ("terminated", "running"):  # on a queue that no worker polls
        ids[name] = (await request(conn, *await revision(conn), adopted_version="paper-pdf@9"))[0]
    assert await dispatch_due(conn, temporal_start(temporal, queue)) == 4
    async with Worker(
        temporal, task_queue=queue("paper-pdf@1"), workflows=[CannedWorkflow],
        workflow_runner=UnsandboxedWorkflowRunner(),
    ):  # fmt: skip
        for name in ("complete", "failed"):
            await temporal.get_workflow_handle(ids[name]).result()
    await temporal.get_workflow_handle(ids["terminated"]).terminate()

    assert await reconcile(conn, temporal) == Counter(recorded=3, running=1)

    cursor = await conn.execute(
        "SELECT request_id, state, terminal_at IS NOT NULL, error FROM request"
    )
    by_id = {row[0]: row[1:] for row in await cursor.fetchall()}
    assert by_id[ids["complete"]] == ("succeeded", True, None)
    assert by_id[ids["failed"]] == ("failed", True, ERROR)
    state, ended, error = by_id[ids["terminated"]]
    assert (state, ended) == ("failed", True)
    assert {key: error[key] for key in ("domain", "reason", "retryable", "metadata")} == {
        "domain": "admission.knowledge-platform",
        "reason": "WORKFLOW_ENDED_WITHOUT_RESULT",
        "retryable": True,
        "metadata": {"status": "TERMINATED"},
    }
    assert error["occurred_at"].endswith("Z")
    assert by_id[ids["running"]] == ("queued", False, None)
    assert await reconcile(conn, temporal) == Counter(running=1)


async def test_the_reconciler_redispatches_a_lost_workflow_under_the_same_id(conn, temporal):
    request_id, _ = await request(conn, *await revision(conn))
    start = temporal_start(temporal, queue)
    assert await dispatch_due(conn, start) == 1
    await temporal.workflow_service.delete_workflow_execution(
        DeleteWorkflowExecutionRequest(
            namespace=temporal.namespace,
            workflow_execution=WorkflowExecution(workflow_id=request_id),
        )
    )
    for _ in range(50):  # the server deletes in the background
        try:
            await temporal.get_workflow_handle(request_id).describe()
        except RPCError as gone:
            assert gone.status == RPCStatusCode.NOT_FOUND
            break
        await asyncio.sleep(0.1)

    assert await reconcile(conn, temporal) == Counter(redispatched=1)

    cursor = await conn.execute(
        "SELECT dispatched_at, redispatch_reason FROM outbox WHERE request_id = %s", (request_id,)
    )
    dispatched_at, reason = await cursor.fetchone()
    assert dispatched_at is None
    assert "not found" in reason
    assert await dispatch_due(conn, start) == 1
    assert await runs(temporal, request_id) == 1
    assert await reconcile(conn, temporal) == Counter(running=1)


async def test_a_missing_namespace_raises_and_sends_nothing_back(conn, temporal, temporal_address):
    await request(conn, *await revision(conn))
    assert await dispatch_due(conn, temporal_start(temporal, queue)) == 1
    elsewhere = await Client.connect(temporal_address, namespace="missing")

    with pytest.raises(RPCError) as raised:
        await reconcile(conn, elsewhere)

    assert raised.value.status == RPCStatusCode.NOT_FOUND
    cursor = await conn.execute("SELECT dispatched_at IS NOT NULL, redispatch_reason FROM outbox")
    assert await cursor.fetchone() == (True, None)
