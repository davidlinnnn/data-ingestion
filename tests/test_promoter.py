"""The promoter against a real Temporal dev server (#135, #178): what one run does to Worker
Deployments, and when it raises an alarm. The server refreshes drainage every 2 s and forgets
pollers after 5 s; the defaults are minutes."""

import asyncio
import contextlib
import json
import logging
import shutil
from datetime import timedelta

import pytest
from temporalio import workflow
from temporalio.api.workflowservice.v1 import DescribeWorkerDeploymentRequest
from temporalio.client import Client
from temporalio.common import VersioningBehavior, WorkerDeploymentVersion
from temporalio.service import RPCError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import UnsandboxedWorkflowRunner, Worker, WorkerDeploymentConfig

from kp_canonicalization import cli
from kp_canonicalization.promoter import promote
from kp_canonicalization.workflow import QUEUES

pytestmark = pytest.mark.network

FAST = [
    'matching.wv.VersionDrainageStatusRefreshInterval="2s"',
    'matching.wv.VersionDrainageStatusVisibilityGracePeriod="2s"',
    'matching.PollerHistoryTTL="5s"',
]
DEPLOYMENT = "paper-pdf-7"
ORCHESTRATION = f"{DEPLOYMENT}.orchestration"


@pytest.fixture
async def client():
    async with await WorkflowEnvironment.start_local(
        dev_server_existing_path=shutil.which("temporal"),
        dev_server_extra_args=[a for value in FAST for a in ("--dynamic-config-value", value)],
    ) as env:
        yield env.client


@workflow.defn(name="held")
class Held:
    """Stays open until released, like a document still in processing."""

    def __init__(self) -> None:
        self.released = False

    @workflow.signal
    def release(self) -> None:
        self.released = True

    @workflow.run
    async def run(self) -> str:
        await workflow.wait_condition(lambda: self.released)
        return workflow.info().get_current_deployment_version().build_id  # type: ignore[union-attr]


@contextlib.asynccontextmanager
async def build(client: Client, build_id: str, queues=QUEUES, deployment: str = DEPLOYMENT):
    """A build's pods: one versioned worker per queue, as worker.make_worker configures them."""
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
                    workflows=[Held],
                    workflow_runner=UnsandboxedWorkflowRunner(),
                    deployment_config=config,
                )
            )
        yield


async def state(client: Client, deployment: str = DEPLOYMENT) -> tuple[str | None, set[str]]:
    """(current build, every build Temporal still holds); (None, set()) for no deployment."""
    try:
        described = await client.workflow_service.describe_worker_deployment(
            DescribeWorkerDeploymentRequest(namespace=client.namespace, deployment_name=deployment)
        )
    except RPCError:
        return None, set()
    info = described.worker_deployment_info
    current = info.routing_config.current_deployment_version.build_id or None
    return current, {v.deployment_version.build_id for v in info.version_summaries}


async def promoted(client: Client, wanted: dict, until, limit_s: float = 40) -> list[list[str]]:
    """Run the promoter as its CronJob does, again and again, until state() satisfies `until`.
    Returns each run's alarms."""
    runs = []
    for _ in range(int(limit_s / 0.5)):
        runs.append(await promote(client, wanted))
        if until(await state(client)):
            return runs
        await asyncio.sleep(0.5)
    raise TimeoutError(f"state {await state(client)} after {limit_s} s; alarms {runs[-1]}")


def values(*builds: str, current: str) -> dict:
    return {DEPLOYMENT: {"builds": list(builds), "current": current}}


async def test_a_build_becomes_current_once_it_polls_all_five_queues(client, caplog):
    caplog.set_level(logging.INFO, logger="kp_canonicalization.promoter")
    wanted = values("r1", current="r1")

    assert await promote(client, wanted) == []  # no pod yet: nothing to do, nothing to report
    async with build(client, "r1", queues=QUEUES[:4]):
        await asyncio.sleep(2)
        assert await promote(client, wanted) == []  # younger than ten minutes
        (alarm,) = await promote(client, wanted, stale_after=timedelta(0))
        assert await state(client) == (None, {"r1"})
        async with build(client, "r1", queues=QUEUES[4:]):
            runs = await promoted(client, wanted, lambda s: s[0] == "r1")

    assert "r1" in alarm and f"{DEPLOYMENT}.d3" in alarm
    assert runs[-1] == []
    assert f"{DEPLOYMENT}: r1 does not poll ['{DEPLOYMENT}.d3'] yet" in caplog.messages
    assert f"{DEPLOYMENT}: current none -> r1" in caplog.messages
    assert await promote(client, wanted, stale_after=timedelta(0)) == []  # current: no clock runs


