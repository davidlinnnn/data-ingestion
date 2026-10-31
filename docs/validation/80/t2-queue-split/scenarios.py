"""Seam B for the orchestration/inference split: scenarios S1-S5 of README.md.

    .venv/bin/python docs/validation/80/t2-queue-split/scenarios.py CORPUS_MANIFEST

Same stack as ../t2-tracer-bullet/run.py (whose helpers it reuses): its own Temporal dev
server, here with one read and one write partition per task queue, fake_admission, the
RustFS S3 stand-in on port 9100, and every worker a `kp-processing worker --queue ...`
process. Each scenario runs in a fresh bucket so nothing is reused. Writes evidence.json
next to this file; raw samples go to the log directory.
"""

import asyncio
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import timezone
from pathlib import Path

from temporalio.api.enums.v1 import PendingActivityState, TaskQueueType
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
from temporalio.client import Client

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "t2-tracer-bullet"))
import run as seamb  # noqa: E402

from kp_processing.cli import start_request  # noqa: E402

INFERENCE = {"parse_group", "assemble"}
PAPERS = [1, 2, 3, 4]  # corpus indices, 22-28 pages each


class Stack:
    def __init__(self, client: Client, papers: dict[int, bytes]) -> None:
        self.client = client
        self.papers = papers
        self.procs: list[subprocess.Popen] = []

    async def bucket(self, name: str) -> str:
        bucket = f"queues-{seamb.RUN}-{name}"
        s = seamb.store(bucket)  # also points this process's environment at the bucket
        for data in self.papers.values():
            await s.put_if_absent(f"custody/{hashlib.sha256(data).hexdigest()}", data)
        return bucket

    async def worker(self, bucket: str, name: str, queue: str, *extra: str) -> subprocess.Popen:
        log = seamb.LOGS / f"worker-{name}-{queue}.log"
        proc = subprocess.Popen(
            [*seamb.CLI, "worker", "--queue", queue, "--profile", seamb.PROFILE,
             "--build-id", "queues-r1", *extra],
            env=seamb.env(bucket), stdout=open(log, "w"), stderr=subprocess.STDOUT,
            cwd=seamb.REPO,
        )  # fmt: skip
        self.procs.append(proc)
        while "worker paper-pdf@1" not in log.read_text():
            assert proc.poll() is None, f"{name} {queue} worker exited: {log.read_text()}"
            await asyncio.sleep(0.2)
        return proc

    def stop_workers(self) -> None:
        for proc in self.procs:
            if proc.poll() is None:
                proc.send_signal(signal.SIGKILL)
            proc.wait()
        self.procs.clear()

    async def start(self, bucket: str, index: int, rid: str, priority: str = "normal") -> str:
        data = self.papers[index]
        sha = hashlib.sha256(data).hexdigest()
        start = seamb.start_input(sha, data, bucket, rid, priority=priority)
        assert await start_request(start, wait=False) == 0
        return rid

    async def finish(self, rids: list[str]) -> dict[str, dict]:
        return {rid: await self.client.get_workflow_handle(rid).result() for rid in rids}


def identity(proc: subprocess.Popen) -> str:
    return f"{proc.pid}@{socket.gethostname()}"  # the SDK's default worker identity


async def backlog(client: Client) -> dict:
    response = await client.workflow_service.describe_task_queue(
        DescribeTaskQueueRequest(
            namespace="default",
            task_queue=TaskQueue(name="inference"),
            task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_ACTIVITY,
            report_stats=True,
        )
    )
    return {
        "total": response.stats.approximate_backlog_count,
        "by_priority": {k: v.approximate_backlog_count for k, v in response.stats_by_priority_key.items()},
    }  # fmt: skip


async def sampler(client: Client, rids: list[str], out: list[dict], stop: asyncio.Event) -> None:
    """Every 0.25 s: each running workflow's pending inference Activities and the backlog."""
    while not stop.is_set():
        acts = []
        for rid in list(rids):
            described = await client.get_workflow_handle(rid).describe()
            for pa in described.raw_description.pending_activities:
                if pa.activity_type.name in INFERENCE:
                    acts.append({
                        "rid": rid, "id": pa.activity_id, "type": pa.activity_type.name,
                        "state": PendingActivityState.Name(pa.state).removeprefix("PENDING_ACTIVITY_STATE_"),
                        "worker": pa.last_worker_identity, "attempt": pa.attempt,
                    })  # fmt: skip
        out.append({"t": time.time(), "acts": acts, "backlog": await backlog(client)})
        await asyncio.sleep(0.25)


