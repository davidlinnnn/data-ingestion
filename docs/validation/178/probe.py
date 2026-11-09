"""Probes for task queues and Worker Deployments per Processing Profile version (#178;
Server 1.32.0, temporalio 1.34.0).

P1  A workflow started on a queue that no deployment polls yet (owner adopted before the
    rollout) runs once a versioned worker arrives and is made current; nothing is refused.
P2  An Activity on a queue owned by ANOTHER Worker Deployment (one deployment per queue, as the
    Worker Controller forces) runs on that deployment's current version while the workflow
    stays pinned to its own.
P3  After the Activity queue's deployment gets a new current build, a pinned-running workflow's
    next Activity runs on the NEW build (patch roll-out without touching the workflow).
P4  Control: a workflow started while current exists is pinned to it (reads versioningInfo).
P5  A version whose Processing Profile lost its adoption, with no workflow left, stays current
    and does not read draining, so the Controller never scales it down. Controls: the same
    reading shows draining and drained on a version that stopped being current.
P6  Deleting every version of a deployment, one version or a patched two, needs both
    preconditions, in either order: not current, and no pollers. Then the deployment itself can
    go. Replays the order of the Controller's finalizer (v1.14.0 handleDeletion).
P7  What that order does to a workflow still open on the version: --skip-drainage deletes the
    version anyway. Which is why retirement counts open workflows first.
"""

import asyncio
import json
import socket
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

from temporalio import activity, workflow
from temporalio.api.workflowservice.v1 import SetWorkerDeploymentCurrentVersionRequest
from temporalio.client import Client
from temporalio.common import VersioningBehavior, WorkerDeploymentVersion
from temporalio.worker import Worker, WorkerDeploymentConfig

PORT = 7322
ADDR = f"127.0.0.1:{PORT}"
ORCH, INF = "pp2.orchestration", "pp2.inference"
D_ORCH, D_INF = "pp2-orchestration", "pp2-inference"
D_PATCHED = "kp/paper-pdf-6-orchestration"
POLLER_TTL_S = 5  # the defaults are minutes; see README.md
FAST = [
    'matching.wv.VersionDrainageStatusRefreshInterval="2s"',
    'matching.wv.VersionDrainageStatusVisibilityGracePeriod="2s"',
    f'matching.PollerHistoryTTL="{POLLER_TTL_S}s"',
]


@workflow.defn
class Probe:
    @workflow.run
    async def run(self, rounds: int) -> list[str]:
        out = []
        for _ in range(rounds):
            out.append(await workflow.execute_activity(
                "which_build", task_queue=INF, start_to_close_timeout=timedelta(seconds=60)))
            if len(out) < rounds:
                await asyncio.sleep(3)  # a workflow timer; the patch of the Activity queue lands meanwhile
        return out


@workflow.defn
class Held:
    def __init__(self) -> None:
        self.released = False

    @workflow.signal
    def release(self) -> None:
        self.released = True

    @workflow.run
    async def run(self) -> str:
        await workflow.wait_condition(lambda: self.released)
        return "done"


def worker(client, queue, deployment, build, **kw):
    config = WorkerDeploymentConfig(
        WorkerDeploymentVersion(deployment, build), use_worker_versioning=True,
        default_versioning_behavior=VersioningBehavior.PINNED)
    return Worker(client, task_queue=queue, deployment_config=config, **kw)


def inf_worker(client, build):
    @activity.defn(name="which_build")
    async def which_build() -> str:
        return build
    return worker(client, INF, D_INF, build, activities=[which_build])


async def set_current(client, deployment, build):
    await client.workflow_service.set_worker_deployment_current_version(
        SetWorkerDeploymentCurrentVersionRequest(
            namespace=client.namespace, deployment_name=deployment, build_id=build))


async def versioning(client, wf_id):
    d = await client.get_workflow_handle(wf_id).describe()
    raw = d.raw_description.workflow_execution_info.versioning_info
    v = raw.deployment_version
    return {"behavior": VersioningBehavior(raw.behavior).name, "version": f"{v.deployment_name}:{v.build_id}" if v.build_id else None}


