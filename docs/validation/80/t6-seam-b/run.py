"""Seam B for #135: reuse across requests, builds and Processing Profile versions (V3), and the
upgrade, patch and retirement of a version through Worker Versioning (V1, local rehearsal, the
flow of #178), on one paper in one bucket.

    scripts/heavy-lock t6-seam-b -- \\
        .venv/bin/python docs/validation/80/t6-seam-b/run.py CORPUS_MANIFEST [PAPER_INDEX]

Needs the S3 stand-in (tests/s3/compose.yaml, port 9100), the `temporal` CLI and the model
weights. Ports of its own (Temporal 7304/7305, fake_admission 8141, VLM stand-in 8142, summary
stand-in 8143, d3 stand-in 8144); it refuses to start when any is taken. No request leaves the
machine: the VLM stand-in replays the gpt-6-luna recordings (tests/fixtures/vlm), the summary
stand-in is the DEV fake and the d3 stand-in answers every question with 0.99.

A build is five `kp-canonicalization worker` processes, one per task queue, that take their
Worker Deployment and build ID from TEMPORAL_DEPLOYMENT_NAME and TEMPORAL_WORKER_BUILD_ID, as the
chart will inject them. Requests go through `start-request`, which is admission's start: the
orchestration queue of the request's adopted_version, no map and no override. The Temporal side
is driven only by `kp-canonicalization promote VALUES`, the promoter CronJob's command, over the
values file this run rewrites the way a deployment values PR would.

Processing Profile versions:
  paper-pdf@1  the DEV profile (tests/profiles/paper-pdf-dev.yaml), from this tree
  paper-pdf@2  the same with picture-interpretation@2, from a second tree: a copy of
               src/kp_canonicalization whose picture_interpretation package says VERSION = 2.
               One tree loads one profile version, as one image does.
The dev server refreshes drainage and forgets pollers after seconds instead of minutes.

Steps (cli/ keeps each temporal CLI and promoter output, evidence.json the checks):
  1  adoption before rollout: R1 starts on a queue nothing polls and waits; a worker whose
     TEMPORAL_DEPLOYMENT_NAME names another version refuses to start; with four of
     paper-pdf-1-r1's queues polled the promoter waits; with five it makes the build current
  2  R1 then runs, on 1-r1 only, Pinned, and yields an enrichment of every kind, so the later
     reuse checks cannot pass on a kind the paper lacks
  3  R2 resubmission (new request, new source revision) and R3 redrive (operator, same
     revision): no inference request, every parse group, the assembly, the inventory and every
     enrichment reused, nothing new under documents/
  4  patch: 1-r2 starts beside 1-r1 and is listed; R4 starts on the current 1-r1 and is held
     open (1-r1's inference worker is down); `current` moves to 1-r2 and the promoter switches;
     R5 runs on 1-r2 while R4 stays on 1-r1; taking 1-r1's tag off the values while R4 is open
     makes the promoter exit 1; the worker returns, R4 completes on 1-r1; the tag comes off, the
     pods stop and the promoter deletes the version once Temporal forgets its pollers
  5  upgrade: paper-pdf-2-r1 from the second tree is listed and becomes current; R6, the refresh
     under paper-pdf@2, computes picture-interpretation@2 and nothing else: no parse, no
     summary and no d3 request; the result's profile section names paper-pdf@2 and
     picture-interpretation@2 with a new module digest
  6  R7, a resubmission under paper-pdf@2: nothing is computed
  7  retirement: paper-pdf-1 leaves the values; the promoter sets it unversioned, deletes its
     version once the pods are gone and forgotten, then deletes the Worker Deployment
  8  which build IDs and deployment names a worker can join with (`-`, `@`, `.`, `/`)
The paper stays out of git; evidence keeps counts, IDs and statuses only.
"""

import asyncio
import getpass
import hashlib
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml
from temporalio import activity
from temporalio.client import Client
from temporalio.common import WorkerDeploymentVersion
from temporalio.worker import Worker, WorkerDeploymentConfig

from kp_canonicalization.workflow import QUEUES

HERE = Path(__file__).resolve().parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


t5c = load("t5c", HERE.parent / "t5c-seam-b/run.py")
t5, t4, t2 = t5c.t5, t5c.t4, t5c.t2
from tests.d3 import system_one  # noqa: E402