async def runs(client: Client, rid: str) -> list[dict]:
    """Every inference Activity of a workflow from its history: final attempt's times and worker."""
    history = await client.get_workflow_handle(rid).fetch_history()
    by_id: dict[int, dict] = {}
    for e in history.events:
        t = e.event_time.ToDatetime(timezone.utc).timestamp()
        if e.HasField("activity_task_scheduled_event_attributes"):
            a = e.activity_task_scheduled_event_attributes
            by_id[e.event_id] = {"rid": rid, "id": a.activity_id, "type": a.activity_type.name,
                                 "scheduled": t}  # fmt: skip
        elif e.HasField("activity_task_started_event_attributes"):
            a = e.activity_task_started_event_attributes
            by_id[a.scheduled_event_id] |= {"started": t, "attempt": a.attempt, "worker": a.identity}
        elif e.HasField("activity_task_completed_event_attributes"):
            by_id[e.activity_task_completed_event_attributes.scheduled_event_id]["completed"] = t
    return [r for r in by_id.values() if r["type"] in INFERENCE]


async def all_runs(client: Client, rids: list[str]) -> list[dict]:
    return [r for rid in rids for r in await runs(client, rid)]


def started_counts(samples: list[dict]) -> list[dict[str, int]]:
    """Per sample: started inference Activities per worker identity."""
    counts = []
    for s in samples:
        c: dict[str, int] = {}
        for a in s["acts"]:
            if a["state"] == "STARTED":
                c[a["worker"]] = c.get(a["worker"], 0) + 1
        counts.append(c)
    return counts


async def sampled(stack: Stack, rids: list[str], samples: list[dict]):
    stop = asyncio.Event()
    task = asyncio.create_task(sampler(stack.client, rids, samples, stop))
    outcomes = await stack.finish(rids)
    stop.set()
    await task
    return outcomes


async def s1_s4(stack: Stack) -> dict:
    bucket = await stack.bucket("s1")
    await stack.worker(bucket, "s1", "orchestration")
    await stack.worker(bucket, "s1", "inference")
    rids = [await stack.start(bucket, i, f"req_{seamb.RUN}_s1_{i}") for i in PAPERS[:3]]
    samples: list[dict] = []
    outcomes = await sampled(stack, rids, samples)
    stack.stop_workers()
    counts = started_counts(samples)
    waiting_while_running = sum(
        1 for s, c in zip(samples, counts, strict=True)
        if sum(c.values()) == 1 and any(a["state"] == "SCHEDULED" for a in s["acts"])
    )  # fmt: skip
    prepare_s = {}
    for rid in rids:
        history = await stack.client.get_workflow_handle(rid).fetch_history()
        first = history.events[0].event_time.ToDatetime(timezone.utc).timestamp()
        names, done = {}, None
        for e in history.events:
            if e.HasField("activity_task_scheduled_event_attributes"):
                names[e.event_id] = e.activity_task_scheduled_event_attributes.activity_type.name
            elif e.HasField("activity_task_completed_event_attributes"):
                if names[e.activity_task_completed_event_attributes.scheduled_event_id] == "prepare":
                    done = e.event_time.ToDatetime(timezone.utc).timestamp()
                    break
        prepare_s[rid] = round(done - first, 2)
    (seamb.LOGS / "s1-samples.json").write_text(json.dumps(samples))
    result = {
        "samples": len(samples),
        "max_started": max(sum(c.values()) for c in counts),
        "samples_with_one_running_and_one_waiting": waiting_while_running,
        "max_backlog": max(s["backlog"]["total"] for s in samples),
        "outcomes": sorted({o["outcome"] for o in outcomes.values()}),
        "prepare_seconds_after_start": prepare_s,
    }
    result["S1"] = {
        "a_at_most_one_started": result["max_started"] <= 1,
        "b_waits_in_temporal": waiting_while_running > 0,
        "c_backlog_visible": result["max_backlog"] > 0,
        "d_all_complete": result["outcomes"] == ["complete"],
    }
    result["S4"] = {"prepare_within_5s": all(v <= 5 for v in prepare_s.values())}
    return result