async def test_changing_current_switches_new_workflows_and_changing_it_back_rolls_back(client):
    async with build(client, "r1"), build(client, "r2"):
        await promoted(client, values("r1", current="r1"), lambda s: s[0] == "r1")
        first = await client.start_workflow("held", id="first", task_queue=ORCHESTRATION)

        await promoted(client, values("r1", "r2", current="r2"), lambda s: s[0] == "r2")
        second = await client.start_workflow("held", id="second", task_queue=ORCHESTRATION)

        await promoted(client, values("r1", "r2", current="r1"), lambda s: s[0] == "r1")
        third = await client.start_workflow("held", id="third", task_queue=ORCHESTRATION)
        for handle in (first, second, third):
            await handle.signal(Held.release)
        ran_on = [await handle.result() for handle in (first, second, third)]

    assert ran_on == ["r1", "r2", "r1"]  # each stayed on the build it started on


async def test_a_tag_removed_under_an_open_workflow_raises_an_alarm_and_deletes_nothing(client):
    both, only_new = values("r1", "r2", current="r2"), values("r2", current="r2")
    async with build(client, "r2"):
        async with build(client, "r1"):
            await promoted(client, values("r1", current="r1"), lambda s: s[0] == "r1")
            open_on_r1 = await client.start_workflow("held", id="open", task_queue=ORCHESTRATION)
            await visible(client, 'TemporalWorkerDeploymentVersion="paper-pdf-7:r1"')
            await promoted(client, both, lambda s: s[0] == "r2")

            (alarm,) = await promote(client, only_new)
            assert await promote(client, both) == []  # control: listed, so its workflow is fine
            await open_on_r1.signal(Held.release)
            await open_on_r1.result()
        # r1's pods are gone and its tag is off the list: deleted once drained and forgotten.
        runs = await promoted(client, only_new, lambda s: s == ("r2", {"r2"}))

    assert "r1" in alarm and "1 open" in alarm
    assert runs[-1] == []


async def test_a_version_off_the_list_is_retired_once_no_workflow_is_open_on_its_queue(client):
    async with build(client, "r1"):
        await promoted(client, values("r1", current="r1"), lambda s: s[0] == "r1")
        held = await client.start_workflow("held", id="held", task_queue=ORCHESTRATION)
        await visible(client, f'TaskQueue="{ORCHESTRATION}"')

        (alarm,) = await promote(client, {})
        assert await state(client) == ("r1", {"r1"})  # still current: nothing was touched
        await held.signal(Held.release)
        await held.result()
        await promoted(client, {}, lambda s: s[0] is None)  # unversioned while its pods still poll
    runs = await promoted(client, {}, lambda s: s == (None, set()))

    assert DEPLOYMENT in alarm and "1 open" in alarm
    assert runs[-1] == []
    with pytest.raises(RPCError, match="no Worker Deployment found"):
        await client.workflow_service.describe_worker_deployment(
            DescribeWorkerDeploymentRequest(namespace=client.namespace, deployment_name=DEPLOYMENT)
        )


async def test_a_current_that_is_not_among_the_builds_raises_an_alarm_and_changes_nothing(client):
    async with build(client, "r1"), build(client, "r2"):
        await promoted(client, values("r1", current="r1"), lambda s: s == ("r1", {"r1", "r2"}))

        (alarm,) = await promote(client, values("r1", current="r2"))

        assert await state(client) == ("r1", {"r1", "r2"})
    assert "current" in alarm and "builds" in alarm


async def test_the_command_logs_json_lines_and_exits_1_on_an_alarm_or_a_failed_run(
    client, monkeypatch, capsys, root_logging
):
    async def connect():
        return client

    async def unreachable():
        raise RuntimeError("no Temporal at this address")

    monkeypatch.setattr(cli, "connect", connect)
    quiet = await cli.run_promoter({"profiles": values("r1", current="r1")})
    alarmed = await cli.run_promoter({"profiles": values("r1", current="r2")})
    monkeypatch.setattr(cli, "connect", unreachable)
    failed = await cli.run_promoter({"profiles": values("r1", current="r1")})

    lines = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    ours = [(line["level"], line["message"]) for line in lines if line["logger"] == cli.__name__]
    assert (quiet, alarmed, failed) == (0, 1, 1)
    assert ours[0] == ("INFO", "promoter ok")
    assert ours[1][0] == "ERROR" and "current is not among builds" in ours[1][1]
    assert ours[2] == ("ERROR", "promoter run failed: RuntimeError('no Temporal at this address')")
    assert lines[0]["message"] == f"{DEPLOYMENT}: no pod of it has polled yet"


async def visible(client: Client, query: str) -> None:
    """Wait until visibility, which lags, counts one running workflow for the query."""
    for _ in range(100):
        count = await client.count_workflows(f'{query} AND ExecutionStatus="Running"')
        if count.count == 1:
            return
        await asyncio.sleep(0.1)
    raise TimeoutError(query)