TEMPORAL_PORT, ADMISSION_PORT, VLM_PORT, SUMMARY_PORT, D3_PORT = 7304, 8141, 8142, 8143, 8144
t2.TEMPORAL, t2.ADMISSION = f"127.0.0.1:{TEMPORAL_PORT}", f"http://127.0.0.1:{ADMISSION_PORT}"
t2.BASE_ENV.update(TEMPORAL_ADDRESS=t2.TEMPORAL, KP_ADMISSION_URL=t2.ADMISSION)
SERVICES = {
    "vlm": {"KP_VLM_BASE_URL": f"http://127.0.0.1:{VLM_PORT}/v1", "KP_VLM_API_KEY": "none"},
    "summary": {"KP_SUMMARY_BASE_URL": f"http://127.0.0.1:{SUMMARY_PORT}/v1",
                "KP_SUMMARY_API_KEY": "none"},
    "d3": {"KP_D3_BASE_URL": f"http://127.0.0.1:{D3_PORT}", "KP_D3_API_KEY": "none"},
}  # fmt: skip
V1, V2 = "paper-pdf-1", "paper-pdf-2"  # the Worker Deployments of paper-pdf@1 and paper-pdf@2
R1, R2, U1 = "paper-pdf-1-r1", "paper-pdf-1-r2", "paper-pdf-2-r1"  # builds: image tags
BUMPED = "picture-interpretation"
STEPS = ("1", "2", "3", "4", "5", "6", "7", "8")
# The Activities every complete request runs, whether they compute or reuse.
EVERY_REQUEST = {"parse_group", "assemble", "inventory", "summary_sections", "enrich_local",
                 "enrich_vlm", "check"}  # fmt: skip
KINDS = {"picture-ocr", "picture-interpretation", "formula", "code", "table-status",
         "document-summary"}  # fmt: skip
# (deployment, build ID, whether the server lists the version); the last is the SDK's split at `.`
NAMES = (("names-probe", "a-1", True), ("names-probe", "a@1", True), ("names-probe", "a.1", True),
         ("names-probe", "a/1", True), ("names.probe", "a-1", False))  # fmt: skip
CALLS: Counter = Counter()  # requests each stand-in answered
CLI_OUT = HERE / "cli"
REDACT = {socket.gethostname(): "<host>", getpass.getuser(): "<user>"}


class Vlm(t5c.Replay):
    def answer(self, request: dict) -> bytes:
        CALLS["vlm"] += 1
        return super().answer(request)


class Summary(t5c.Summary):
    def answer(self, request: dict) -> bytes:
        CALLS["summary"] += 1
        return super().answer(request)


class D3(t5c.StandIn):
    def answer(self, request: dict) -> bytes:
        CALLS["d3"] += 1
        return system_one(request, 0.99).body


def redact(text: str) -> str:
    for secret, mask in REDACT.items():
        text = text.replace(secret, mask)
    return text


STEP = Counter()


def temporal(name: str, *args: str, check: bool = True) -> tuple[int, str]:
    """A temporal CLI command against this run's server; its output is kept in cli/."""
    done = subprocess.run(["temporal", *args, "--address", t2.TEMPORAL], capture_output=True,
                          text=True)  # fmt: skip
    out = redact(done.stdout + done.stderr)
    STEP["n"] += 1
    (CLI_OUT / f"{STEP['n']:02d}-{name}.txt").write_text(
        f"$ temporal {' '.join(args)}\n# exit {done.returncode}\n{out}"
    )
    if check and done.returncode:
        raise SystemExit(f"temporal {name} failed: {out}")
    return done.returncode, out


def build(bucket, deployment, build_id, profile, queues=QUEUES, tree: Path | None = None) -> dict:
    """One worker per queue of a build, keyed by queue, with the environment the chart injects.
    `tree` is the src directory the build's image holds when it is not this checkout's."""
    processes = {}
    for queue in queues:
        log = open(t2.LOGS / f"worker-{build_id}-{queue}.log", "a")
        processes[queue] = subprocess.Popen(
            [*t2.CLI, "worker", "--queue", queue, "--profile", str(profile)],
            env={**t2.env(bucket), **SERVICES.get(queue, {}),
                 "TEMPORAL_DEPLOYMENT_NAME": deployment, "TEMPORAL_WORKER_BUILD_ID": build_id,
                 **({"PYTHONPATH": str(tree)} if tree else {})},
            stdout=log, stderr=subprocess.STDOUT, cwd=t2.REPO,
        )  # fmt: skip
    return processes


