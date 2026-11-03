"""Capacity and freshness for #136: V2 (one paper in a 4 CPU / 5 GiB linux/arm64 inference
container, with a worker kill) and V8 (five normal papers and one low at once on one
orchestration worker and three inference containers).

    env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t7-capacity/run.py v2 CORPUS_MANIFEST INDEX
    env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t7-capacity/run.py kill CORPUS_MANIFEST INDEX
    env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t7-capacity/run.py v8 CORPUS_MANIFEST N1,N2,N3,N4,N5 LOW

Needs the image `kp-processing:t7` (Dockerfile here), the S3 stand-in on port 9100, the
`temporal` CLI and the weights under ~/models/docling. The stack is t5's on ports of its own
(Temporal 7284, fake_admission 8121, VLM stand-in 8122, summary stand-in 8123, metrics
9480-9491); it refuses to start when any is taken. Temporal runs with one task-queue
partition, so priority holds (#129), and registers the correlation search attributes. The
orchestration, vlm and summary workers run on the host; each inference worker runs in its own
container limited to 4 CPU and 5 GiB, whose cgroup memory is sampled every second.

Writes v2-INDEX.json, kill-INDEX.json or v8.json next to this file: timings, counts, memory and
metric samples only; the papers are third-party.
"""

import asyncio
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import UTC
from pathlib import Path

from temporalio.client import Client

HERE = Path(__file__).resolve().parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


t5 = load("t5", HERE.parent / "t5-seam-b/run.py")
t4, t2 = t5.t4, t5.t2
from kp_processing.profile import PROFILES_DIR, load_profile  # noqa: E402
from kp_processing.stages import enrichment_key, item_prefix  # noqa: E402
from kp_processing.workflow import STAGE_DURATION  # noqa: E402

TEMPORAL_PORT, ADMISSION_PORT, VLM_PORT, SUMMARY_PORT = 7284, 8121, 8122, 8123
METRICS = {"orchestration": 9480, "vlm": 9482, "summary": 9484}  # +1: the Temporal runtime's
INFERENCE_METRICS = 9486  # inference container i: 9486 + 2i and 9487 + 2i
t2.TEMPORAL, t2.ADMISSION = f"127.0.0.1:{TEMPORAL_PORT}", f"http://127.0.0.1:{ADMISSION_PORT}"
t2.BASE_ENV.update(TEMPORAL_ADDRESS=t2.TEMPORAL, KP_ADMISSION_URL=t2.ADMISSION)
IMAGE = "kp-processing:t7"
MODELS = Path.home() / "models/docling"
CPUS, MEMORY_GIB = 4, 5
GUARD_GIB = load_profile(PROFILES_DIR / "paper-pdf@1.yaml").runtime["memory_guard_gib"]
GIB = 1 << 30
MATCHING_GRACE_S = 1.0


class CountingStandIn(t4.StandIn):
    """t4's VLM stand-in (the canned answer after 3 s), counting requests in flight."""

    lock = threading.Lock()
    in_flight = 0
    peak = 0
    total = 0

    def do_POST(self) -> None:
        cls = CountingStandIn
        with cls.lock:
            cls.in_flight += 1
            cls.total += 1
            cls.peak = max(cls.peak, cls.in_flight)
        try:
            super().do_POST()
        finally:
            with cls.lock:
                cls.in_flight -= 1


