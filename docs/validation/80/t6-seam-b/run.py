"""Seam B for #135: Worker Versioning (V1, local rehearsal) and reuse across requests, builds and
profile versions (V3), on one paper in one bucket.

    .venv/bin/python docs/validation/80/t6-seam-b/run.py CORPUS_MANIFEST [PAPER_INDEX]

Needs the S3 stand-in (tests/s3/compose.yaml, port 9100), the `temporal` CLI and the model
weights. Ports of its own (Temporal 7304/7305, fake_admission 8141, VLM stand-in 8142, summary
stand-in 8143, d3 stand-in 8144); it refuses to start when any is taken. No request leaves the
machine: the VLM stand-in replays the gpt-6-luna recordings (tests/fixtures/vlm), the summary
stand-in is the DEV fake and the d3 stand-in answers every question with 0.99.

Every build is a set of `kp-canonicalization worker --build-id B` processes, one per task queue, in
Worker Deployment canonicalization; every request goes through `start-request --builds MAP`, the
dispatcher stand-in. Profiles, both DEV (tests/profiles/paper-pdf-dev.yaml) with another id:
  A  paper-pdf@1: the DEV profile without d3-check@1 (no d3 queue)
  B  paper-pdf@2: the DEV profile, so A plus d3-check@1: the rehearsal of adding a method
The dev server refreshes drainage and forgets pollers after seconds instead of minutes.

Steps (cli/ keeps each temporal CLI output, evidence.json the checks):
  1  build paper-pdf-1-r1 (A): a start pinned to it before its workers polled is refused; it
     joins the deployment on its four queues; set-current-version makes it current
  2  R1 pinned to 1-r1 by the map: the paper is processed, on 1-r1 only
  3  R2 resubmission (new request, new source revision) and R3 redrive (operator, same
     revision): no inference request, every parse group, the assembly, the inventory and every
     enrichment reused, nothing new under documents/
  4  build paper-pdf-1-r2 (A, a patch) beside 1-r1, which stays current: R4 pinned to 1-r2 by
     the new map and R5 pinned to 1-r1 by the old one run at once, each on its own build
  5  retire 1-r1: current moves to 1-r2; with 1-r1's inference worker stopped, R6 pinned to
     1-r1 stays open; visibility counts it while the version's drainage status is read; the
     worker returns, R6 completes on 1-r1, visibility counts 0, 1-r1's workers stop and its
     version is deleted
  6  build paper-pdf-2-r1 (B) on five queues; a map that sends paper-pdf@1 to it fails R7
     with integrity (ADOPTED_VERSION_MISMATCH)
  7  R8, the refresh of the document under paper-pdf@2: only d3-check@1 runs (one d3 request
     per check item, no VLM or summary request, parse reused); the result's profile section
     names paper-pdf@2 and d3-check@1 with its module digest; 2-r1 becomes current
The paper stays out of git; evidence keeps counts, IDs and statuses only.
"""

import asyncio
import getpass
import hashlib
import importlib.util
import json
import socket
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import yaml
from temporalio.client import Client

from kp_canonicalization.workflow import DEPLOYMENT

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
QUEUES_A = ("orchestration", "inference", "vlm", "summary")
QUEUES_B = (*QUEUES_A, "d3")
CHECK = "d3-check@1"
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
        return system_one(request, 0.99).body.encode()


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


def build(bucket: str, build_id: str, profile: Path, queues: tuple[str, ...]) -> dict:
    """One worker per queue of a build, keyed by queue."""
    processes = {}
    for queue in queues:
        log = open(t2.LOGS / f"worker-{build_id}-{queue}.log", "a")
        processes[queue] = subprocess.Popen(
            [*t2.CLI, "worker", "--queue", queue, "--profile", str(profile),
             "--build-id", build_id],
            env={**t2.env(bucket), **SERVICES.get(queue, {})}, stdout=log,
            stderr=subprocess.STDOUT, cwd=t2.REPO,
        )  # fmt: skip
    return processes


def joined(build_id: str, queues: tuple[str, ...]) -> dict:
    """Wait until the build's version lists every queue; keep that describe-version output."""
    for _ in range(240):
        code, out = temporal(f"describe-version-{build_id}", "worker", "deployment",
                             "describe-version", "--deployment-name", DEPLOYMENT, "--build-id",
                             build_id, "-o", "json", check=False)  # fmt: skip
        if code == 0 and set(queues) <= {q["name"] for q in json.loads(out)["taskQueuesInfos"]}:
            return json.loads(out)
        STEP["n"] -= 1  # keep only the describe that shows every queue
        time.sleep(0.5)
    raise SystemExit(f"build {build_id} did not join {queues}")