def promote(name: str, values: dict) -> tuple[int, str]:
    """One promoter run over the deployment values, as the CronJob runs it; output kept in cli/."""
    path = t2.LOGS / "values.yaml"
    path.write_text(yaml.safe_dump({"profiles": values}))
    done = subprocess.run([*t2.CLI, "promote", str(path)], env=t2.BASE_ENV, capture_output=True,
                          text=True, cwd=t2.REPO)  # fmt: skip
    out = redact(done.stdout + done.stderr)
    STEP["n"] += 1
    (CLI_OUT / f"{STEP['n']:02d}-{name}.txt").write_text(
        f"$ kp-canonicalization promote values.yaml\n# values: {json.dumps(values)}\n"
        f"# exit {done.returncode}\n{out}"
    )
    return done.returncode, out


def deployment(name: str, label: str | None = None) -> dict:
    """{current, builds: {build: drainage status}} of a Worker Deployment; {} when Temporal has
    none by that name."""
    args = ("worker", "deployment", "describe", "--name", name, "-o", "json")
    if label:
        code, out = temporal(label, *args, check=False)
    else:
        done = subprocess.run(["temporal", *args, "--address", t2.TEMPORAL], capture_output=True,
                              text=True)  # fmt: skip
        code, out = done.returncode, done.stdout
    if code:
        return {}
    described = json.loads(out)
    return {"current": described["routingConfig"].get("currentVersionBuildID") or None,
            "builds": {v["BuildID"]: v.get("drainageStatus", "unspecified")
                       for v in described.get("versionSummaries") or []}}  # fmt: skip


def promoted(name: str, values: dict, watch: str, until, limit_s: float = 120) -> dict:
    """Run the promoter every second until deployment(watch) satisfies `until`. Keeps the first
    and the last run's output; returns how many runs it took and each distinct exit code."""
    codes, begin = [], time.monotonic()
    while time.monotonic() - begin < limit_s:
        code, _ = promote(name, values)
        codes.append(code)
        if until(deployment(watch)):
            return {"runs": len(codes), "exit_codes": sorted(set(codes)),
                    "seconds": round(time.monotonic() - begin, 1)}  # fmt: skip
        STEP["n"] -= 1 if len(codes) > 1 else 0
        time.sleep(1)
    raise SystemExit(f"promoter {name}: {watch} is {deployment(watch)} after {limit_s} s")


def start(bucket: str, start_input: dict, wait: bool = True) -> subprocess.Popen:
    """The dispatcher stand-in: start-request, which calls admission's start; the process."""
    path = t2.LOGS / f"{start_input['request_id']}.json"
    path.write_text(json.dumps(start_input))
    return subprocess.Popen(
        [*t2.CLI, "start-request", str(path), *(["--wait"] if wait else [])],
        env=t2.env(bucket), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        cwd=t2.REPO,
    )  # fmt: skip


def open_workflows(name: str, query: str) -> int:
    _, out = temporal(name, "workflow", "count", "--query",
                      f'{query} AND ExecutionStatus="Running"', "-o", "json")  # fmt: skip
    return int(json.loads(out).get("count", 0))


async def activities(client: Client, request_id: str, pids: dict[int, str]) -> list[dict]:
    """Per Activity execution: type, the build of the worker that ran it, the reused flags."""
    history = await client.get_workflow_handle(request_id).fetch_history()
    scheduled, started, out = {}, {}, []
    for event in history.events:
        if event.HasField("activity_task_scheduled_event_attributes"):
            name = event.activity_task_scheduled_event_attributes.activity_type.name
            scheduled[event.event_id] = name
        elif event.HasField("activity_task_started_event_attributes"):
            a = event.activity_task_started_event_attributes
            started[a.scheduled_event_id] = int(a.identity.split("@")[0])
        elif event.HasField("activity_task_completed_event_attributes"):
            a = event.activity_task_completed_event_attributes
            data = a.result.payloads[0].data if a.result.payloads else b""
            payload = json.loads(data) if data else None  # an Activity returning None sends b""
            items = payload if isinstance(payload, list) else [payload]
            out.append({
                "activity": scheduled[a.scheduled_event_id],
                "build": pids.get(started[a.scheduled_event_id], "unknown"),
                "reused": [i.get("reused") for i in items if isinstance(i, dict)
                           and "reused" in i] or None,
            })  # fmt: skip
    return out


