"""The adoption gate on a real Temporal server (#261): the version's five queues on its current
build, and a test workflow whose result is complete, on that build. A stand-in for the canonical
workflow returns what the test sets, so it ends `COMPLETED` in Temporal whatever its outcome."""

import asyncio
import contextlib
import random
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from google.protobuf.timestamp_pb2 import Timestamp
from temporalio import workflow
from temporalio.api.deployment.v1 import RoutingConfig, WorkerDeploymentInfo
from temporalio.api.enums.v1 import RoutingConfigUpdateState
from temporalio.api.workflowservice.v1 import (
    DescribeWorkerDeploymentRequest,
    SetWorkerDeploymentCurrentVersionRequest,
)
from temporalio.client import Client
from temporalio.common import VersioningBehavior, WorkerDeploymentVersion
from temporalio.service import RPCError
from temporalio.worker import UnsandboxedWorkflowRunner, Worker, WorkerDeploymentConfig

from kp_admission import adoption, gate
from kp_admission.storage import FakeObjectStore
from kp_canonicalization.promoter import promote
from kp_canonicalization.workflow import QUEUES, WORKFLOW, deployment_name

pytestmark = pytest.mark.docker

PDF = "application/pdf"
STARTS: list[dict[str, Any]] = []
OUTCOME = {"outcome": "complete"}


@workflow.defn(name=WORKFLOW)
class StandIn:
    """Returns OUTCOME, as the canonical workflow returns its result."""

    @workflow.run
    async def run(self, start: Any) -> dict[str, Any]:
        STARTS.append(start)
        return dict(OUTCOME)


@pytest.fixture
def version() -> str:
    """A Processing Profile version of its own: the Temporal server is shared."""
    return f"gate-pdf@{random.randrange(1, 10**9)}"


@contextlib.asynccontextmanager
async def build(client: Client, version: str, build_id: str, queues=QUEUES):
    """A build's pods, one versioned worker per queue, made current as the promoter does."""
    deployment = deployment_name(version)
    config = WorkerDeploymentConfig(
        WorkerDeploymentVersion(deployment, build_id),
        use_worker_versioning=True,
        default_versioning_behavior=VersioningBehavior.PINNED,
    )
    async with contextlib.AsyncExitStack() as stack:
        for queue in queues:
            await stack.enter_async_context(
                Worker(
                    client,
                    task_queue=f"{deployment}.{queue}",
                    workflows=[StandIn],
                    workflow_runner=UnsandboxedWorkflowRunner(),
                    deployment_config=config,
                )
            )
        if queues == QUEUES:
            wanted = {deployment: {"builds": [build_id], "current": build_id}}
            for _ in range(80):
                await promote(client, wanted)
                if await current(client, deployment) == build_id:
                    break
                await asyncio.sleep(0.5)
        yield


async def current(client: Client, deployment: str) -> str | None:
    """The deployment's current build once its routing change is done."""
    try:
        described = await client.workflow_service.describe_worker_deployment(
            DescribeWorkerDeploymentRequest(namespace=client.namespace, deployment_name=deployment)
        )
    except RPCError:  # no pod has polled yet
        return None
    info = described.worker_deployment_info
    done = RoutingConfigUpdateState.ROUTING_CONFIG_UPDATE_STATE_COMPLETED
    # Right after a switch the routing change reads IN_PROGRESS for a moment.
    if info.routing_config_update_state != done:
        return None
    return info.routing_config.current_deployment_version.build_id


async def settled(check: gate.TemporalGate, version: str, adopted_before: bool = False):
    """Runs the gate as its CronJob does until it stops waiting on the test workflow."""
    for _ in range(100):
        passed, reason = await check(PDF, version, adopted_before)
        if reason not in ("check_started", "check_running"):
            return passed, reason
        await asyncio.sleep(0.2)
    raise TimeoutError("the test workflow did not end")


@pytest.fixture
def make_gate(conn, temporal):
    store = FakeObjectStore()

    def make(**options) -> gate.TemporalGate:
        return gate.TemporalGate(conn, temporal, store, "t1", **options)

    make.store = store  # type: ignore[attr-defined]
    return make


async def test_a_version_not_deployed_or_not_on_all_five_queues_waits(make_gate, temporal, version):
    check = make_gate()

    assert await check(PDF, version, False) == (False, "not_deployed")
    async with build(temporal, version, "r1", queues=QUEUES[:4]):
        assert await check(PDF, version, False) in {
            (False, "no_current_build"),
            (False, "not_deployed"),
        }
    assert all(s["adopted_version"] != version for s in STARTS)