class Container:
    """One inference worker in a container limited to CPUS and MEMORY_GIB, its cgroup memory
    sampled every second while it runs."""

    def __init__(self, name: str, bucket: str, slot: int) -> None:
        self.name, self.samples, self.peaks = name, [], []
        env = {k: v for k, v in t2.env(bucket).items() if k.startswith(("KP_S3_", "AWS_"))}
        env.update(KP_S3_ENDPOINT="http://host.docker.internal:9100",
                   TEMPORAL_ADDRESS=f"host.docker.internal:{TEMPORAL_PORT}")  # fmt: skip
        port = INFERENCE_METRICS + 2 * slot
        self.metrics = (port, port + 1)
        subprocess.run(
            ["docker", "run", "-d", "--name", name, "--platform", "linux/arm64",
             "--cpus", str(CPUS), "--memory", f"{MEMORY_GIB}g", "--memory-swap", f"{MEMORY_GIB}g",
             "-v", f"{MODELS}:/models:ro",
             "-p", f"127.0.0.1:{port}:9480", "-p", f"127.0.0.1:{port + 1}:9481",
             *[a for k, v in env.items() for a in ("-e", f"{k}={v}")],
             IMAGE, "worker", "--queue", "inference", "--profile", "tests/profiles/paper-pdf-dev.yaml",
             "--build-id", "seamb-r1", "--metrics-port", "9480", "--temporal-metrics-port", "9481"],
            check=True, capture_output=True,
        )  # fmt: skip
        self.limits = {
            "cpu.max": self.read("cpu.max"),
            "memory.max": self.read("memory.max"),
            "memory.swap.max": self.read("memory.swap.max"),
        }
        self.wait_ready()
        self.sample()

    def read(self, name: str) -> str:
        return subprocess.run(["docker", "exec", self.name, "cat", f"/sys/fs/cgroup/{name}"],
                              capture_output=True, text=True, check=True).stdout.strip()  # fmt: skip

    def wait_ready(self) -> None:
        for _ in range(240):
            logs = subprocess.run(["docker", "logs", self.name], capture_output=True, text=True)
            if "on inference" in logs.stdout + logs.stderr:
                return
            time.sleep(0.5)
        raise RuntimeError(f"{self.name} did not start:\n{logs.stdout}{logs.stderr}")

    def sample(self) -> None:
        script = ("while :; do echo $(date +%s.%N) $(cat /sys/fs/cgroup/memory.current) "
                  "$(awk '/^anon /{print $2}' /sys/fs/cgroup/memory.stat); sleep 1; done")  # fmt: skip
        sampler = subprocess.Popen(["docker", "exec", self.name, "sh", "-c", script],
                                   stdout=subprocess.PIPE, text=True)  # fmt: skip

        def read() -> None:
            for line in sampler.stdout or []:
                at, current, anon = line.split()
                self.samples.append((float(at), int(current), int(anon)))

        threading.Thread(target=read, daemon=True).start()

    def kill(self) -> None:
        self.peaks.append(self.peak())
        subprocess.run(["docker", "kill", self.name], check=True, capture_output=True)

    def restart(self) -> None:
        subprocess.run(["docker", "start", self.name], check=True, capture_output=True)
        self.wait_ready()
        self.sample()

    def peak(self) -> dict:
        return {"memory.peak": int(self.read("memory.peak")),
                "oom_kill": int(re.search(r"oom_kill (\d+)", self.read("memory.events"))[1])}  # fmt: skip

    def remove(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)

    def memory(self, since: float, until: float) -> dict:
        window = [s for s in self.samples if since <= s[0] <= until]
        current = [s[1] for s in window]
        anon = [s[2] for s in window]
        return {
            "limits": self.limits,
            "samples": len(window),
            "current_max_gib": round(max(current) / GIB, 3) if current else None,
            "anon_max_gib": round(max(anon) / GIB, 3) if anon else None,
            "samples_over_guard": sum(c > GUARD_GIB * GIB for c in current),
            "peaks": [{**p, "memory.peak_gib": round(p["memory.peak"] / GIB, 3)}
                      for p in self.peaks],
        }  # fmt: skip


def scrape(port: int) -> list[str]:
    """The kp_processing_* and temporal_* sample lines of one metrics endpoint."""
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as response:
        text = response.read().decode()
    return [line for line in text.splitlines() if line.startswith(("kp_processing_", "temporal_"))]