async def s2(stack: Stack) -> dict:
    bucket = await stack.bucket("s2")
    await stack.worker(bucket, "s2", "orchestration")
    inference = [await stack.worker(bucket, f"s2-{n}", "inference") for n in (1, 2)]
    rids = [await stack.start(bucket, i, f"req_{seamb.RUN}_s2_{i}") for i in PAPERS]
    samples: list[dict] = []
    outcomes = await sampled(stack, rids, samples)
    stack.stop_workers()
    counts = started_counts(samples)
    done = await all_runs(stack.client, rids)
    per_worker = {
        f"inference-{n}": sum(r["worker"] == identity(p) for r in done)
        for n, p in enumerate(inference, 1)
    }
    return {
        "max_started_per_worker": max((max(c.values(), default=0) for c in counts), default=0),
        "max_started_total": max(sum(c.values()) for c in counts),
        "inference_runs_per_worker": per_worker,
        "outcomes": sorted({o["outcome"] for o in outcomes.values()}),
        "S2": {
            "a_one_per_worker_two_total": max(max(c.values(), default=0) for c in counts) <= 1
            and max(sum(c.values()) for c in counts) <= 2,
            "b_both_workers_ran": all(n > 0 for n in per_worker.values()),
            "c_all_complete": {o["outcome"] for o in outcomes.values()} == {"complete"},
        },
    }


async def s3(stack: Stack) -> dict:
    bucket = await stack.bucket("s3")
    await stack.worker(bucket, "s3", "orchestration")
    await stack.worker(bucket, "s3", "inference")
    bulk = [await stack.start(bucket, i, f"req_{seamb.RUN}_s3_bulk_{i}", "low") for i in PAPERS[:3]]
    while not any(r.get("started") for r in await all_runs(stack.client, bulk)):
        await asyncio.sleep(0.2)
    normal = await stack.start(bucket, PAPERS[3], f"req_{seamb.RUN}_s3_normal")
    outcomes = await stack.finish([*bulk, normal])
    stack.stop_workers()
    n_runs = await runs(stack.client, normal)
    b_runs = await all_runs(stack.client, bulk)
    overtaken = [
        {"bulk": b["id"], "bulk_rid": b["rid"], "normal": n["id"]}
        for b in b_runs for n in n_runs
        if n["scheduled"] < b["started"] - 0.1 and n["started"] > b["started"]
    ]  # fmt: skip
    longest_bulk = max(b["completed"] - b["started"] for b in b_runs)
    waits = [round(n["started"] - n["scheduled"], 2) for n in n_runs]
    normal_done = max(n["completed"] for n in n_runs)
    last_bulk_done = max(b["completed"] for b in b_runs)
    return {
        "bulk_started_while_normal_waited": overtaken,
        "normal_waits_s": waits,
        "longest_bulk_inference_s": round(longest_bulk, 2),
        "normal_done_before_last_bulk_s": round(last_bulk_done - normal_done, 2),
        "outcomes": sorted({o["outcome"] for o in outcomes.values()}),
        "S3": {
            "a_no_bulk_overtakes_waiting_normal": not overtaken,
            "b_normal_before_last_bulk": normal_done < last_bulk_done,
            "c_wait_within_one_bulk_group": max(waits) <= longest_bulk + 2,
        },
    }


async def s5(stack: Stack, name: str, grace: str, reference: dict) -> dict:
    bucket = await stack.bucket(name)
    await stack.worker(bucket, name, "orchestration")
    inference = [
        await stack.worker(bucket, f"{name}-{n}", "inference", "--shutdown-grace-s", grace)
        for n in (1, 2)
    ]
    rid = await stack.start(bucket, PAPERS[0], f"req_{seamb.RUN}_{name}")
    # SIGTERM whichever worker runs the second group, as a scale-down would.
    while True:
        running = [
            a for a in (await stack.client.get_workflow_handle(rid).describe())
            .raw_description.pending_activities
            if a.activity_type.name == "parse_group" and a.activity_id != "1"
            and a.state == PendingActivityState.PENDING_ACTIVITY_STATE_STARTED
        ]  # fmt: skip
        if running:
            break
        await asyncio.sleep(0.05)
    leaving = next(p for p in inference if identity(p) == running[0].last_worker_identity)
    staying = next(p for p in inference if p is not leaving)
    activity_id = running[0].activity_id
    sigterm = time.time()
    leaving.send_signal(signal.SIGTERM)
    leaving.wait()
    exited = time.time()
    outcome = await stack.client.get_workflow_handle(rid).result()
    stack.stop_workers()
    done = await runs(stack.client, rid)
    target = next(r for r in done if r["id"] == activity_id)
    after = [r for r in done if r["worker"] == identity(leaving) and r["started"] > sigterm]
    result_json = json.loads(await seamb.store(bucket).get(f"requests/{rid}/result.json"))
    return {
        "activity": activity_id,
        "attempt_that_completed": target["attempt"],
        "completed_on": "leaving" if target["worker"] == identity(leaving)
        else "staying" if target["worker"] == identity(staying) else target["worker"],
        "exit_after_sigterm_s": round(exited - sigterm, 2),
        "exit_after_its_group_done_s": round(exited - target["completed"], 2)
        if target["worker"] == identity(leaving) else None,
        "retry_started_after_sigterm_s": round(target["started"] - sigterm, 2),
        "started_by_leaving_after_sigterm": len(after),
        "outcome": outcome["outcome"],
        "native_equals_uninterrupted": result_json["native"] == reference["native"],
    }  # fmt: skip