async def cli(*args):
    """The operating doc's commands, as the operator runs them: (exit code, output or error)."""
    r = await asyncio.to_thread(
        subprocess.run, ["temporal", "worker", "deployment", *args, "--address", ADDR, "-o", "json"],
        capture_output=True, text=True)
    return r.returncode, r.stdout if r.returncode == 0 else r.stderr.strip()


async def state(deployment):
    code, out = await cli("describe", "--name", deployment)
    if code:
        return {"exit": code, "error": out}
    d = json.loads(out)
    return {"current": d["routingConfig"]["currentVersionBuildID"],
            "versions": {v["BuildID"]: v["drainageStatus"] for v in d["versionSummaries"] or []}}


async def delete_version(deployment, build, *flags):
    code, out = await cli("delete-version", "--deployment-name", deployment, "--build-id", build, *flags)
    return {"exit": code, "error": out if code else None}


async def delete_deployment(deployment):
    code, out = await cli("delete", "--name", deployment)
    return {"exit": code, "error": out if code else None}


async def unversioned(deployment):
    code, out = await cli("set-current-version", "--deployment-name", deployment, "--unversioned", "--yes")
    assert code == 0, out


async def until(read, want):
    """The first reading that satisfies `want` and its wait in seconds; wait is None after 30 s."""
    t0 = time.monotonic()
    while True:
        value = await read()
        if want(value):
            return value, round(time.monotonic() - t0, 1)
        if time.monotonic() - t0 > 30:
            return value, None
        await asyncio.sleep(0.5)


async def count(query):
    """The operating doc's pre-check, as the operator runs it: open workflows matching `query`."""
    r = await asyncio.to_thread(
        subprocess.run, ["temporal", "workflow", "count", "--address", ADDR, "--query", f'{query} AND ExecutionStatus="Running"'],
        capture_output=True, text=True, check=True)
    return int(r.stdout.split("Total:")[1].split()[0])