def metric_summary(lines: list[str]) -> dict[str, float]:
    """Sum of each metric series name (labels dropped): proof that each one has values."""
    totals: dict[str, float] = {}
    for line in lines:
        name, value = re.match(r"([a-z_]+)(?:\{.*\})? (\S+)", line).groups()  # type: ignore[union-attr]
        if not name.endswith("_created"):
            totals[name] = totals.get(name, 0.0) + float(value)
    return totals


async def timeline(client: Client, request_id: str) -> dict:
    """Workflow start and close, and per Activity: type, queue, scheduled, started, closed (all
    UTC epoch seconds), the attempt that closed it and how it closed."""
    handle = client.get_workflow_handle(request_id)
    described = await handle.describe()
    history = await handle.fetch_history()
    acts: dict[int, dict] = {}
    for event in history.events:
        at = event.event_time.ToDatetime(tzinfo=UTC).timestamp()
        if event.HasField("activity_task_scheduled_event_attributes"):
            a = event.activity_task_scheduled_event_attributes
            acts[event.event_id] = {"activity": a.activity_type.name, "queue": a.task_queue.name,
                                    "scheduled": at}  # fmt: skip
        elif event.HasField("activity_task_started_event_attributes"):
            a = event.activity_task_started_event_attributes
            acts[a.scheduled_event_id].update(started=at, attempt=a.attempt)
        for field, how in (("activity_task_completed_event_attributes", "completed"),
                           ("activity_task_failed_event_attributes", "failed"),
                           ("activity_task_timed_out_event_attributes", "timed_out")):  # fmt: skip
            if event.HasField(field):
                acts[getattr(event, field).scheduled_event_id].update(closed=at, how=how)
    return {
        "start": described.start_time.timestamp(),
        "close": described.close_time.timestamp() if described.close_time else None,
        "activities": list(acts.values()),
    }


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(p * len(ordered)))], 3)


def stage_times(reports: list[dict]) -> dict[str, float]:
    """Wall seconds of each status stage, from the first running to the succeeded report."""
    from datetime import datetime

    def at(r: dict) -> float:
        return datetime.fromisoformat(r["observed_at"].replace("Z", "+00:00")).timestamp()

    times = {}
    for stage in ("prepare", "parse", "enrich", "finalize"):
        running = [at(r) for r in reports if r["stage"] == stage and r["state"] == "running"]
        done = [at(r) for r in reports if r["stage"] == stage and r["state"] == "succeeded"]
        if running and done:
            times[stage] = round(done[0] - running[0], 2)
    return times


def activity_times(line: dict) -> dict[str, dict]:
    """Per Activity type: count, total and max seconds from start to close, and timeouts."""
    out: dict[str, dict] = {}
    for a in line["activities"]:
        entry = out.setdefault(a["activity"], {"count": 0, "seconds": 0.0, "max": 0.0,
                                               "timed_out": 0})  # fmt: skip
        entry["count"] += 1
        if "started" in a and "closed" in a:
            seconds = a["closed"] - a["started"]
            entry["seconds"] = round(entry["seconds"] + seconds, 2)
            entry["max"] = round(max(entry["max"], seconds), 2)
        entry["timed_out"] += a.get("how") == "timed_out"
    return out


