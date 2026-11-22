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

from kp_admission import feed, reports
from kp_admission.dispatcher import dispatch_due, temporal_start
from kp_admission.reconciler import reconcile
from kp_admission.requests import record_outcome
from tests.admission.support import CANDIDATE, queue, request, revision, runs
from tests.admission.test_status import PIPELINE, report

pytestmark = pytest.mark.docker

ERROR = {
    "domain": "kp-canonicalization",
    "reason": "PASSWORD_REQUIRED",
    "retryable": False,
    "metadata": {"cause": "source", "category": "source"},
}


@workflow.defn(name="paper-pdf")
class CannedWorkflow:
    """Ends as its start input's trace_id says, as the paper-pdf workflow returns."""

    @workflow.run
    async def run(self, start: dict) -> dict:
        ref = f"requests/{start['request_id']}/result.json"
        if start["trace_id"] == "complete":
            return {"outcome": "complete", "manifest_ref": ref}
        if start["trace_id"] == "accepted":
            return {"outcome": "complete", "manifest_ref": ref, "candidate": CANDIDATE.model_dump()}
        if start["trace_id"] == "malformed":
            return {"outcome": "complete", "manifest_ref": ref, "candidate": {"ref": ""}}
        return {"outcome": "failed", "manifest_ref": ref, "error": ERROR}


async def test_the_reconciler_records_ended_workflows_and_leaves_running_ones(conn, temporal):
    ids = {
        trace: (await request(conn, *await revision(conn), trace_id=trace))[0]
        for trace in ("complete", "failed")
    }
    for name in ("terminated", "running"):  # on a queue that no worker polls
        ids[name] = (await request(conn, *await revision(conn), adopted_version="paper-pdf@9"))[0]
    # A platform refresh that fails leaves its Source Revision's outcome alone (spec §3).
    ids["refresh"] = (
        await request(conn, *await revision(conn), trace_id="failed", initiator="platform")
    )[0]
    assert await dispatch_due(conn, temporal_start(temporal, queue)) == 5
    async with Worker(
        temporal, task_queue=queue("paper-pdf@1"), workflows=[CannedWorkflow],
        workflow_runner=UnsandboxedWorkflowRunner(),
    ):  # fmt: skip
        for name in ("complete", "failed", "refresh"):
            await temporal.get_workflow_handle(ids[name]).result()
    await temporal.get_workflow_handle(ids["terminated"]).terminate()

    assert await reconcile(conn, temporal) == Counter(recorded=4, running=1)

    cursor = await conn.execute(
        "SELECT request_id, state, terminal_at IS NOT NULL, error, outcome"
        " FROM request JOIN source_revision USING (source_revision_id)"
    )
    by_id = {row[0]: row[1:] for row in await cursor.fetchall()}
    assert by_id[ids["complete"]] == ("succeeded", True, None, "pending")  # no candidate
    assert by_id[ids["failed"]] == ("failed", True, ERROR, "rejected")
    assert by_id[ids["refresh"]] == ("failed", True, ERROR, "pending")
    state, ended, error, outcome = by_id[ids["terminated"]]
    assert (state, ended, outcome) == ("failed", True, "failed")
    assert {key: error[key] for key in ("domain", "reason", "retryable", "metadata")} == {
        "domain": "admission.knowledge-platform",
        "reason": "WORKFLOW_ENDED_WITHOUT_RESULT",
        "retryable": True,
        "metadata": {"status": "TERMINATED"},
    }
    assert error["occurred_at"].endswith("Z")
    assert by_id[ids["running"]] == ("queued", False, None, "pending")
    assert await reconcile(conn, temporal) == Counter(running=1)


async def test_the_reconciler_accepts_a_lost_report_s_candidate_once(conn, temporal):
    """#251: the reconciler records the acceptance a lost last report would have, a malformed
    candidate ends the request without one, and an acceptance a report recorded first stays: a
    report and the reconciler both arriving is the resend of test_acceptance."""
    ids = {}
    for trace in ("accepted", "malformed", "reported"):
        uid, srv = await revision(conn)
        ids[trace] = (uid, (await request(conn, uid, srv, trace_id=trace))[0])
    assert await dispatch_due(conn, temporal_start(temporal, queue)) == 3
    async with Worker(
        temporal, task_queue=queue("paper-pdf@1"), workflows=[CannedWorkflow],
        workflow_runner=UnsandboxedWorkflowRunner(),
    ):  # fmt: skip
        for _, request_id in ids.values():
            await temporal.get_workflow_handle(request_id).result()
    reported_uid, reported_id = ids["reported"]
    assert await record_outcome(conn, reported_id, "succeeded", None, None, CANDIDATE)
    start = await feed.head(conn)

    assert await reconcile(conn, temporal) == Counter(recorded=2)

    current = {}
    for trace, (uid, _) in ids.items():
        state = await feed.document_state(conn, uid, None)
        assert state
        current[trace] = state.current and state.current.canonical_revision_id
    accepted_uid, accepted_id = ids["accepted"]
    assert current == {
        "accepted": "crv_" + accepted_id.removeprefix("req_"),
        "malformed": None,
        "reported": "crv_" + reported_id.removeprefix("req_"),
    }
    # The lost report arrives after all: it is taken and accepts nothing again.
    [(attempt_id,)] = await (
        await conn.execute("SELECT attempt_id FROM request WHERE request_id = %s", (accepted_id,))
    ).fetchall()
    late = report(accepted_id, 1, "finalize", "succeeded", attempt_id=attempt_id,
                  candidate=CANDIDATE.model_dump())  # fmt: skip
    taken = await reports.take(conn, PIPELINE, reports.Report.model_validate(late))
    assert taken.result == "recorded"
    found, _ = await feed.read(conn, start, limit=10)
    assert [e.document_uid for e in found] == [accepted_uid]  # once, and none for the reported one
    cursor = await conn.execute("SELECT count(*) FROM canonical_revision")
    assert await cursor.fetchone() == (2,)


async def test_the_reconciler_redispatches_a_lost_workflow_under_the_same_id(conn, temporal):
    request_id, _ = await request(conn, *await revision(conn))
    start = temporal_start(temporal, queue)
    assert await dispatch_due(conn, start) == 1
    await conn.execute(  # a report of the run about to be lost
        "UPDATE request SET last_report = '{\"seq\": 1}', reported_at = now()"
        " WHERE request_id = %s",
        (request_id,),
    )
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
        "SELECT dispatched_at, redispatch_reason, attempt_id, last_report, reported_at"
        " FROM outbox JOIN request USING (request_id) WHERE request_id = %s",
        (request_id,),
    )
    dispatched_at, reason, *attempt = await cursor.fetchone()
    assert dispatched_at is None
    assert attempt == [None, None, None]  # the lost run's reports no longer count
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
