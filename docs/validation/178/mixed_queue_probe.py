"""P8 for #178, revised design of 2026-11-10: one Worker Deployment per Processing Profile
version, its queue serving workflows AND Activities, switched r1 -> r2 with the CLI the way the
promoter CronJob will (Server 1.32.0, temporalio 1.34.0).

temporalio/temporal#11842 reports routingConfigUpdateState stuck IN_PROGRESS forever on a queue of
that shape, wedging every rollout. Our orchestration queue is that shape: worker.py registers the
workflow and the Orchestration activities on it. P8 reads the state the report names, over gRPC,
because the CLI's JSON does not print it.
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
from temporalio.api.workflowservice.v1 import DescribeWorkerDeploymentRequest
from temporalio.client import Client
from temporalio.common import VersioningBehavior, WorkerDeploymentVersion
from temporalio.worker import Worker, WorkerDeploymentConfig

PORT = 7323
ADDR = f"127.0.0.1:{PORT}"
QUEUE = "pp3.orchestration"
DEPLOYMENT = "pp3"
COMPLETED = 2  # ROUTING_CONFIG_UPDATE_STATE_COMPLETED; IN_PROGRESS is 1
FAST = [
    'matching.wv.VersionDrainageStatusRefreshInterval="2s"',
    'matching.wv.VersionDrainageStatusVisibilityGracePeriod="2s"',
    'matching.PollerHistoryTTL="5s"',
]


@workflow.defn(versioning_behavior=VersioningBehavior.PINNED)
class Mixed:
    @workflow.run
    async def run(self) -> str:
        # No task_queue: the Activity runs on the workflow's own queue, as Orchestration's do.
        return await workflow.execute_activity(
            "which_build", start_to_close_timeout=timedelta(seconds=60))


def which_build_on(build):
    @activity.defn(name="which_build")
    async def which_build() -> str:
        return build
    return which_build


def worker(client, build):
    config = WorkerDeploymentConfig(
        WorkerDeploymentVersion(DEPLOYMENT, build), use_worker_versioning=True,
        default_versioning_behavior=VersioningBehavior.PINNED)
    return Worker(client, task_queue=QUEUE, workflows=[Mixed], activities=[which_build_on(build)],
                  deployment_config=config)


async def cli(*args):
    r = await asyncio.to_thread(
        subprocess.run, ["temporal", "worker", "deployment", *args, "--address", ADDR, "-o", "json"],
        capture_output=True, text=True)
    return r.returncode, r.stdout if r.returncode == 0 else r.stderr.strip()


async def set_current(build):
    """The promoter's call, retried: a version exists only once its worker has polled."""
    t0 = time.monotonic()
    first_error = None
    for _ in range(60):
        code, out = await cli("set-current-version", "--deployment-name", DEPLOYMENT, "--build-id", build, "--yes")
        if code == 0:
            return {"ok": True, "wait_s": round(time.monotonic() - t0, 1), "first_error": first_error}
        first_error = first_error or out
        await asyncio.sleep(0.5)
    return {"ok": False, "wait_s": None, "first_error": first_error}


async def drainage():
    code, out = await cli("describe", "--name", DEPLOYMENT)
    summaries = (json.loads(out) if code == 0 else {}).get("versionSummaries") or []
    return {v["BuildID"]: v.get("drainageStatus") for v in summaries}


async def describe(client):
    resp = await client.workflow_service.describe_worker_deployment(
        DescribeWorkerDeploymentRequest(namespace="default", deployment_name=DEPLOYMENT))
    info = resp.worker_deployment_info
    rc = info.routing_config
    return {"current": rc.current_deployment_version.build_id if rc.HasField("current_deployment_version") else None,
            "routing_config_update_state": info.routing_config_update_state,
            "versions": await drainage()}


async def run_one(client, wid):
    t0 = time.monotonic()
    out = await client.execute_workflow(Mixed.run, id=wid, task_queue=QUEUE,
                                        execution_timeout=timedelta(seconds=60))
    return {"ran_on": out, "wait_s": round(time.monotonic() - t0, 1)}


async def until(read, want, limit=30):
    """Seconds until `read()` returns `want`; None past the limit."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit:
        if await read() == want:
            return round(time.monotonic() - t0, 1)
        await asyncio.sleep(0.2)
    return None


def within(wait, limit=30):
    return wait is not None and 0 <= wait <= limit


async def main() -> int:
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", PORT)) == 0:
            raise SystemExit(f"port {PORT} is already in use")
    server = subprocess.Popen(["temporal", "server", "start-dev", "--headless", "--port", str(PORT),
                               "--ui-port", str(PORT + 1), "--log-level", "error",
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
        async with worker(client, "r1"):
            ev["r1_set_current"] = await set_current("r1")
            ev["w1"] = await run_one(client, "w1")  # control: before the switch
            async with worker(client, "r2"):
                ev["r2_set_current"] = await set_current("r2")
                ev["after_switch"] = await describe(client)
                ev["w2"] = await run_one(client, "w2")
                ev["r1_wait_drained_s"] = await until(lambda: drainage(), {"r1": "drained", "r2": "unspecified"})
                ev["after_drain"] = await describe(client)
                ev["w3"] = await run_one(client, "w3")
        switch, drain = ev["after_switch"], ev["after_drain"]
        ev["pass"] = {
            "P8 control: before the switch a workflow ran on r1": ev["w1"]["ran_on"] == "r1" and within(ev["w1"]["wait_s"]),
            "P8 both switches succeeded within the limit": ev["r1_set_current"]["ok"] and ev["r2_set_current"]["ok"] and within(ev["r2_set_current"]["wait_s"]),
            "P8 current is r2 and the routing state reads COMPLETED, not IN_PROGRESS": switch["current"] == "r2" and switch["routing_config_update_state"] == COMPLETED,
            "P8 new workflows ran on r2": ev["w2"]["ran_on"] == "r2" and ev["w3"]["ran_on"] == "r2" and within(ev["w2"]["wait_s"]) and within(ev["w3"]["wait_s"]),
            "P8 r1 read draining at the switch, then drained; r2 unspecified": switch["versions"] == {"r1": "draining", "r2": "unspecified"} and within(ev["r1_wait_drained_s"]) and drain["versions"] == {"r1": "drained", "r2": "unspecified"},
            "P8 the routing state stays COMPLETED after drainage": drain["current"] == "r2" and drain["routing_config_update_state"] == COMPLETED,
        }
        Path(__file__).with_name("mixed_queue_evidence.json").write_text(json.dumps(ev, indent=2, default=str) + "\n")
        for name, ok in ev["pass"].items():
            print("PASS" if ok else "FAIL", name)
        return 0 if all(ev["pass"].values()) else 1
    finally:
        server.terminate()
        server.wait()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