class Stack:
    """Temporal, fake_admission, both stand-ins and the host workers for one bucket."""

    def __init__(self, bucket: str) -> None:
        self.bucket = bucket
        ports = [TEMPORAL_PORT, TEMPORAL_PORT + 1, ADMISSION_PORT, VLM_PORT, SUMMARY_PORT,
                 *[p + d for p in METRICS.values() for d in (0, 1)],
                 *range(INFERENCE_METRICS, INFERENCE_METRICS + 6)]  # fmt: skip
        if busy := [port for port in ports if t5.taken(port)]:
            raise SystemExit(f"ports already in use: {busy}")
        t2.LOGS.mkdir(parents=True)
        self.processes = [subprocess.Popen(
            ["temporal", "server", "start-dev", "--headless", "--port", str(TEMPORAL_PORT),
             "--ui-port", str(TEMPORAL_PORT + 1), "--db-filename", str(t2.LOGS / "temporal.db"),
             "--log-level", "warn",
             "--dynamic-config-value", "matching.numTaskqueueReadPartitions=1",
             "--dynamic-config-value", "matching.numTaskqueueWritePartitions=1",
             *t2.SEARCH_ATTRIBUTE_FLAGS],
            stdout=open(t2.LOGS / "temporal.log", "w"), stderr=subprocess.STDOUT,
        ), subprocess.Popen(
            [str(t2.REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server",
             "--port", str(ADMISSION_PORT), "--log", str(t2.LOGS / "reports.jsonl")], cwd=t2.REPO,
        )]  # fmt: skip
        self.servers = [t5.stand_in(CountingStandIn, VLM_PORT),
                        t5.stand_in(t5.SummaryStandIn, SUMMARY_PORT)]  # fmt: skip
        self.containers: list[Container] = []

    async def start(self, inference: int) -> Client:
        t2.store(self.bucket)  # creates the bucket, which every worker probes on start
        for _ in range(60):
            try:
                client = await Client.connect(t2.TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        extra = {"vlm": {"KP_VLM_BASE_URL": f"http://127.0.0.1:{VLM_PORT}/v1", "KP_VLM_API_KEY": "none"},
                 "summary": {"KP_SUMMARY_BASE_URL": f"http://127.0.0.1:{SUMMARY_PORT}",
                             "KP_SUMMARY_API_KEY": "none"}}  # fmt: skip
        for queue, port in METRICS.items():
            log = open(t2.LOGS / f"worker-{queue}.log", "w")
            self.processes.append(subprocess.Popen(
                [*t2.CLI, "worker", "--queue", queue, "--profile", t2.PROFILE,
                 "--build-id", "seamb-r1", "--metrics-port", str(port),
                 "--temporal-metrics-port", str(port + 1)],
                env={**t2.env(self.bucket), **extra.get(queue, {})},
                stdout=log, stderr=subprocess.STDOUT, cwd=t2.REPO,
            ))  # fmt: skip
        for i in range(inference):
            self.containers.append(Container(f"t7-{t2.RUN}-inference-{i}", self.bucket, i))
        return client

    def metrics(self) -> dict:
        """Per endpoint, each metric's total; for the workflow's status-stage series, the label
        names the Temporal meter gives it."""
        endpoints = {q: p for q, p in METRICS.items()}
        endpoints |= {f"{q}-temporal": p + 1 for q, p in METRICS.items()}
        endpoints |= {c.name: c.metrics[0] for c in self.containers}
        endpoints |= {f"{c.name}-temporal": c.metrics[1] for c in self.containers}
        out = {}
        for name, port in endpoints.items():
            lines = scrape(port)
            (t2.LOGS / f"metrics-{name}.txt").write_text("\n".join(lines))
            out[name] = metric_summary(lines)
        stage = [line for line in scrape(METRICS["orchestration"] + 1)
                 if line.startswith(f"{STAGE_DURATION}_count")]  # fmt: skip
        out["status_stage_labels"] = sorted(
            {k for line in stage for k in re.findall(r'(\w+)="', line)}
        )
        return out

    def close(self) -> None:
        for container in self.containers:
            subprocess.run(["docker", "logs", container.name],
                           stdout=open(t2.LOGS / f"{container.name}.log", "w"),
                           stderr=subprocess.STDOUT)  # fmt: skip
            container.remove()
        for process in reversed(self.processes):
            process.terminate()
            process.wait()
        for server in self.servers:
            server.shutdown()


def paper(manifest: Path, index: int) -> tuple[dict, bytes, str]:
    entry = next(p for p in json.loads(manifest.read_text())["papers"] if p["index"] == index)
    data = (manifest.parent / entry["file"]).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    assert sha == entry["sha256"], "paper does not match the corpus manifest"
    return {k: entry[k] for k in ("index", "file", "sha256", "pages")}, data, sha


def image_digest() -> str:
    return subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
                          capture_output=True, text=True, check=True).stdout.strip()  # fmt: skip


async def run_v2(manifest: Path, index: int) -> dict:
    """One paper, uninterrupted: stage times, memory and guard samples, no timeout."""
    entry, data, sha = paper(manifest, index)
    stack = Stack(f"seamb-{t2.RUN}-t7-v2")
    try:
        client = await stack.start(inference=1)
        store = t2.store(stack.bucket)
        await store.put_if_absent(f"custody/{sha}", data)
        request_id = f"req_{t2.RUN}_v2"
        begin = time.time()
        code, result, seconds = await t4.run_case(stack.bucket, sha, data, request_id)
        end = time.time()
        line = await timeline(client, request_id)
        container = stack.containers[0]
        container.peaks.append(container.peak())
        time.sleep(1.5)
        evidence = {
            "paper": entry, "image": image_digest(), "exit": code, "seconds": seconds,
            "outcome": result.get("outcome"),
            "status_stages_s": stage_times(await t2.reports(request_id)),
            "activities": activity_times(line),
            "timeouts": sum(a.get("how") == "timed_out" for a in line["activities"]),
            "statuses": t4.per_method(result),
            "memory": container.memory(begin, end),
            "vlm_requests": CountingStandIn.total, "vlm_peak_in_flight": CountingStandIn.peak,
            "metrics": stack.metrics(),
        }  # fmt: skip
        memory = evidence["memory"]
        evidence["pass"] = (
            code == 0 and evidence["outcome"] == "complete" and evidence["timeouts"] == 0
            and memory["samples"] > 0
            and 0 < memory["peaks"][0]["memory.peak"] <= MEMORY_GIB * GIB
            and memory["peaks"][0]["oom_kill"] == 0
        )  # fmt: skip
        return evidence
    finally:
        stack.close()


async def local_keys(store, client: Client, request_id: str, uid: str) -> list[str]:
    """The outcome.json keys of the paper's local enrichment items, once inventory is done."""
    profile = load_profile(Path(t2.PROFILE))
    while True:
        history = await client.get_workflow_handle(request_id).fetch_history()
        names = {e.event_id: e.activity_task_scheduled_event_attributes.activity_type.name
                 for e in history.events
                 if e.HasField("activity_task_scheduled_event_attributes")}  # fmt: skip
        for e in history.events:
            done = e.activity_task_completed_event_attributes
            if e.HasField("activity_task_completed_event_attributes") and (
                names[done.scheduled_event_id] == "inventory"
            ):
                inventory = json.loads(
                    await store.get(json.loads(done.result.payloads[0].data)["ref"])
                )
                return [
                    f"{item_prefix(uid, enrichment_key(uid, item, profile.methods[item['method']]))}"
                    "/outcome.json"
                    for item in inventory["items"]
                    if profile.methods[item["method"]].service is None
                ]
        await asyncio.sleep(0.2)


async def run_kill(manifest: Path, index: int) -> dict:
    """The inference container killed (SIGKILL) once half the local items are registered,
    then started again: the retried enrichment reuses exactly the items registered before, and
    the statuses match the uninterrupted run (v2-INDEX.json, run first)."""
    uninterrupted = json.loads((HERE / f"v2-{index}.json").read_text())
    entry, data, sha = paper(manifest, index)
    uid = f"doc_{sha[:16]}"
    stack = Stack(f"seamb-{t2.RUN}-t7-kill")
    try:
        client = await stack.start(inference=1)
        store = t2.store(stack.bucket)
        await store.put_if_absent(f"custody/{sha}", data)
        request_id = f"req_{t2.RUN}_kill"
        start = t2.start_input(sha, data, stack.bucket, request_id)
        begin = time.time()
        code, _ = t2.start_request(stack.bucket, start, wait=False)
        keys = await local_keys(store, client, request_id, uid)
        while sum([await store.head(k) is not None for k in keys]) < (len(keys) + 1) // 2:
            await asyncio.sleep(0.1)
        container = stack.containers[0]
        container.kill()
        killed_at = time.time()
        at_kill = sum([await store.head(k) is not None for k in keys])
        container.restart()
        code, out = t2.start_request(stack.bucket, start)
        end = time.time()
        result = json.loads(await store.get(f"requests/{request_id}/result.json"))
        container.peaks.append(container.peak())
        local = [e for e in result["enrichments"] if f"{e['result_ref']}" in keys]
        line = await timeline(client, request_id)
        evidence = {
            "paper": entry, "image": image_digest(), "exit": code,
            "seconds": round(end - begin, 1), "killed_after_s": round(killed_at - begin, 1),
            "outcome": result["outcome"],
            "local_items": len(keys), "registered_at_kill": at_kill,
            "local_enrichments": len(local),
            "reused_after_restart": sum(e["reused"] for e in local),
            "enrich_local_attempts": [(a.get("attempt"), a.get("how")) for a in line["activities"]
                                      if a["activity"] == "enrich_local"],
            "statuses": t4.per_method(result),
            "memory": container.memory(begin, end),
        }  # fmt: skip
        evidence["pass"] = (
            code == 0 and result["outcome"] == "complete"
            and 0 < at_kill < len(keys)
            and evidence["local_enrichments"] == len(keys)
            and evidence["reused_after_restart"] == at_kill
            and evidence["statuses"] == uninterrupted["statuses"]
        )  # fmt: skip
        return evidence
    finally:
        stack.close()


def priority_violations(lines: dict[str, dict], bulk: set[str]) -> list[dict]:
    """Inference Activities of a bulk request that started while a normal request's inference
    Activity was scheduled and not yet started (first attempts only). History records the
    schedule a few milliseconds before the task reaches matching, where an idle worker takes
    whichever task arrives first: a normal task counts as waiting MATCHING_GRACE_S after its
    schedule."""
    acts = [(rid, a) for rid, line in lines.items() for a in line["activities"]
            if a["queue"] == "inference" and a.get("attempt") == 1 and "started" in a]  # fmt: skip
    return [
        {"bulk": rid, "activity": a["activity"], "started": a["started"], "waiting": wid}
        for rid, a in acts if rid in bulk
        for wid, w in acts
        if wid not in bulk and w["scheduled"] + MATCHING_GRACE_S < a["started"] < w["started"]
    ]  # fmt: skip


async def run_v8(manifest: Path, normal: list[int], low: int) -> dict:
    """Five normal papers and one low at once: effective VLM concurrency, queue age,
    priority, starvation and the processing-complete time of each paper."""
    stack = Stack(f"seamb-{t2.RUN}-t7-v8")
    try:
        client = await stack.start(inference=3)
        store = t2.store(stack.bucket)
        starts, papers = {}, []
        for index in [*normal, low]:
            entry, data, sha = paper(manifest, index)
            papers.append(entry)
            await store.put_if_absent(f"custody/{sha}", data)
            request_id = f"req_{t2.RUN}_v8_{index}"
            starts[request_id] = t2.start_input(
                sha, data, stack.bucket, request_id, priority="low" if index == low else "normal"
            )
        bulk = {rid for rid, s in starts.items() if s["priority"] == "low"}
        begin = time.time()
        launched = [
            asyncio.create_task(asyncio.to_thread(t2.start_request, stack.bucket, s, False))
            for s in starts.values()
        ]
        assert all(code == 0 for code, _ in await asyncio.gather(*launched))
        outcomes = await asyncio.gather(
            *[client.get_workflow_handle(rid).result() for rid in starts]
        )
        end = time.time()
        lines = {rid: await timeline(client, rid) for rid in starts}
        ages: dict[str, list[float]] = {}
        for rid, line in lines.items():
            for a in line["activities"]:
                if a.get("attempt") == 1 and "started" in a:
                    tier = "bulk" if rid in bulk else "normal"
                    ages.setdefault(f"{a['queue']}/{tier}", []).append(
                        a["started"] - a["scheduled"]
                    )
        complete = {rid: round(line["close"] - line["start"], 1) for rid, line in lines.items()}
        violations = priority_violations(lines, bulk)
        # Starvation: every normal paper's second inference Activity starts before any normal
        # paper finishes parsing, so no paper waits for another to be parsed whole. The second:
        # the first may land on an idle worker before the papers contend.
        first_parse_done = min(
            a["closed"]
            for rid, line in lines.items()
            if rid not in bulk
            for a in line["activities"]
            if a["activity"] == "assemble"
        )
        second_inference = {rid: sorted(a["started"] for a in line["activities"]
                                        if a["queue"] == "inference" and "started" in a)[1]
                            for rid, line in lines.items()}  # fmt: skip
        # Negative control: the low paper waits behind normal work, so the same check must see
        # its second inference Activity start only after a normal paper's parse is done.
        bulk_second = min(second_inference[rid] for rid in bulk)
        # Negative control: the same check, with one normal request taken for bulk, must see
        # that request's Activities start while other normal ones wait.
        control = priority_violations(lines, {sorted(set(starts) - bulk)[-1]})
        time.sleep(1.5)
        for container in stack.containers:
            container.peaks.append(container.peak())
        evidence = {
            "papers": papers, "image": image_digest(), "seconds": round(end - begin, 1),
            "outcomes": {rid: o["outcome"] for rid, o in zip(starts, outcomes, strict=True)},
            "processing_complete_s": complete,
            "vlm_requests": CountingStandIn.total,
            "vlm_peak_in_flight": CountingStandIn.peak,
            "vlm_ceiling": "1 vlm worker x 5 slots x c 4 = 20",
            "queue_age_s": {k: {"n": len(v), "p50": percentile(v, 0.5), "p95": percentile(v, 0.95),
                                "max": percentile(v, 1.0)} for k, v in sorted(ages.items())},
            "priority_violations": violations, "priority_control_hits": len(control),
            "second_inference_start_s": {rid: round(t - begin, 1)
                                         for rid, t in second_inference.items()},
            "first_parse_done_s": round(first_parse_done - begin, 1),
            "activities": {rid: activity_times(line) for rid, line in lines.items()},
            "memory": {c.name: c.memory(begin, end) for c in stack.containers},
            "metrics": stack.metrics(),
        }  # fmt: skip
        normal_times = [complete[rid] for rid in starts if rid not in bulk]
        evidence["pass"] = {
            "all_complete": all(o["outcome"] == "complete" for o in outcomes),
            "concurrency_le_28": 1 <= CountingStandIn.peak <= 28,
            "queue_age_present": all(
                evidence["queue_age_s"].get(f"{q}/{t}", {}).get("n", 0) > 0
                for q in ("orchestration", "inference", "vlm", "summary")
                for t in ("normal", "bulk")
            ),
            "no_bulk_while_normal_waits": violations == [] and len(control) > 0,
            "no_starvation": all(
                begin <= t < first_parse_done
                for rid, t in second_inference.items()
                if rid not in bulk
            )
            and bulk_second >= first_parse_done,
            "normal_within_10_min": all(0 < t <= 600 for t in normal_times),
        }
        return evidence
    finally:
        stack.close()


def main(argv: list[str]) -> int:
    mode, manifest = argv[0], Path(argv[1])
    if mode == "v8":
        normal, low = [int(i) for i in argv[2].split(",")], int(argv[3])
        evidence, out = asyncio.run(run_v8(manifest, normal, low)), HERE / "v8.json"
        ok = all(evidence["pass"].values())
    else:
        index = int(argv[2])
        run = run_v2 if mode == "v2" else run_kill
        evidence, out = asyncio.run(run(manifest, index)), HERE / f"{mode}-{index}.json"
        ok = evidence["pass"]
    evidence["run"] = t2.RUN
    out.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({k: v for k, v in evidence.items()
                      if k not in ("metrics", "activities")}, indent=1))  # fmt: skip
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