async def main(manifest: Path) -> int:
    seamb.LOGS.mkdir(parents=True)
    corpus = {p["index"]: p for p in json.loads(manifest.read_text())["papers"]}
    papers = {}
    for i in PAPERS:
        data = (manifest.parent / corpus[i]["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == corpus[i]["sha256"]
        papers[i] = data
    temporal = subprocess.Popen(
        ["temporal", "server", "start-dev", "--headless", "--port", "7244", "--ui-port", "7245",
         "--db-filename", str(seamb.LOGS / "temporal.db"), "--log-level", "warn",
         "--dynamic-config-value", "matching.numTaskqueueReadPartitions=1",
         "--dynamic-config-value", "matching.numTaskqueueWritePartitions=1"],
        stdout=open(seamb.LOGS / "temporal.log", "w"), stderr=subprocess.STDOUT,
    )  # fmt: skip
    admission = subprocess.Popen(
        [str(seamb.REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server", "--port",
         "8091", "--log", str(seamb.LOGS / "reports.jsonl")], cwd=seamb.REPO,
    )  # fmt: skip
    os.environ.update(seamb.BASE_ENV)
    evidence: dict = {"run": seamb.RUN, "papers": {i: {k: corpus[i][k] for k in ("file", "sha256", "pages")} for i in PAPERS}}  # fmt: skip
    stack = None
    try:
        for _ in range(60):
            try:
                client = await Client.connect(seamb.TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        evidence["temporal"] = subprocess.run(
            ["temporal", "--version"], capture_output=True, text=True
        ).stdout.strip()
        stack = Stack(client, papers)
        evidence["S1_S4"] = await s1_s4(stack)
        reference = json.loads(
            await seamb.store(f"queues-{seamb.RUN}-s1").get(
                f"requests/req_{seamb.RUN}_s1_{PAPERS[0]}/result.json"
            )
        )
        evidence["S2"] = await s2(stack)
        evidence["S3"] = await s3(stack)
        evidence["S5a"] = await s5(stack, "s5a", "120", reference)
        evidence["S5b"] = await s5(stack, "s5b", "0", reference)
        a, b = evidence["S5a"], evidence["S5b"]
        a["S5a"] = {
            "group_completed_on_attempt_1_by_leaving": a["attempt_that_completed"] == 1
            and a["completed_on"] == "leaving",
            "no_new_work_after_sigterm": a["started_by_leaving_after_sigterm"] == 0,
            "exits_once_group_done": a["exit_after_its_group_done_s"] is not None
            and 0 <= a["exit_after_its_group_done_s"] <= 3,
            "paper_completes": a["outcome"] == "complete",
        }
        b["S5b"] = {
            "exits_within_5s": b["exit_after_sigterm_s"] <= 5,
            "retried_on_other_worker_within_10s": b["completed_on"] == "staying"
            and b["retry_started_after_sigterm_s"] <= 10,
            "paper_completes_and_equals_uninterrupted": b["outcome"] == "complete"
            and b["native_equals_uninterrupted"],
        }
    finally:
        if stack:
            stack.stop_workers()
        admission.terminate()
        temporal.terminate()
    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    verdicts = {
        f"{scenario}.{criterion}": passed
        for section in evidence.values() if isinstance(section, dict)
        for scenario, checks in section.items() if str(scenario).startswith("S") and isinstance(checks, dict)
        for criterion, passed in checks.items()
    }  # fmt: skip
    print(json.dumps(verdicts, indent=2))
    print(f"logs in {seamb.LOGS}")
    return 0 if all(verdicts.values()) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]))))