def start(bucket: str, start_input: dict, builds: dict, wait: bool = True) -> subprocess.Popen:
    """The dispatcher stand-in: start-request with the map; returns the process."""
    path = t2.LOGS / f"{start_input['request_id']}.json"
    path.write_text(json.dumps(start_input))
    builds_path = t2.LOGS / f"builds-{start_input['request_id']}.yaml"
    builds_path.write_text(yaml.safe_dump(builds))
    return subprocess.Popen(
        [*t2.CLI, "start-request", str(path), "--builds", str(builds_path),
         *(["--wait"] if wait else [])],
        env=t2.env(bucket), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        cwd=t2.REPO,
    )  # fmt: skip


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


async def case(client, store, bucket, start_input, builds, pids, uid) -> dict:
    """Run one request through the dispatcher stand-in; what it sent, ran and added."""
    before = set(await store.list_prefix(f"documents/{uid}/"))
    calls = Counter(CALLS)
    begin = time.monotonic()
    process = start(bucket, start_input, builds)
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
    versioning = (json.loads(described).get("workflowExecutionInfo", {})
                  .get("versioningInfo") if described.startswith("{") else None)  # fmt: skip
    (t2.LOGS / f"result-{request_id}.json").write_text(json.dumps(result, indent=2))
    enrichments = result.get("enrichments", [])
    return {
        "request_id": request_id,
        "exit": code,
        "output": redact(output.strip().splitlines()[-1]) if output.strip() else "",
        "seconds": round(time.monotonic() - begin, 1),
        "outcome": result.get("outcome") or result["kind"],
        "reason": (result.get("error") or {}).get("reason"),
        "category": ((result.get("error") or {}).get("metadata") or {}).get("category"),
        "build_id": result.get("profile", {}).get("runtime_identity", {}).get("build_id"),
        "profile": result.get("profile", {}).get("id"),
        "profile_methods": {f"{m['id']}@{m['version']}": m["module_digest"]
                            for m in result.get("profile", {}).get("methods", [])},
        "versioning_info": versioning,
        "stand_in_calls": dict(CALLS - calls),
        "receipts": dict(Counter(r["method"] for r in await t4.receipts(store, request_id))),
        "activity_builds": sorted({a["build"] for a in ran}),
        "activities": dict(Counter(a["activity"] for a in ran)),
        "fresh_activities": sorted({a["activity"] for a in ran
                                    if a["reused"] and not all(a["reused"])}),
        "enrichments": len(enrichments),
        "enrichments_reused": sum(e["reused"] for e in enrichments),
        "item_folders_added": len({k.split("/")[3] for k in added if "/items/" in k}),
        "objects_added_outside_items": sum("/items/" not in k for k in added),
    }  # fmt: skip