async def task_queue(queue):
    r = await asyncio.to_thread(
        subprocess.run, ["temporal", "task-queue", "describe", "--address", ADDR, "--task-queue", queue, "-o", "json"],
        capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    return {"pollers": len(d["pollers"] or []),
            "workflow_backlog": sum(s["approximateBacklogCount"] for s in d["stats"] or [] if s["taskQueueType"] == "workflow")}


async def queues_of(deployment, build):
    """The operating doc's name check: the queues a version polls, or the refusal."""
    code, out = await cli("describe-version", "--deployment-name", deployment, "--build-id", build)
    return {"exit": code, "error": out} if code else [q["name"] for q in json.loads(out)["taskQueuesInfos"]]


async def p5_idle():
    """Runs inside the P1-P4 workers: orchestration r1 is current and every workflow has ended."""
    samples = []
    for _ in range(4):
        await asyncio.sleep(4)  # 16 s in all: eight drainage refreshes
        samples.append({"orch": await state(D_ORCH), "inf": await state(D_INF)})
    return {
        "samples": samples,
        "open_workflows": await count(f'TemporalWorkerDeploymentVersion="{D_ORCH}:r1"'),
        "queues": await queues_of(D_ORCH, "r1"),
        "queues_wrong_deployment": await queues_of(D_ORCH + "-typo", "r1"),
        "count_wrong_name": await count(f'TaskQueue="{ORCH}-typo"'),
        "task_queue_with_versioned_worker": await task_queue(ORCH),
    }


async def p5_control(client):
    dep, queue = D_PATCHED, "pp6.orchestration"
    async with worker(client, queue, dep, "r1", workflows=[Held]), worker(client, queue, dep, "r2", workflows=[Held]):
        await asyncio.sleep(1.5)
        await set_current(client, dep, "r1")
        h = await client.start_workflow(Held.run, id="p5-control", task_queue=queue)
        await asyncio.sleep(1)
        await set_current(client, dep, "r2")
        draining, wait_draining = await until(lambda: state(dep), lambda s: s["versions"]["r1"] == "draining")
        await h.signal(Held.release)
        await h.result()
        drained, wait_drained = await until(lambda: state(dep), lambda s: s["versions"]["r1"] == "drained")
    return {"draining": draining, "wait_draining_s": wait_draining, "drained": drained, "wait_drained_s": wait_drained}


async def p6_retire(client):
    # Named as the Controller names them: <k8s namespace>/<CR name>, <image tag>-<template hash>.
    dep, queue, build = "kp/paper-pdf-3-orchestration", "pp3.orchestration", "paper-pdf-3-r1-0a1b2c"
    steps = {}
    async with worker(client, queue, dep, build, workflows=[Held]):
        await asyncio.sleep(1.5)
        await set_current(client, dep, build)
        h = await client.start_workflow(Held.run, id="p6", task_queue=queue)
        await h.signal(Held.release)
        await h.result()
        steps["current_with_pollers"] = await delete_version(dep, build, "--skip-drainage")
        steps["delete_deployment_with_version"] = await delete_deployment(dep)
        await unversioned(dep)
        steps["state_after_unversioned"] = await state(dep)
        steps["not_current_with_pollers"] = await delete_version(dep, build, "--skip-drainage")
        steps["drained_if_waited"], steps["wait_drained_s"] = await until(
            lambda: state(dep), lambda s: s["versions"][build] == "drained")
    steps["just_after_workers_stop"] = await delete_version(dep, build, "--skip-drainage")
    deleted, wait = await until(lambda: delete_version(dep, build, "--skip-drainage"), lambda r: r["exit"] == 0)
    steps["not_current_no_pollers"], steps["wait_for_poller_ttl_s"] = deleted, wait
    steps["state_after_delete_version"] = await state(dep)
    steps["delete_empty_deployment"] = await delete_deployment(dep)
    steps["state_after_delete"] = await state(dep)

    # The other order: the workers leave first and the version is still current.
    dep2, queue2, build2 = "kp/paper-pdf-4-orchestration", "pp4.orchestration", "paper-pdf-4-r1-0a1b2c"
    async with worker(client, queue2, dep2, build2, workflows=[Held]):
        await asyncio.sleep(1.5)
        await set_current(client, dep2, build2)
    await asyncio.sleep(POLLER_TTL_S + 2)
    steps["current_no_pollers"] = await delete_version(dep2, build2, "--skip-drainage")
    await unversioned(dep2)
    steps["other_order_not_current_no_pollers"] = await delete_version(dep2, build2, "--skip-drainage")

    # After a patch, as p5_control left it: r1 superseded, r2 current, workers gone.
    await unversioned(D_PATCHED)
    await asyncio.sleep(POLLER_TTL_S + 2)
    steps["patched_before_delete"] = await state(D_PATCHED)
    steps["patched_r1"] = await delete_version(D_PATCHED, "r1", "--skip-drainage")
    steps["patched_r2"] = await delete_version(D_PATCHED, "r2", "--skip-drainage")
    steps["patched_deployment"] = await delete_deployment(D_PATCHED)
    steps["patched_after_delete"] = await state(D_PATCHED)
    return steps


async def p7_open_workflow(client):
    dep, queue, build = "kp/paper-pdf-5-orchestration", "pp5.orchestration", "paper-pdf-5-r1-0a1b2c"
    out = {}
    async with worker(client, queue, dep, build, workflows=[Held]):
        await asyncio.sleep(1.5)
        await set_current(client, dep, build)
        h = await client.start_workflow(Held.run, id="p7", task_queue=queue)
        await asyncio.sleep(1)
        out["versioning"] = await versioning(client, "p7")
        # Negative control of the required pre-check: both queries must see this one workflow.
        out["count_by_queue"], out["wait_count_s"] = await until(
            lambda: count(f'TaskQueue="{queue}"'), lambda c: c == 1)
        out["count_by_version"] = await count(f'TemporalWorkerDeploymentVersion="{dep}:{build}"')
        await unversioned(dep)
        out["draining"], _ = await until(lambda: state(dep), lambda s: s["versions"][build] == "draining")
    await asyncio.sleep(POLLER_TTL_S + 2)
    out["delete_without_skip"] = await delete_version(dep, build)
    out["delete_with_skip"] = await delete_version(dep, build, "--skip-drainage")
    out["delete_deployment"] = await delete_deployment(dep)
    out["status_after_delete"] = (await h.describe()).status.name
    await h.signal(Held.release)
    await asyncio.sleep(4)
    out["status_4s_after_signal_no_worker"] = (await h.describe()).status.name
    t0 = time.monotonic()
    async with worker(client, queue, dep, build, workflows=[Held]):
        try:
            out["result_when_build_returns"] = await asyncio.wait_for(h.result(), 20)
            out["wait_when_build_returns_s"] = round(time.monotonic() - t0, 1)
        except TimeoutError:
            out["result_when_build_returns"] = None
    return out


def refused(step, text):
    return step["exit"] != 0 and text in step["error"]


def pinned(reading, version):
    return reading == {"behavior": "PINNED", "version": version}


def within(wait, limit=30):
    return wait is not None and 0 <= wait <= limit


async def main() -> int:
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            raise SystemExit(f"port {PORT} is already in use")
    server = subprocess.Popen(["temporal", "server", "start-dev", "--headless", "--port", str(PORT),
                               "--ui-port", str(PORT + 1), "--log-level", "warn",
                               *[a for value in FAST for a in ("--dynamic-config-value", value)]],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        client = None
        for _ in range(60):
            try:
                client = await Client.connect(ADDR)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        assert client
        ev = {}

        # P1: start before any worker or deployment exists
        h1 = await client.start_workflow(Probe.run, 1, id="p1", task_queue=ORCH)
        await asyncio.sleep(2)
        d = await h1.describe()
        ev["p1_status_before_workers"] = d.status.name
        ev["p1_count_by_queue_before_workers"], _ = await until(
            lambda: count(f'TaskQueue="{ORCH}"'), lambda c: c == 1)
        ev["p1_count_by_version_before_workers"] = await count(f'TemporalWorkerDeploymentVersion="{D_ORCH}:r1"')
        ev["p1_task_queue_before_workers"], _ = await until(lambda: task_queue(ORCH), lambda q: q["workflow_backlog"] == 1)
        orch_r1 =worker(client, ORCH, D_ORCH, "r1", workflows=[Probe])
        inf_r1 = inf_worker(client, "r1")
        async with orch_r1, inf_r1:
            await asyncio.sleep(1.5)  # workers polled; versions exist
            await set_current(client, D_ORCH, "r1")
            await set_current(client, D_INF, "r1")
            t0 = time.monotonic()
            ev["p1_result"] = await asyncio.wait_for(h1.result(), 60)
            ev["p1_wait_s"] = round(time.monotonic() - t0, 1)
            ev["p1_versioning"] = await versioning(client, "p1")

            # P4 control: start while current exists
            h4 = await client.start_workflow(Probe.run, 1, id="p4", task_queue=ORCH)
            ev["p4_result"] = await asyncio.wait_for(h4.result(), 60)
            ev["p4_versioning"] = await versioning(client, "p4")

            # P2/P3: a workflow doing two activities; between them, inference gets build r2
            h2 = await client.start_workflow(Probe.run, 2, id="p2", task_queue=ORCH)
            await asyncio.sleep(1.0)  # first activity done on r1
            inf_r2 = inf_worker(client, "r2")
            async with inf_r2:
                await asyncio.sleep(1.5)
                await set_current(client, D_INF, "r2")
                ev["p2_p3_result"] = await asyncio.wait_for(h2.result(), 60)
                ev["p2_versioning"] = await versioning(client, "p2")
                # a fresh workflow now: orchestration still r1 (pinned), inference current r2
                h3 = await client.start_workflow(Probe.run, 1, id="p3", task_queue=ORCH)
                ev["p3_result"] = await asyncio.wait_for(h3.result(), 60)
                ev["p3_versioning"] = await versioning(client, "p3")
                ev["p5"] = await p5_idle()
        ev["p5_control"] = await p5_control(client)
        ev["p6"] = await p6_retire(client)
        ev["p7"] = await p7_open_workflow(client)

        p5, ctrl, p6, p7 = ev["p5"], ev["p5_control"], ev["p6"], ev["p7"]
        ev["pass"] = {
            "P1 runs once workers arrive, not refused": ev["p1_status_before_workers"] == "RUNNING" and ev["p1_result"] == ["r1"] and within(ev["p1_wait_s"]),
            "P1 pinned to the version once it ran": pinned(ev["p1_versioning"], f"{D_ORCH}:r1"),
            "P1 the queue count sees a workflow with no version yet": ev["p1_count_by_queue_before_workers"] == 1 and ev["p1_count_by_version_before_workers"] == 0,
            "P1 the waiting workflow shows as backlog": ev["p1_task_queue_before_workers"]["workflow_backlog"] == 1,
            "P2 activity ran on the other deployment": ev["p2_p3_result"][0] == "r1",
            "P3 next activity followed the new current": ev["p2_p3_result"][1] == "r2" and ev["p3_result"] == ["r2"],
            "P3 both workflows stayed pinned to orchestration r1": pinned(ev["p2_versioning"], f"{D_ORCH}:r1") and pinned(ev["p3_versioning"], f"{D_ORCH}:r1"),
            "P4 control pinned to orchestration r1": pinned(ev["p4_versioning"], f"{D_ORCH}:r1"),
            "P5 no open workflow on the idle version": p5["open_workflows"] == 0,
            "P5 the name check names the queue and refuses a wrong deployment; a wrong queue counts 0": p5["queues"] == [ORCH] and refused(p5["queues_wrong_deployment"], "not found") and p5["count_wrong_name"] == 0,
            "P5 task-queue describe lists no pollers of a versioned worker": p5["task_queue_with_versioned_worker"]["pollers"] == 0,
            "P5 idle version stays current, not draining": all(
                s["orch"]["current"] == "r1" and s["orch"]["versions"]["r1"] == "unspecified"
                and s["inf"]["current"] == "r2" and s["inf"]["versions"]["r2"] == "unspecified"
                for s in p5["samples"]),
            "P5 control: a superseded version with no pinned workflow reads drained": p5["samples"][-1]["inf"]["versions"]["r1"] == "drained",
            "P5 control: an open pinned workflow reads draining, then drained": within(ctrl["wait_draining_s"]) and within(ctrl["wait_drained_s"]),
            "P6 an idle version out of current reads drained if waited for": within(p6["wait_drained_s"]),
            "P6 current with pollers refused": refused(p6["current_with_pollers"], "current or ramping"),
            "P6 deployment with a version refused": refused(p6["delete_deployment_with_version"], "deployment has versions"),
            "P6 not current with pollers refused": refused(p6["not_current_with_pollers"], "active pollers"),
            "P6 refused just after the workers stop": refused(p6["just_after_workers_stop"], "active pollers"),
            "P6 not current, no pollers deletes": p6["not_current_no_pollers"]["exit"] == 0 and within(p6["wait_for_poller_ttl_s"], POLLER_TTL_S * 4),
            "P6 empty deployment deletes and is gone": p6["delete_empty_deployment"]["exit"] == 0 and refused(p6["state_after_delete"], "no Worker Deployment found"),
            "P6 current, no pollers refused": refused(p6["current_no_pollers"], "current or ramping"),
            "P6 other order deletes": p6["other_order_not_current_no_pollers"]["exit"] == 0,
            "P6 a patched deployment's two versions delete, then the deployment": set(p6["patched_before_delete"]["versions"]) == {"r1", "r2"} and p6["patched_r1"]["exit"] == 0 and p6["patched_r2"]["exit"] == 0 and p6["patched_deployment"]["exit"] == 0 and refused(p6["patched_after_delete"], "no Worker Deployment found"),
            "P7 pre-check sees the open workflow": p7["count_by_queue"] == 1 and p7["count_by_version"] == 1 and pinned(p7["versioning"], "kp/paper-pdf-5-orchestration:paper-pdf-5-r1-0a1b2c"),
            "P7 draining refused without --skip-drainage": refused(p7["delete_without_skip"], "draining"),
            "P7 --skip-drainage deletes under an open workflow": p7["delete_with_skip"]["exit"] == 0 and p7["delete_deployment"]["exit"] == 0,
            "P7 the workflow is left running, with no worker": p7["status_after_delete"] == "RUNNING" and p7["status_4s_after_signal_no_worker"] == "RUNNING",
            "P7 the same build returning finishes it": p7["result_when_build_returns"] == "done" and within(p7["wait_when_build_returns_s"]),
        }
        Path(__file__).with_name("evidence.json").write_text(json.dumps(ev, indent=2, default=str) + "\n")
        for name, ok in ev["pass"].items():
            print("PASS" if ok else "FAIL", name)
        return 0 if all(ev["pass"].values()) else 1
    finally:
        server.terminate()
        server.wait()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