async def test_a_current_build_missing_a_queue_waits(make_gate, temporal, version):
    """A build made current without its d3 workers, as Temporal allows on request."""
    deployment = deployment_name(version)
    async with build(temporal, version, "r1", queues=QUEUES[:4]):
        for _ in range(80):
            try:
                await temporal.workflow_service.set_worker_deployment_current_version(
                    SetWorkerDeploymentCurrentVersionRequest(
                        namespace=temporal.namespace,
                        deployment_name=deployment,
                        build_id="r1",
                        ignore_missing_task_queues=True,
                    )
                )
                break
            except RPCError:  # the build has not polled yet
                await asyncio.sleep(0.25)
        result = await make_gate()(PDF, version, True)

    assert result == (False, "queues_not_polled")


async def test_a_new_version_passes_once_its_test_workflow_completes_on_the_current_build(
    make_gate, temporal, version, monkeypatch
):
    monkeypatch.setitem(OUTCOME, "outcome", "complete")
    check = make_gate()
    async with build(temporal, version, "r1"):
        first = await check(PDF, version, False)
        result = await settled(check, version)
        described = await temporal.workflow_service.describe_worker_deployment(
            DescribeWorkerDeploymentRequest(
                namespace=temporal.namespace, deployment_name=deployment_name(version)
            )
        )
    changed = described.worker_deployment_info.routing_config.current_version_changed_time
    # The fallback's clock: Temporal sets it when the build became current.
    assert timedelta(0) <= datetime.now(UTC) - changed.ToDatetime(UTC) < timedelta(minutes=1)

    assert first == (False, "check_started")
    assert result == (True, "")
    [start] = [s for s in STARTS if s["adopted_version"] == version]
    assert start["request_id"].startswith(adoption.CHECK_PREFIX)
    [file] = start["files"]
    assert file["custody_ref"] == f"s3://kp-custody/checks/{file['sha256']}"
    assert await make_gate.store.head(f"checks/{file['sha256']}")  # type: ignore[attr-defined]


async def test_a_test_workflow_whose_result_is_failed_blocks_and_is_replaced_by_a_new_one(
    make_gate, temporal, version, monkeypatch
):
    """Temporal reads the stand-in `COMPLETED` while its outcome is failed."""
    monkeypatch.setitem(OUTCOME, "outcome", "failed")
    check = make_gate()
    async with build(temporal, version, "r1"):
        await check(PDF, version, False)
        blocked = await settled(check, version)
        again = await check(PDF, version, False)  # within CHECK_RETRY: no new test workflow
        monkeypatch.setitem(OUTCOME, "outcome", "complete")
        retried = make_gate(check_retry=timedelta(0))
        passed = await settled(retried, version)

    starts = [s for s in STARTS if s["adopted_version"] == version]
    assert blocked == again == (False, "check_failed")
    assert passed == (True, "")
    assert len(starts) == 2
    assert len({s["document_uid"] for s in starts}) == 2  # a new document each time
    assert len({s["request_id"] for s in starts}) == 2


async def test_a_pass_on_an_older_build_does_not_count_for_the_current_one(
    make_gate, temporal, version, monkeypatch
):
    monkeypatch.setitem(OUTCOME, "outcome", "complete")
    check = make_gate()
    async with build(temporal, version, "r1"):
        await check(PDF, version, False)
        assert await settled(check, version) == (True, "")
    async with build(temporal, version, "r2"):
        assert await check(PDF, version, False) == (False, "check_started")
        assert await settled(check, version) == (True, "")


async def test_a_version_adopted_before_runs_no_test_workflow(
    make_gate, temporal, version, monkeypatch
):
    monkeypatch.setitem(OUTCOME, "outcome", "failed")  # the model service is down
    check = make_gate()
    async with build(temporal, version, "r1"):
        assert await check(PDF, version, True) == (True, "")

    assert all(s["adopted_version"] != version for s in STARTS)


def info(state: int, changed: datetime) -> WorkerDeploymentInfo:
    stamp = Timestamp()
    stamp.FromDatetime(changed)
    return WorkerDeploymentInfo(
        routing_config=RoutingConfig(current_version_changed_time=stamp),
        routing_config_update_state=state,  # type: ignore[arg-type]
    )


def test_routing_stuck_in_progress_falls_back_after_the_limit():
    """temporalio/temporal#11842: the state can stay IN_PROGRESS on a healthy build."""
    now = datetime(2026, 11, 23, 12, tzinfo=UTC)
    progress = RoutingConfigUpdateState.ROUTING_CONFIG_UPDATE_STATE_IN_PROGRESS
    done = RoutingConfigUpdateState.ROUTING_CONFIG_UPDATE_STATE_COMPLETED
    limit = timedelta(minutes=10)

    assert gate.routing(info(done, now), now, limit) == "completed"
    assert gate.routing(info(progress, now - timedelta(minutes=9)), now, limit) == "waiting"
    assert gate.routing(info(progress, now - timedelta(minutes=11)), now, limit) == "fallback"
    unknown = WorkerDeploymentInfo(routing_config_update_state=progress)  # type: ignore[arg-type]
    assert gate.routing(unknown, now, limit) == "waiting"