def all_reused(c: dict) -> bool:
    """Nothing was computed: no inference request and no fresh Activity or registered item."""
    return (
        c["outcome"] == "complete" and c["stand_in_calls"] == {} and c["receipts"] == {}
        and c["fresh_activities"] == [] and c["activities"].get("parse_group", 0) > 0
        and c["enrichments_reused"] == c["enrichments"] > 0
        and c["item_folders_added"] == c["objects_added_outside_items"] == 0
    )  # fmt: skip


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

    dev = yaml.safe_load(Path(t2.PROFILE).read_text())
    profile_b = t2.LOGS / "paper-pdf-dev@2.yaml"
    profile_b.write_text(yaml.safe_dump({**dev, "profile": "paper-pdf@2"}, sort_keys=False))
    del dev["methods"][CHECK]
    profile_a = t2.LOGS / "paper-pdf-dev@1.yaml"
    profile_a.write_text(yaml.safe_dump(dev, sort_keys=False))

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

    def up(build_id: str, profile: Path, queues: tuple[str, ...]) -> None:
        builds[build_id] = build(bucket, build_id, profile, queues)
        pids.update({p.pid: build_id for p in builds[build_id].values()})

    def request(name: str, **overrides) -> dict:
        return t2.start_input(sha, data, bucket, f"req_{t2.RUN}_{name}", **overrides)

    try:
        client = None
        for _ in range(60):
            try:
                client = await Client.connect(t2.TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        assert client is not None

        # 1. the first build
        up("paper-pdf-1-r1", profile_a, QUEUES_A)
        early = start(bucket, request("early"), {"paper-pdf@1": "paper-pdf-1-r1"}, wait=False)
        early_out = early.communicate()[0]
        joined_r1 = joined("paper-pdf-1-r1", QUEUES_A)
        temporal("set-current-1-r1", "worker", "deployment", "set-current-version",
                 "--deployment-name", DEPLOYMENT, "--build-id", "paper-pdf-1-r1", "--yes")  # fmt: skip
        temporal("describe-deployment-1", "worker", "deployment", "describe", "--name",
                 DEPLOYMENT, "-o", "json")  # fmt: skip
        evidence["1"] = {
            "early_start": {"exit": early.returncode,
                            "error": redact(early_out.strip().splitlines()[-1])},
            "task_queues": sorted({q["name"] for q in joined_r1["taskQueuesInfos"]}),
        }  # fmt: skip
        evidence["1"]["pass"] = (
            early.returncode != 0 and "is not present in task queue" in early_out
            and evidence["1"]["task_queues"] == sorted(QUEUES_A)
        )  # fmt: skip

        # 2. pinned start, the first processing
        old_map = {"paper-pdf@1": "paper-pdf-1-r1"}
        r1 = evidence["2"] = await case(client, store, bucket, request("r1"), old_map, pids, uid)
        r1["pass"] = (
            r1["outcome"] == "complete" and r1["build_id"] == "paper-pdf-1-r1"
            and r1["activity_builds"] == ["paper-pdf-1-r1"]
            and r1["stand_in_calls"].get("vlm", 0) > 0 and r1["item_folders_added"] > 0
        )  # fmt: skip

        # 3. resubmission and redrive
        r2 = await case(client, store, bucket,
                        request("r2", source_revision_id="srv_2"), old_map, pids, uid)  # fmt: skip
        r3 = await case(client, store, bucket, request("r3", initiator="operator"), old_map, pids,
                        uid)  # fmt: skip
        evidence["3"] = {"resubmission": r2, "redrive": r3,
                         "pass": all_reused(r2) and all_reused(r3)}  # fmt: skip

        # 4. a patch build beside the current one
        up("paper-pdf-1-r2", profile_a, QUEUES_A)
        joined("paper-pdf-1-r2", QUEUES_A)
        new_map = {"paper-pdf@1": "paper-pdf-1-r2"}
        before = set(await store.list_prefix(f"documents/{uid}/"))
        calls, begin = Counter(CALLS), time.monotonic()
        both = [(request("r4"), start(bucket, request("r4"), new_map)),
                (request("r5"), start(bucket, request("r5"), old_map))]  # fmt: skip
        outputs = [(s, p.communicate()[0], p.returncode) for s, p in both]
        r4, r5 = [await observe(client, store, s, code, out, before, calls, begin, pids, uid)
                  for s, out, code in outputs]  # fmt: skip
        _, deployment = temporal("describe-deployment-2", "worker", "deployment", "describe",
                                 "--name", DEPLOYMENT, "-o", "json")  # fmt: skip
        evidence["4"] = {"r4": r4, "r5": r5}
        evidence["4"]["pass"] = (
            r4["build_id"] == "paper-pdf-1-r2" and r4["activity_builds"] == ["paper-pdf-1-r2"]
            and r5["build_id"] == "paper-pdf-1-r1" and r5["activity_builds"] == ["paper-pdf-1-r1"]
            and all_reused(r4) and all_reused(r5)
            and json.loads(deployment)["routingConfig"]["currentVersionBuildID"] == "paper-pdf-1-r1"
        )  # fmt: skip

        # 5. retire 1-r1
        temporal("set-current-1-r2", "worker", "deployment", "set-current-version",
                 "--deployment-name", DEPLOYMENT, "--build-id", "paper-pdf-1-r2", "--yes")  # fmt: skip
        stop([builds["paper-pdf-1-r1"].pop("inference")])
        r6_start = request("r6")
        r6_calls, r6_begin = Counter(CALLS), time.monotonic()
        r6_before = set(await store.list_prefix(f"documents/{uid}/"))
        r6 = start(bucket, r6_start, old_map)
        await asyncio.sleep(8)  # several drainage refreshes and visibility grace periods
        query = (f'TemporalWorkerDeploymentVersion="{DEPLOYMENT}:paper-pdf-1-r1" '
                 'AND ExecutionStatus="Running"')  # fmt: skip
        _, open_count = temporal("count-open-1-r1-while-r6", "workflow", "count", "--query",
                                 query, "-o", "json")  # fmt: skip
        _, draining = temporal("describe-version-1-r1-while-r6", "worker", "deployment",
                               "describe-version", "--deployment-name", DEPLOYMENT,
                               "--build-id", "paper-pdf-1-r1", "-o", "json")  # fmt: skip
        restarted = build(bucket, "paper-pdf-1-r1", profile_a, ("inference",))
        builds["paper-pdf-1-r1"] |= restarted
        pids.update({p.pid: "paper-pdf-1-r1" for p in restarted.values()})
        r6_out = r6.communicate()[0]
        r6_done = await observe(client, store, r6_start, r6.returncode, r6_out, r6_before,
                                r6_calls, r6_begin, pids, uid)  # fmt: skip
        await asyncio.sleep(4)
        _, closed_count = temporal("count-open-1-r1-after-r6", "workflow", "count", "--query",
                                   query, "-o", "json")  # fmt: skip
        _, drained = temporal("describe-version-1-r1-after-r6", "worker", "deployment",
                              "describe-version", "--deployment-name", DEPLOYMENT,
                              "--build-id", "paper-pdf-1-r1", "-o", "json")  # fmt: skip
        stop(builds.pop("paper-pdf-1-r1").values())
        deleted = None
        for attempt in range(60):
            code, out = temporal("delete-version-1-r1", "worker", "deployment", "delete-version",
                                 "--deployment-name", DEPLOYMENT, "--build-id", "paper-pdf-1-r1",
                                 check=False)  # fmt: skip
            if code == 0:
                deleted = {"attempts": attempt + 1, "output": out.strip()}
                break
            STEP["n"] -= 1 if attempt else 0  # keep the first refusal and the success
            await asyncio.sleep(2)
        temporal("describe-deployment-3", "worker", "deployment", "describe", "--name",
                 DEPLOYMENT, "-o", "json")  # fmt: skip
        evidence["5"] = {
            "open_while_r6": int(json.loads(open_count).get("count", 0)),
            "drainage_while_r6": json.loads(draining)["drainageInfo"]["drainageStatus"],
            "r6": r6_done,
            "open_after_r6": int(json.loads(closed_count).get("count", 0)),
            "drainage_after_r6": json.loads(drained)["drainageInfo"]["drainageStatus"],
            "deleted": deleted,
        }
        evidence["5"]["pass"] = (
            evidence["5"]["open_while_r6"] == 1 and evidence["5"]["open_after_r6"] == 0
            and r6_done["build_id"] == "paper-pdf-1-r1" and all_reused(r6_done)
            and deleted is not None
        )  # fmt: skip

        # 6. a profile that adds a method, and a map that names the wrong build
        up("paper-pdf-2-r1", profile_b, QUEUES_B)
        joined("paper-pdf-2-r1", QUEUES_B)
        wrong = {"paper-pdf@1": "paper-pdf-2-r1"}
        r7 = evidence["6"] = await case(client, store, bucket, request("r7"), wrong, pids, uid)
        r7["pass"] = (
            r7["outcome"] == "failure" and r7["category"] == "integrity"
            and r7["reason"] == "ADOPTED_VERSION_MISMATCH" and r7["stand_in_calls"] == {}
            and r7["item_folders_added"] == 0
        )  # fmt: skip

        # 7. the refresh under paper-pdf@2
        both_maps = {"paper-pdf@1": "paper-pdf-1-r2", "paper-pdf@2": "paper-pdf-2-r1"}
        r8 = evidence["7"] = await case(
            client, store, bucket,
            request("r8", adopted_version="paper-pdf@2", adoption_sequence=2, initiator="operator"),
            both_maps, pids, uid,
        )  # fmt: skip
        temporal("set-current-2-r1", "worker", "deployment", "set-current-version",
                 "--deployment-name", DEPLOYMENT, "--build-id", "paper-pdf-2-r1", "--yes")  # fmt: skip
        temporal("describe-deployment-4", "worker", "deployment", "describe", "--name",
                 DEPLOYMENT, "-o", "json")  # fmt: skip
        checks = r8["receipts"].get(CHECK, 0)
        r8["pass"] = (
            r8["outcome"] == "complete" and r8["build_id"] == "paper-pdf-2-r1"
            and r8["profile"] == "paper-pdf@2" and CHECK in r8["profile_methods"]
            and r8["stand_in_calls"] == {"d3": checks} and checks > 0
            and r8["receipts"] == {CHECK: checks} and r8["item_folders_added"] == checks
            and r8["objects_added_outside_items"] == 0
            and r8["fresh_activities"] == ["check"]
            and r8["enrichments_reused"] == r8["enrichments"] > 0
        )  # fmt: skip
    finally:
        stop([p for b in builds.values() for p in b.values()])
        stop([admission, server])
        for s in servers:
            s.shutdown()

    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    failed = [step for step, value in evidence.items() if isinstance(value, dict)
              and "pass" in value and not value["pass"]]  # fmt: skip
    print("failed:", failed or "none", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 8)))
