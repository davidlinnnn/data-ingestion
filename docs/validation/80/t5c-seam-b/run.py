"""Seam B for #161: the d3 Quality Check in the real stack, d3-mini served by the model package's
d3_server.py on MPS with one request per forward.

    scripts/heavy-lock t5c-seam-b -- env HF_HUB_OFFLINE=1 .venv/bin/python \\
        docs/validation/80/t5c-seam-b/run.py CORPUS_MANIFEST D3_PACKAGE D3_PYTHON \\
        [--against-153 R153_DIR] [--switch INDEX BEFORE_TREE] [INDEX ...]

D3_PACKAGE is the d3-mini model package (d3_server.py beside the weights) and D3_PYTHON the
python of its runtime; both live outside git. The server asks for a bearer key made for the run.

Ports of its own (Temporal 7294/7295, fake_admission 8131, VLM stand-in 8132, summary stand-in
8133, d3 server 8134; S3 stand-in on 9100); it refuses to start when any is taken.

No request leaves the machine. The VLM stand-in replays the gpt-6-luna responses recorded for
the corpus (tests/fixtures/vlm, named by the request's params_digest) and gives the canned
answer to a request without one; the summary stand-in is the DEV fake (tests/summary.py).

Cases:
  A  (--against-153) against_153.py with the server: #153's formula and ocr test items through
     SystemOne and the package, scores compared with #153's
  W  (--switch INDEX BEFORE_TREE) one paper, one bucket, three requests:
       before  the code and DEV profile under BEFORE_TREE, the tree this branch started from
       off     this code, the DEV profile without d3-check, no d3 worker, no KP_D3_* variable:
               nothing new under documents/, no request, and the result equals before's
               (sha256 of the result without request_id and the reused flags)
       on      this code, the DEV profile, the d3 worker: every enrichment reused, only d3
               requests, only the check items new under documents/, and the result differs
               from off's by the d3 signals and what a d3 contradiction changes
     and `worker --queue d3` without KP_D3_BASE_URL exits 2 naming the variable
  S  each INDEX in a fresh bucket: the document completes; every formula, table-status and
     picture-ocr item whose outcome is success carries a d3 score; one ok d3 request per check
     item
  C  a second request for the same document: no request, every check outcome reused, nothing
     new under documents/

evidence-INDEX.json and evidence-switch.json keep counts, timings, scores and statuses only: the
papers are third-party.
"""

import asyncio
import hashlib
import importlib.util
import json
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import yaml
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
sys.path.insert(0, str(HERE))
import against_153  # noqa: E402

from kp_processing.identity import canonical_json  # noqa: E402
from tests import summary as dev_summary  # noqa: E402
from tests.vlm import canned, schema_name  # noqa: E402

TEMPORAL_PORT, ADMISSION_PORT, VLM_PORT, SUMMARY_PORT, D3_PORT = 7294, 8131, 8132, 8133, 8134
t2.TEMPORAL, t2.ADMISSION = f"127.0.0.1:{TEMPORAL_PORT}", f"http://127.0.0.1:{ADMISSION_PORT}"
t2.BASE_ENV.update(TEMPORAL_ADDRESS=t2.TEMPORAL, KP_ADMISSION_URL=t2.ADMISSION)
CHECK = "d3-check@1"
JUDGED = ("picture-ocr", "formula", "table-status")
REPLAYED: Counter = Counter()  # "<schema> replayed" and "<schema> canned" VLM answers