async def outcome(store, request_id: str) -> dict:
    for name in ("result", "failure"):
        key = f"requests/{request_id}/{name}.json"
        if await store.head(key) is not None:
            return {"kind": name, **json.loads(await store.get(key))}
    return {"kind": None}


async def case(client, store, bucket, start_input, pids, uid) -> dict:
    """Run one request through the dispatcher stand-in; what it sent, ran and added."""
    before = set(await store.list_prefix(f"documents/{uid}/"))
    calls = Counter(CALLS)
    begin = time.monotonic()
    process = start(bucket, start_input)
    output = process.communicate()[0]
    return await observe(client, store, start_input, process.returncode, output, before, calls,
                         begin, pids, uid)  # fmt: skip


async def observe(client, store, start_input, code, output, before, calls, begin, pids, uid):
    request_id = start_input["request_id"]
    result = await outcome(store, request_id)
    added = set(await store.list_prefix(f"documents/{uid}/")) - before
    ran = await activities(client, request_id, pids) if code == 0 else []
    _, described = temporal(f"describe-{request_id}", "workflow", "describe", "--workflow-id",
                            request_id, "-o", "json", check=False)  # fmt: skip
    info = (json.loads(described).get("workflowExecutionInfo", {})
            if described.startswith("{") else {})  # fmt: skip
    (t2.LOGS / f"result-{request_id}.json").write_text(json.dumps(result, indent=2))
    enrichments = result.get("enrichments", [])
    return {
        "request_id": request_id,
        "exit": code,
        "output": redact(output.strip().splitlines()[-1]) if output.strip() else "",
        "seconds": round(time.monotonic() - begin, 1),
        "started": info.get("startTime"),
        "closed": info.get("closeTime"),
        "outcome": result.get("outcome") or result["kind"],
        "reason": (result.get("error") or {}).get("reason"),
        "category": ((result.get("error") or {}).get("metadata") or {}).get("category"),
        "build_id": result.get("profile", {}).get("runtime_identity", {}).get("build_id"),
        "profile": result.get("profile", {}).get("id"),
        "profile_methods": {f"{m['id']}@{m['version']}": m["module_digest"]
                            for m in result.get("profile", {}).get("methods", [])},
        "task_queue": info.get("taskQueue"),
        "versioning_info": info.get("versioningInfo"),
        "stand_in_calls": dict(CALLS - calls),
        "receipts": dict(Counter(r["method"] for r in await t4.receipts(store, request_id))),
        "activity_builds": sorted({a["build"] for a in ran}),
        "activities": dict(Counter(a["activity"] for a in ran)),
        "fresh_activities": sorted({a["activity"] for a in ran
                                    if a["reused"] and not all(a["reused"])}),
        "enrichments": len(enrichments),
        "enrichments_reused": sum(e["reused"] for e in enrichments),
        "enrichment_methods": dict(Counter(e["method_ref"]["id"] for e in enrichments)),
        "item_folders_added": len({k.split("/")[3] for k in added if "/items/" in k}),
        "objects_added_outside_items": sum("/items/" not in k for k in added),
    }  # fmt: skip


def all_reused(c: dict) -> bool:
    """Nothing was computed: no inference request and no fresh Activity or registered item."""
    return (
        c["outcome"] == "complete" and c["stand_in_calls"] == {} and c["receipts"] == {}
        and c["fresh_activities"] == [] and EVERY_REQUEST <= set(c["activities"])
        and c["enrichments_reused"] == c["enrichments"] > 0
        and c["item_folders_added"] == c["objects_added_outside_items"] == 0
    )  # fmt: skip


def pinned_to(c: dict, deployment: str, build_id: str) -> bool:
    """The workflow is Pinned to the build by its worker's default, with no override, and every
    Activity ran on that build."""
    info = c["versioning_info"] or {}
    return (
        info.get("behavior") == "VERSIONING_BEHAVIOR_PINNED" and "versioningOverride" not in info
        and info.get("deploymentVersion") == {"deploymentName": deployment, "buildId": build_id}
        and c["build_id"] == build_id and c["activity_builds"] == [build_id]
        and c["task_queue"] == f"{deployment}.orchestration"
    )  # fmt: skip


def instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def overlap_s(a: dict, b: dict) -> float:
    """How long two requests' workflows ran at once, by the server's times; negative when apart."""
    latest_start = max(instant(a["started"]), instant(b["started"]))
    earliest_close = min(instant(a["closed"]), instant(b["closed"]))
    return (earliest_close - latest_start).total_seconds()


@activity.defn
async def noop() -> None:
    pass


async def listed(client: Client, deployment: str, build_id: str) -> dict:
    """Whether a worker can join with this version: the server lists its task queue."""
    queue = "names-probe"
    config = WorkerDeploymentConfig(WorkerDeploymentVersion(deployment, build_id),
                                    use_worker_versioning=True)  # fmt: skip
    STEP["names"] += 1
    async with Worker(client, task_queue=queue, activities=[noop], deployment_config=config):
        await asyncio.sleep(2)
        code, out = temporal(f"describe-version-name-{STEP['names']}", "worker", "deployment",
                             "describe-version", "--deployment-name", deployment, "--build-id",
                             build_id, "-o", "json", check=False)  # fmt: skip
    return {"deployment": deployment, "build_id": build_id, "listed": code == 0 and queue in out}


def stop(processes) -> None:
    t5c.stop(list(processes))


async def main(manifest: Path, index: int) -> int:
    ports = (TEMPORAL_PORT, TEMPORAL_PORT + 1, ADMISSION_PORT, VLM_PORT, SUMMARY_PORT, D3_PORT)
    if busy := [port for port in ports if t5.taken(port)]:
        raise SystemExit(f"ports already in use: {busy}")
    t2.LOGS.mkdir(parents=True)
    CLI_OUT.mkdir(exist_ok=True)
    for old in CLI_OUT.glob("*.txt"):
        old.unlink()
    paper = next(p for p in json.loads(manifest.read_text())["papers"] if p["index"] == index)
    data = (manifest.parent / paper["file"]).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    assert sha == paper["sha256"], "paper does not match the corpus manifest"
    bucket, uid = f"seamb-{t2.RUN}-t6", f"doc_{sha[:16]}"
    store = t2.store(bucket)
    await store.put_if_absent(f"custody/{sha}", data)

    # The second tree: what the image of paper-pdf@2 holds.
    tree = t2.LOGS / "tree-2"
    shutil.copytree(t2.REPO / "src/kp_canonicalization", tree / "kp_canonicalization",
                    ignore=shutil.ignore_patterns("__pycache__"))  # fmt: skip
    package = tree / "kp_canonicalization/methods" / BUMPED.replace("-", "_") / "__init__.py"
    source = package.read_text()
    assert source.count("\nVERSION = 1\n") == 1
    package.write_text(source.replace("\nVERSION = 1\n", "\nVERSION = 2\n"))
    profile_1 = Path(t2.PROFILE)
    text = profile_1.read_text()
    assert text.count("profile: paper-pdf@1\n") == text.count(f"  {BUMPED}@1:\n") == 1
    profile_2 = t2.LOGS / "paper-pdf-dev@2.yaml"
    profile_2.write_text(text.replace("profile: paper-pdf@1\n", "profile: paper-pdf@2\n")
                         .replace(f"  {BUMPED}@1:\n", f"  {BUMPED}@2:\n"))  # fmt: skip

    fast = ["matching.wv.VersionDrainageStatusRefreshInterval=\"2s\"",
            "matching.wv.VersionDrainageStatusVisibilityGracePeriod=\"2s\"",
            "matching.PollerHistoryTTL=\"5s\""]  # fmt: skip
    server = subprocess.Popen(
        ["temporal", "server", "start-dev", "--headless", "--port", str(TEMPORAL_PORT),
         "--ui-port", str(TEMPORAL_PORT + 1), "--db-filename", str(t2.LOGS / "temporal.db"),
         "--log-level", "warn", *t2.SEARCH_ATTRIBUTE_FLAGS,
         *[a for value in fast for a in ("--dynamic-config-value", value)]],
        stdout=open(t2.LOGS / "temporal.log", "w"), stderr=subprocess.STDOUT,
    )  # fmt: skip
    admission = subprocess.Popen(
        [str(t2.REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server",
         "--port", str(ADMISSION_PORT), "--log", str(t2.LOGS / "reports.jsonl")], cwd=t2.REPO,
    )  # fmt: skip
    servers = [t5.stand_in(Vlm, VLM_PORT), t5.stand_in(Summary, SUMMARY_PORT),
               t5.stand_in(D3, D3_PORT)]  # fmt: skip
    builds: dict[str, dict] = {}
    pids: dict[int, str] = {}
    evidence: dict = {"run": t2.RUN, "paper": {k: paper[k] for k in ("index", "sha256", "pages")},
                      "dynamic_config": fast}  # fmt: skip

    def up(deployment_name, build_id, profile, queues=QUEUES, tree=None) -> None:
        started = build(bucket, deployment_name, build_id, profile, queues, tree)
        builds.setdefault(build_id, {}).update(started)
        pids.update({p.pid: build_id for p in started.values()})

    def request(name: str, **overrides) -> dict:
        return t2.start_input(sha, data, bucket, f"req_{t2.RUN}_{name}", **overrides)

    def version_2(name: str, **overrides) -> dict:
        return request(name, adopted_version="paper-pdf@2", adoption_sequence=2, **overrides)

    try:
        client = None
        for _ in range(60):
            try:
                client = await Client.connect(t2.TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        assert client is not None

        # 1. adoption before rollout, then the first build
        r1_start = request("r1")
        r1_before = set(await store.list_prefix(f"documents/{uid}/"))
        r1_calls, r1_begin = Counter(CALLS), time.monotonic()
        r1 = start(bucket, r1_start)
        values = {V1: {"builds": [R1], "current": R1}}
        no_pods_code, _ = promote("promote-no-pods", values)
        mislisted = build(bucket, V2, "mislisted", profile_1, ("orchestration",))["orchestration"]
        mislisted_code = mislisted.wait(timeout=60)
        mislisted_log = (t2.LOGS / "worker-mislisted-orchestration.log").read_text()
        up(V1, R1, profile_1, QUEUES[:4])
        four = promoted("promote-four-queues", values, V1, lambda d: R1 in d.get("builds", {}))
        await asyncio.sleep(3)  # long enough for a wrong promotion to show
        after_four = deployment(V1)
        waiting = open_workflows("count-open-before-current", f'TaskQueue="{V1}.orchestration"')
        up(V1, R1, profile_1, QUEUES[4:])
        five = promoted("promote-five-queues", values, V1, lambda d: d.get("current") == R1)
        _, described = temporal("describe-version-1-r1", "worker", "deployment",
                                "describe-version", "--deployment-name", V1, "--build-id", R1,
                                "-o", "json")  # fmt: skip
        evidence["1"] = {
            "promoter_without_pods_exit": no_pods_code,
            "mislisted_worker": {"exit": mislisted_code,
                                 "error": redact(mislisted_log.strip().splitlines()[-1])},
            "after_four_queues": after_four, "promoter_four_queues": four,
            "open_before_current": waiting, "promoter_five_queues": five,
            "task_queues": sorted({q["name"] for q in json.loads(described)["taskQueuesInfos"]}),
        }  # fmt: skip
        evidence["1"]["pass"] = (
            no_pods_code == 0 and mislisted_code == 2
            and "TEMPORAL_DEPLOYMENT_NAME is paper-pdf-2" in mislisted_log
            and after_four == {"current": None, "builds": {R1: "unspecified"}}
            and four["exit_codes"] == [0] and waiting == 1 and r1.poll() is None
            and five["exit_codes"] == [0]
            and evidence["1"]["task_queues"] == sorted(f"{V1}.{queue}" for queue in QUEUES)
        )  # fmt: skip

        # 2. the request that waited runs: the first processing
        r1_out = r1.communicate()[0]
        r1 = evidence["2"] = await observe(client, store, r1_start, r1.returncode, r1_out,
                                           r1_before, r1_calls, r1_begin, pids, uid)  # fmt: skip
        r1["pass"] = (
            r1["outcome"] == "complete" and pinned_to(r1, V1, R1)
            and r1["stand_in_calls"].get("vlm", 0) > 0
            and r1["stand_in_calls"].get("summary", 0) > 0
            and r1["stand_in_calls"].get("d3", 0) > 0
            and r1["item_folders_added"] > 0 and KINDS <= set(r1["enrichment_methods"])
        )  # fmt: skip

        # 3. resubmission and redrive
        r2 = await case(client, store, bucket, request("r2", source_revision_id="srv_2"), pids, uid)
        r3 = await case(client, store, bucket, request("r3", initiator="operator"), pids, uid)
        evidence["3"] = {"resubmission": r2, "redrive": r3,
                         "pass": all_reused(r2) and all_reused(r3)
                         and pinned_to(r2, V1, R1) and pinned_to(r3, V1, R1)
                         and r2["enrichment_methods"] == r3["enrichment_methods"]
                         == r1["enrichment_methods"]}  # fmt: skip

        # 4. a patch build, a workflow held on the old one, and the old tag taken off too early
        up(V1, R2, profile_1)
        values = {V1: {"builds": [R1, R2], "current": R1}}
        listed_only = promoted("promote-1-r2-listed", values, V1,
                               lambda d: set(d.get("builds", {})) == {R1, R2})  # fmt: skip
        stop([builds[R1].pop("inference")])
        r4_start = request("r4")
        r4_calls, r4_begin = Counter(CALLS), time.monotonic()
        r4_before = set(await store.list_prefix(f"documents/{uid}/"))
        r4 = start(bucket, r4_start)
        pinned = f'TemporalWorkerDeploymentVersion="{V1}:{R1}"'
        for _ in range(60):
            if open_workflows("count-open-1-r1-while-r4", pinned) == 1:
                break
            STEP["n"] -= 1
            await asyncio.sleep(0.5)
        values = {V1: {"builds": [R1, R2], "current": R2}}
        switched = promoted("promote-current-1-r2", values, V1, lambda d: d.get("current") == R2)
        r5 = await case(client, store, bucket, request("r5"), pids, uid)
        await asyncio.sleep(6)  # several drainage refreshes and visibility grace periods
        while_r4 = deployment(V1, "describe-deployment-while-r4")
        early_code, early_out = promote("promote-1-r1-tag-off-early",
                                        {V1: {"builds": [R2], "current": R2}})  # fmt: skip
        after_alarm = deployment(V1)
        back_code, _ = promote("promote-1-r1-tag-back", values)
        up(V1, R1, profile_1, ("inference",))
        r4_out = r4.communicate()[0]
        r4_done = await observe(client, store, r4_start, r4.returncode, r4_out, r4_before,
                                r4_calls, r4_begin, pids, uid)  # fmt: skip
        drained = None
        for _ in range(60):
            drained = deployment(V1)
            if drained["builds"].get(R1) == "drained":
                break
            await asyncio.sleep(1)
        deployment(V1, "describe-deployment-1-r1-drained")
        values = {V1: {"builds": [R2], "current": R2}}
        with_pods_code, with_pods_out = promote("promote-1-r1-tag-off-pods-up", values)
        stop(builds.pop(R1).values())
        deleted = promoted("promote-1-r1-deleted", values, V1,
                           lambda d: set(d.get("builds", {})) == {R2})  # fmt: skip
        evidence["4"] = {
            "promoter_listed_only": listed_only, "promoter_switch": switched,
            "r4": r4_done, "r5": r5, "while_r4": while_r4,
            "tag_off_early": {"exit": early_code, "alarm": early_out.strip().splitlines()[-1],
                              "after": after_alarm},
            "tag_back_exit": back_code,
            "drained": drained,
            "tag_off_with_pods_up": {"exit": with_pods_code,
                                     "output": with_pods_out.strip().splitlines()[0]},
            "promoter_delete": deleted,
        }  # fmt: skip
        evidence["4"]["pass"] = (
            listed_only["exit_codes"] == switched["exit_codes"] == [0]
            and pinned_to(r4_done, V1, R1) and all_reused(r4_done)  # waited; no hop to current
            and pinned_to(r5, V1, R2) and all_reused(r5)
            and instant(r5["closed"]) < instant(r4_done["closed"])
            and while_r4 == {"current": R2, "builds": {R1: "draining", R2: "unspecified"}}
            and early_code == 1 and f"{V1}:{R1}: 1 open workflows" in early_out
            and after_alarm == while_r4 and back_code == 0
            and drained == {"current": R2, "builds": {R1: "drained", R2: "unspecified"}}
            and with_pods_code == 0 and "active pollers" in with_pods_out
            and deleted["exit_codes"] == [0] and deleted["runs"] > 1
        )  # fmt: skip

        # 5. the upgrade: a second version from the second tree, and the refresh under it
        up(V2, U1, profile_2, tree=tree)
        values = {V1: {"builds": [R2], "current": R2}, V2: {"builds": [U1], "current": U1}}
        upgraded = promoted("promote-2-r1", values, V2, lambda d: d.get("current") == U1)
        r6 = evidence["5"] = await case(client, store, bucket,
                                        version_2("r6", initiator="platform"), pids, uid)  # fmt: skip
        r6["promoter"] = upgraded
        bumped = r6["receipts"].get(f"{BUMPED}@2", 0)
        others = {ref: digest for ref, digest in r6["profile_methods"].items()
                  if ref != f"{BUMPED}@2"}  # fmt: skip
        r6["pass"] = (
            upgraded["exit_codes"] == [0] and deployment(V1)["current"] == R2
            and r6["outcome"] == "complete" and pinned_to(r6, V2, U1)
            and r6["profile"] == "paper-pdf@2"
            and r6["profile_methods"][f"{BUMPED}@2"] != r1["profile_methods"][f"{BUMPED}@1"]
            and others == {ref: digest for ref, digest in r1["profile_methods"].items()
                           if ref != f"{BUMPED}@1"}
            and r6["stand_in_calls"] == {"vlm": bumped} and bumped > 0
            and r6["receipts"] == {f"{BUMPED}@2": bumped}
            and r6["fresh_activities"] == ["enrich_vlm", "inventory"]
            and r6["objects_added_outside_items"] == 0
            and r6["enrichment_methods"] == r1["enrichment_methods"]
            and r6["enrichments"] - r6["enrichments_reused"]
            == r1["enrichment_methods"][BUMPED]
        )  # fmt: skip

        # 6. a resubmission under paper-pdf@2
        r7 = evidence["6"] = await case(client, store, bucket,
                                        version_2("r7", source_revision_id="srv_3"), pids, uid)  # fmt: skip
        r7["pass"] = all_reused(r7) and pinned_to(r7, V2, U1) and r7["profile"] == "paper-pdf@2"

        # 7. retirement of paper-pdf@1
        values = {V2: {"builds": [U1], "current": U1}}
        open_before = open_workflows("count-open-paper-pdf-1", f'TaskQueue="{V1}.orchestration"')
        before = deployment(V1, "describe-deployment-1-before-retirement")
        with_pods_code, with_pods_out = promote("promote-retire-pods-up", values)
        unversioned = deployment(V1)
        stop(builds.pop(R2).values())
        retired = promoted("promote-retired", values, V1, lambda d: d == {})
        _, gone = temporal("describe-deployment-1-after-retirement", "worker", "deployment",
                           "describe", "--name", V1, check=False)  # fmt: skip
        r8 = await case(client, store, bucket, version_2("r8", source_revision_id="srv_4"), pids,
                        uid)  # fmt: skip
        evidence["7"] = {
            "open_before": open_before, "before": before,
            "with_pods_up": {"exit": with_pods_code, "after": unversioned},
            "promoter": retired, "after": redact(gone.strip().splitlines()[-1]),
            "paper_pdf_2_after": deployment(V2), "r8": r8,
        }  # fmt: skip
        evidence["7"]["pass"] = (
            open_before == 0 and before == {"current": R2, "builds": {R2: "unspecified"}}
            and with_pods_code == 0 and "set unversioned" in with_pods_out
            and unversioned["current"] is None and set(unversioned["builds"]) == {R2}
            and retired["exit_codes"] == [0] and "no Worker Deployment found" in gone
            and evidence["7"]["paper_pdf_2_after"] == {"current": U1,
                                                       "builds": {U1: "unspecified"}}
            and all_reused(r8) and pinned_to(r8, V2, U1)
        )  # fmt: skip

        # 8. the names a worker can join with
        names = [await listed(client, deployment, build_id) for deployment, build_id, _ in NAMES]
        evidence["8"] = {"names": names,
                         "pass": [n["listed"] for n in names] == [n[2] for n in NAMES]}  # fmt: skip
    finally:
        stop([p for b in builds.values() for p in b.values()])
        stop([admission, server])
        for s in servers:
            s.shutdown()

    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    failed = [step for step in STEPS if not evidence.get(step, {}).get("pass")]
    print("failed:", failed or "none", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 7)))
