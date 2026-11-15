"""The promoter (#178): makes Temporal's Worker Deployments follow the deployment values. A
CronJob runs it every minute (#137); nothing on the Temporal side of an upgrade, a patch, a
rollback or a retirement is done by hand (profiles/README.md)."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from temporalio.api.deployment.v1 import WorkerDeploymentInfo, WorkerDeploymentVersion
from temporalio.api.workflowservice.v1 import (
    DeleteWorkerDeploymentRequest,
    DeleteWorkerDeploymentVersionRequest,
    DescribeWorkerDeploymentRequest,
    DescribeWorkerDeploymentVersionRequest,
    ListWorkerDeploymentsRequest,
    SetWorkerDeploymentCurrentVersionRequest,
)
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode

from kp_canonicalization.workflow import QUEUES, task_queue

log = logging.getLogger(__name__)


async def promote(
    client: Client, wanted: dict[str, Any], stale_after: timedelta = timedelta(minutes=10)
) -> list[str]:
    """One run over every Worker Deployment of the client's namespace, which must hold nothing
    but Processing Profile versions. `wanted` is the deployment values' `profiles` mapping:
    {deployment name: {"builds": [image tag, ...], "current": image tag}}. Returns the alarms,
    one line each; a run that returns any must end non-zero. It logs what it did or waits for.

    A listed deployment: `current` becomes the current version once Temporal lists all five
    queues for that build, which it does from each queue's first poll on; until then the run
    waits. A build that is off `builds` and not current is deleted once Temporal allows it
    (drained, pollers forgotten). Alarms: the wanted build is not current stale_after after
    Temporal first saw it; workflows are still open on a build that is off `builds`. A build no
    pod of which ever polled is unknown to Temporal and raises nothing here.

    An unlisted deployment is retired: when visibility counts no open workflow on its
    orchestration queue, it is set unversioned, then each version is deleted once Temporal
    allows it, then the deployment. Alarm: workflows are open, and then nothing is touched.

    An entry that is not a mapping whose `current` is among its `builds` is an alarm, and the
    run does nothing else. Drainage is never skipped. An RPC failure other than Temporal's
    refusal to delete raises.
    """
    alarms = [
        f"{name}: current is not among builds in {entry}"
        for name, entry in wanted.items()
        if not isinstance(entry, dict) or entry.get("current") not in (entry.get("builds") or [])
    ]
    if alarms:
        return alarms
    service, namespace = client.workflow_service, client.namespace
    names: list[str] = []
    token = b""
    while True:
        page = await service.list_worker_deployments(
            ListWorkerDeploymentsRequest(namespace=namespace, next_page_token=token)
        )
        names += [deployment.name for deployment in page.worker_deployments]
        token = page.next_page_token
        if not token:
            break
    # The list lags behind a routing change, so a listed deployment is described by its name.
    for name in sorted({*names, *wanted}):
        try:
            described = await service.describe_worker_deployment(
                DescribeWorkerDeploymentRequest(namespace=namespace, deployment_name=name)
            )
        except RPCError as missing:
            if missing.status != RPCStatusCode.NOT_FOUND:
                raise
            if name in wanted:  # otherwise the list still shows a deleted one
                log.info("%s: no pod of it has polled yet", name)
            continue
        info = described.worker_deployment_info
        if name in wanted:
            alarms += await _follow(client, info, wanted[name], stale_after)
        else:
            alarms += await _retire(client, info)
    return alarms


async def _follow(
    client: Client, info: WorkerDeploymentInfo, entry: dict[str, Any], stale_after: timedelta
) -> list[str]:
    name, want = info.name, entry["current"]
    versions = {v.deployment_version.build_id: v for v in info.version_summaries}
    current = info.routing_config.current_deployment_version.build_id
    alarms = []
    if current != want and want not in versions:
        log.info("%s: %s has not polled yet", name, want)
    elif current != want:
        described = await client.workflow_service.describe_worker_deployment_version(
            DescribeWorkerDeploymentVersionRequest(
                namespace=client.namespace,
                deployment_version=WorkerDeploymentVersion(deployment_name=name, build_id=want),
            )
        )
        polled = {queue.name for queue in described.worker_deployment_version_info.task_queue_infos}
        missing = sorted({task_queue(name, queue) for queue in QUEUES} - polled)
        if not missing:
            await _set_current(client, name, want)
            log.info("%s: current %s -> %s", name, current or "none", want)
            current = want
        else:
            age = datetime.now(UTC) - versions[want].create_time.ToDatetime(UTC)
            log.info("%s: %s does not poll %s yet", name, want, missing)
            if age >= stale_after:
                alarms.append(
                    f"{name}: {want} is not current {int(age.total_seconds())} s after its "
                    f"first poll; it does not poll {missing}"
                )
    for build_id in sorted(set(versions) - set(entry["builds"]) - {current}):
        version = f"{name}:{build_id}"
        pinned = f'TemporalWorkerDeploymentVersion="{version}" AND ExecutionStatus="Running"'
        open_workflows = (await client.count_workflows(pinned)).count
        if open_workflows:
            alarms.append(
                f"{version}: {open_workflows} open workflows are pinned to a build that is off "
                "the deployment values; put its tag back until it reads drained"
            )
        else:
            await _delete_version(client, name, build_id)
    return alarms


async def _retire(client: Client, info: WorkerDeploymentInfo) -> list[str]:
    name = info.name
    on_queue = f'TaskQueue="{task_queue(name)}" AND ExecutionStatus="Running"'
    open_workflows = (await client.count_workflows(on_queue)).count
    if open_workflows:
        return [
            f"{name}: off the deployment values with {open_workflows} open workflows on its "
            "orchestration queue; nothing was retired, put its entry back until they end"
        ]
    if info.routing_config.current_deployment_version.build_id:
        await _set_current(client, name, "")
        log.info("%s: retiring, set unversioned", name)
    remaining = [
        version.deployment_version.build_id
        for version in info.version_summaries
        if not await _delete_version(client, name, version.deployment_version.build_id)
    ]
    if not remaining:
        await client.workflow_service.delete_worker_deployment(
            DeleteWorkerDeploymentRequest(namespace=client.namespace, deployment_name=name)
        )
        log.info("%s: retired, Worker Deployment deleted", name)
    return []


async def _set_current(client: Client, name: str, build_id: str) -> None:
    """An empty build_id sets the deployment unversioned."""
    await client.workflow_service.set_worker_deployment_current_version(
        SetWorkerDeploymentCurrentVersionRequest(
            namespace=client.namespace, deployment_name=name, build_id=build_id
        )
    )


async def _delete_version(client: Client, name: str, build_id: str) -> bool:
    """False while Temporal refuses: the version is draining, or its pollers are remembered."""
    try:
        await client.workflow_service.delete_worker_deployment_version(
            DeleteWorkerDeploymentVersionRequest(
                namespace=client.namespace,
                deployment_version=WorkerDeploymentVersion(deployment_name=name, build_id=build_id),
            )
        )
    except RPCError as refusal:
        if refusal.status != RPCStatusCode.FAILED_PRECONDITION:
            raise
        log.info("%s:%s: not deleted yet: %s", name, build_id, refusal.message)
        return False
    log.info("%s:%s: version deleted", name, build_id)
    return True