class StandIn(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = self.answer(json.loads(self.rfile.read(int(self.headers["content-length"]))))
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def answer(self, request: dict) -> bytes:
        raise NotImplementedError

    def log_message(self, *args) -> None:
        pass


class Replay(StandIn):
    """An OpenAI-compatible endpoint answering a request with the response recorded for it,
    else with tests.vlm's canned answer for its schema."""

    def answer(self, request: dict) -> bytes:
        name = schema_name(request)
        params = {k: v for k, v in request.items() if k != "model"}  # OpenAIChat adds the model
        digest = hashlib.sha256(canonical_json(params)).hexdigest()
        fixture = t4.FIXTURES / name / f"{digest}.json"
        REPLAYED[f"{name} {'replayed' if fixture.exists() else 'canned'}"] += 1
        return fixture.read_bytes() if fixture.exists() else canned(request).body


class Summary(StandIn):
    def answer(self, request: dict) -> bytes:
        return dev_summary.reply(dev_summary.answer(request)).body


def worker(bucket: str, name: str, queue: str, profile: Path, extra: dict,
           tree: Path | None = None) -> subprocess.Popen:  # fmt: skip
    """A worker of this code, or of the code under tree/src."""
    log = open(t2.LOGS / f"worker-{name}-{queue}.log", "w")
    env = {**t2.env(bucket), **extra}
    cli = t2.CLI
    if tree is not None:
        cli = [str(t2.REPO / ".venv/bin/python"), "-m", "kp_processing.cli"]
        env["PYTHONPATH"] = str(tree / "src")
    return subprocess.Popen(
        [*cli, "worker", "--queue", queue, "--profile", str(profile), "--build-id", "seamb-r1"],
        env=env, stdout=log, stderr=subprocess.STDOUT, cwd=t2.REPO,
    )  # fmt: skip


def stack(bucket: str, name: str, profile: Path, d3: dict | None,
          tree: Path | None = None) -> list[subprocess.Popen]:  # fmt: skip
    """One worker per task queue; the d3 one only when given its variables."""
    queues = {
        "orchestration": {},
        "inference": {},
        "vlm": {"KP_VLM_BASE_URL": f"http://127.0.0.1:{VLM_PORT}/v1", "KP_VLM_API_KEY": "none"},
        "summary": {"KP_SUMMARY_BASE_URL": f"http://127.0.0.1:{SUMMARY_PORT}/v1",
                    "KP_SUMMARY_API_KEY": "none"},
    }  # fmt: skip
    if d3:
        queues["d3"] = d3
    return [worker(bucket, name, queue, profile, extra, tree) for queue, extra in queues.items()]


def stop(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        process.terminate()
        process.wait()


def wait_for_d3(server: subprocess.Popen, key: str) -> dict:
    """The server's health and model listing, once it has loaded the model and warmed up."""
    root = f"http://127.0.0.1:{D3_PORT}"
    for _ in range(900):
        if server.poll() is not None:
            raise SystemExit(f"d3 server exited; see {t2.LOGS / 'd3-server.log'}")
        try:
            with urllib.request.urlopen(f"{root}/health", timeout=2) as r:
                health = json.loads(r.read())
            models = urllib.request.Request(
                f"{root}/v1/models", headers={"authorization": f"Bearer {key}"}
            )
            with urllib.request.urlopen(models, timeout=10) as r:
                return {"health": health, **json.loads(r.read())}
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError:  # not listening yet
            time.sleep(1)
    raise SystemExit("d3 server not ready after 900 s")


async def check_activity(client: Client, request_id: str) -> dict | None:
    """The check Activity in the workflow history: seconds it waited and ran, its outcomes and
    how many of them were reused."""
    history = await client.get_workflow_handle(request_id).fetch_history()
    scheduled, started = {}, {}
    for event in history.events:
        at = event.event_time.ToDatetime(UTC)
        if event.HasField("activity_task_scheduled_event_attributes"):
            if event.activity_task_scheduled_event_attributes.activity_type.name == "check":
                scheduled[event.event_id] = at
        elif event.HasField("activity_task_started_event_attributes"):
            started[event.activity_task_started_event_attributes.scheduled_event_id] = at
        elif event.HasField("activity_task_completed_event_attributes"):
            done = event.activity_task_completed_event_attributes
            if done.scheduled_event_id in scheduled:
                begin = started[done.scheduled_event_id]
                outcomes = json.loads(done.result.payloads[0].data)
                waited = (begin - scheduled[done.scheduled_event_id]).total_seconds()
                return {"waited_s": round(waited, 1),
                        "seconds": round((at - begin).total_seconds(), 1),
                        "outcomes": len(outcomes),
                        "reused": sum(o["reused"] for o in outcomes)}  # fmt: skip
    return None


def flagged(enrichment: dict) -> bool:
    """Whether d3 contradicts the enrichment: a strong signal at or below its threshold."""
    signal = enrichment["signals"].get("d3", {})
    return signal.get("t_d") is not None and signal["p"] <= signal["t_d"]


async def judged(store, result: dict) -> tuple[dict, list]:
    """Per judged method: its items, those whose outcome is success, how d3 judged them, and the
    disputed ones per status reason. Then one row per judged item, without content."""
    methods = {m: {"items": 0, "success": 0, "scored": 0, "not_run": 0, "unjudged": 0,
                   "judged_without_success": 0, "d3_flagged": 0, "disputed": {}}
               for m in JUDGED}  # fmt: skip
    rows = []
    for e in result["enrichments"]:
        m = methods.get(e["method_ref"]["id"])
        if m is None:
            continue
        signal = e["signals"].get("d3")
        outcome = json.loads(await store.get(e["result_ref"]))["outcome"]
        m["items"] += 1
        if e["status"] == "disputed":
            m["disputed"][e["status_reason"]] = m["disputed"].get(e["status_reason"], 0) + 1
        if outcome != "success":
            m["judged_without_success"] += signal is not None
        else:
            m["success"] += 1
            m["unjudged"] += signal is None
            m["not_run"] += signal is not None and "state" in signal
            m["scored"] += signal is not None and "score" in signal
            m["d3_flagged"] += flagged(e)
        rows.append([e["item_id"], outcome, e["status"], e["status_reason"],
                     (signal or {}).get("score"), (signal or {}).get("p")])  # fmt: skip
    return methods, rows


def d3_receipts(sent: list[dict]) -> dict:
    summary = t4.receipt_summary(sent)
    del summary["tokens"]  # System One counts input_tokens and output_tokens
    return summary | {"input_tokens": sum((r.get("usage") or {}).get("input_tokens", 0)
                                          for r in sent)}  # fmt: skip


async def run_s(client: Client, bucket: str, sha: str, data: bytes, request_id: str) -> dict:
    answered = Counter(REPLAYED)
    code, result, seconds = await t4.run_case(bucket, sha, data, request_id)
    evidence: dict = {"exit": code, "seconds": seconds}
    if code != 0:
        return evidence
    store = t2.store(bucket)
    sent = [r for r in await t4.receipts(store, request_id) if r["method"] == CHECK]
    methods, rows = await judged(store, result)
    evidence |= {"outcome": result["outcome"], "judged": methods, "d3_receipts": d3_receipts(sent),
                 "check": await check_activity(client, request_id),
                 "vlm_answers": dict(REPLAYED - answered), "statuses": t4.per_method(result),
                 "judgements": rows}  # fmt: skip
    checks = sum(m["scored"] for m in methods.values())
    receipts = evidence["d3_receipts"]
    evidence["pass"] = (
        result["outcome"] == "complete"
        and all(m["unjudged"] == m["not_run"] == m["judged_without_success"] == 0
                for m in methods.values())
        and receipts["requests"] == receipts["results"]["ok"] == checks
        and receipts["incomplete"] == 0
        and evidence["check"] is not None
        and evidence["check"]["outcomes"] == checks
        and evidence["check"]["reused"] == 0
    )  # fmt: skip
    return evidence


async def run_c(client: Client, bucket: str, sha: str, data: bytes, request_id: str,
                checks: int) -> dict:  # fmt: skip
    store = t2.store(bucket)
    before = set(await store.list_prefix(f"documents/doc_{sha[:16]}/"))
    code, _, seconds = await t4.run_case(bucket, sha, data, request_id)
    added = set(await store.list_prefix(f"documents/doc_{sha[:16]}/")) - before
    evidence = {"exit": code, "seconds": seconds,
                "external_receipts": len(await t4.receipts(store, request_id)),
                "objects_added_under_documents": len(added),
                "check": await check_activity(client, request_id) if code == 0 else None}  # fmt: skip
    evidence["pass"] = (
        code == 0 and evidence["external_receipts"] == 0 and not added
        and evidence["check"] is not None
        and evidence["check"]["outcomes"] == evidence["check"]["reused"] == checks
    )  # fmt: skip
    return evidence


def comparable(result: dict) -> dict:
    """The result without what a new request for the same document changes."""
    request = {k: v for k, v in result["request"].items() if k != "request_id"}
    enrichments = [{k: v for k, v in e.items() if k != "reused"} for e in result["enrichments"]]
    return {**result, "request": request, "enrichments": enrichments}


def digest(value: dict) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def beyond_d3(off: dict, on: dict) -> list[str]:
    """The item_ids whose enrichment in on differs from off's by more than the d3 signal and,
    for an item d3 contradicts, its status."""
    differing = []
    for before, after in zip(off["enrichments"], on["enrichments"], strict=True):
        ignored = {"reused", "status", "status_reason"} if flagged(after) else {"reused"}
        signals = {k: v for k, v in after["signals"].items() if k != "d3"}
        if {k: v for k, v in {**after, "signals": signals}.items() if k not in ignored} != {
            k: v for k, v in before.items() if k not in ignored
        }:
            differing.append(after["item_id"])
    return differing


async def run_switch(client: Client, paper: dict, sha: str, data: bytes, tree: Path,
                     d3_env: dict) -> dict:  # fmt: skip
    bucket, uid = f"seamb-{t2.RUN}-t5c-sw", f"doc_{sha[:16]}"
    store = t2.store(bucket)
    await store.put_if_absent(f"custody/{sha}", data)
    on = Path(t2.PROFILE)
    profile = yaml.safe_load(on.read_text())
    del profile["methods"][CHECK]
    off = t2.LOGS / "paper-pdf-dev-off.yaml"
    off.write_text(yaml.safe_dump(profile, sort_keys=False))
    evidence: dict = {"run": t2.RUN, "paper": {k: paper[k] for k in ("index", "sha256", "pages")}}

    async def case(name: str, workers: list[subprocess.Popen]) -> tuple[dict, dict]:
        before = set(await store.list_prefix(f"documents/{uid}/"))
        request_id = f"req_{t2.RUN}_sw_{name}"
        try:
            code, result, seconds = await t4.run_case(bucket, sha, data, request_id)
        finally:
            stop(workers)
        added = set(await store.list_prefix(f"documents/{uid}/")) - before
        sent = await t4.receipts(store, request_id)
        evidence[name] = {
            "exit": code, "seconds": seconds,
            "receipts_per_method": dict(Counter(r["method"] for r in sent)),
            "objects_added_under_documents": len(added),
            "item_folders_added": len({k.split("/")[3] for k in added if "/items/" in k}),
            "enrichments": len(result.get("enrichments", [])),
            "enrichments_reused": sum(e["reused"] for e in result.get("enrichments", [])),
            "result_sha256": digest(comparable(result)) if result else None,
            "check": await check_activity(client, request_id) if code == 0 else None,
            "profile_methods": [f"{m['id']}@{m['version']}"
                                for m in result.get("profile", {}).get("methods", [])],
        }  # fmt: skip
        return evidence[name], result

    before, _ = await case("before", stack(bucket, "before", tree / "tests/profiles/paper-pdf-dev.yaml", None, tree))  # fmt: skip
    off_case, off_result = await case("off", stack(bucket, "off", off, None))
    refused = subprocess.run(
        [*t2.CLI, "worker", "--queue", "d3", "--profile", str(on)], capture_output=True,
        text=True, cwd=t2.REPO,
        env={k: v for k, v in t2.env(bucket).items() if not k.startswith("KP_D3_")},
    )  # fmt: skip
    evidence["d3_worker_without_url"] = {"exit": refused.returncode,
                                         "stderr": refused.stderr.strip()}  # fmt: skip
    on_case, on_result = await case("on", stack(bucket, "on", on, d3_env))
    methods, _ = await judged(store, on_result) if on_result else ({}, [])
    checks = sum(m["scored"] for m in methods.values())
    evidence["on"] |= {"judged": methods,
                       "differs_from_off_beyond_d3": beyond_d3(off_result, on_result)
                       if off_result and on_result else None,
                       "same_inventory_as_off": bool(on_result) and bool(off_result)
                       and on_result["inventory"]["ref"] == off_result["inventory"]["ref"]}  # fmt: skip
    evidence["pass"] = (
        before["exit"] == off_case["exit"] == on_case["exit"] == 0
        and CHECK not in before["profile_methods"] and CHECK not in off_case["profile_methods"]
        and off_case["result_sha256"] == before["result_sha256"]
        and off_case["objects_added_under_documents"] == 0
        and off_case["receipts_per_method"] == {} and off_case["check"] is None
        and evidence["d3_worker_without_url"] == {
            "exit": 2, "stderr": "KP_D3_BASE_URL is required for the d3 worker"}
        and CHECK in on_case["profile_methods"]
        and on_case["enrichments_reused"] == on_case["enrichments"] > 0
        and on_case["receipts_per_method"] == {CHECK: checks} and checks > 0
        and on_case["item_folders_added"] == checks
        and on_case["check"] is not None and on_case["check"]["reused"] == 0
        and evidence["on"]["differs_from_off_beyond_d3"] == []
        and evidence["on"]["same_inventory_as_off"]
    )  # fmt: skip
    return evidence


async def main(argv: list[str]) -> int:
    manifest, package, python = Path(argv[0]), Path(argv[1]), argv[2]
    rest = argv[3:]
    r153 = switch = None
    if rest[:1] == ["--against-153"]:
        r153, rest = rest[1], rest[2:]
    if rest[:1] == ["--switch"]:
        switch, rest = (int(rest[1]), Path(rest[2])), rest[3:]
    indices = [int(i) for i in rest]
    ports = (TEMPORAL_PORT, TEMPORAL_PORT + 1, ADMISSION_PORT, VLM_PORT, SUMMARY_PORT, D3_PORT)
    if busy := [port for port in ports if t5.taken(port)]:
        raise SystemExit(f"ports already in use: {busy}")
    t2.LOGS.mkdir(parents=True)
    papers = {p["index"]: p for p in json.loads(manifest.read_text())["papers"]}

    def load_paper(index: int) -> tuple[dict, str, bytes]:
        paper = papers[index]
        data = (manifest.parent / paper["file"]).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        assert sha == paper["sha256"], "paper does not match the corpus manifest"
        return paper, sha, data

    # The children hold the heavy lock: end them when this process is told to stop.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    key = secrets.token_hex(16)
    d3_url = f"http://127.0.0.1:{D3_PORT}"
    d3_env = {"KP_D3_BASE_URL": d3_url, "KP_D3_API_KEY": key}
    command = ["d3_server.py", "--device", "mps", "--batch-size", "1", "--port", str(D3_PORT)]
    d3 = subprocess.Popen(
        [python, str(package / command[0]), *command[1:]],
        env={**os.environ, "DECISION_API_KEY": key, "HF_HUB_OFFLINE": "1",
             "TRANSFORMERS_OFFLINE": "1", "PYTORCH_ENABLE_MPS_FALLBACK": "0"},
        stdout=open(t2.LOGS / "d3-server.log", "w"), stderr=subprocess.STDOUT,
    )  # fmt: skip
    temporal = subprocess.Popen(
        ["temporal", "server", "start-dev", "--headless", "--port", str(TEMPORAL_PORT),
         "--ui-port", str(TEMPORAL_PORT + 1), "--db-filename", str(t2.LOGS / "temporal.db"),
         "--log-level", "warn", *t2.SEARCH_ATTRIBUTE_FLAGS],
        stdout=open(t2.LOGS / "temporal.log", "w"), stderr=subprocess.STDOUT,
    )  # fmt: skip
    admission = subprocess.Popen(
        [str(t2.REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server",
         "--port", str(ADMISSION_PORT), "--log", str(t2.LOGS / "reports.jsonl")], cwd=t2.REPO,
    )  # fmt: skip
    servers = [t5.stand_in(Replay, VLM_PORT), t5.stand_in(Summary, SUMMARY_PORT)]
    workers: list[subprocess.Popen] = []
    failures = []
    try:
        service = {"command": command, "serves": wait_for_d3(d3, key)}
        print("d3 server ready", json.dumps(service["serves"]), flush=True)
        client = None
        for _ in range(60):
            try:
                client = await Client.connect(t2.TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        assert client is not None

        if r153:
            code = await against_153.main([r153, d3_url, key])
            failures += ["A"] if code else []
        if switch:
            paper, sha, data = load_paper(switch[0])
            evidence = await run_switch(client, paper, sha, data, switch[1], d3_env)
            evidence["d3_server"] = service
            (HERE / "evidence-switch.json").write_text(json.dumps(evidence, indent=2) + "\n")
            print("W", json.dumps({k: v for k, v in evidence.items() if k != "d3_server"}),
                  flush=True)  # fmt: skip
            failures += [] if evidence["pass"] else ["W"]
        for index in indices:
            paper, sha, data = load_paper(index)
            bucket = f"seamb-{t2.RUN}-t5c-{index}"
            await t2.store(bucket).put_if_absent(f"custody/{sha}", data)
            workers = stack(bucket, f"p{index}", Path(t2.PROFILE), d3_env)
            evidence = {"run": t2.RUN, "d3_server": service,
                        "paper": {k: paper[k] for k in ("index", "sha256", "pages")}}  # fmt: skip
            s = evidence["S"] = await run_s(client, bucket, sha, data, f"req_{t2.RUN}_s{index}")
            if s["exit"] == 0:
                checks = sum(m["scored"] for m in s["judged"].values())
                evidence["C"] = await run_c(client, bucket, sha, data, f"req_{t2.RUN}_c{index}",
                                            checks)  # fmt: skip
            stop(workers)
            workers = []
            (HERE / f"evidence-{index}.json").write_text(json.dumps(evidence, indent=2) + "\n")
            print(index, json.dumps({c: {k: evidence[c].get(k) for k in
                                         ("pass", "seconds", "judged", "check", "vlm_answers")}
                                     for c in ("S", "C") if c in evidence}), flush=True)  # fmt: skip
            failures += [f"{c}{index}" for c in ("S", "C")
                         if not evidence.get(c, {}).get("pass")]  # fmt: skip
    finally:
        stop([*workers, admission, temporal, d3])
        for server in servers:
            server.shutdown()
    print("failed:", failures or "none", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
