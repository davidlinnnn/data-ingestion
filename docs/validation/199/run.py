"""#199: paper-pdf@1 end to end on the Temporal workflow, every paper with the real DEV models,
then its enrichments scored against the gold and its requests and tokens tabled.

    set -a; . ~/.config/kp-dev/anthropic.env; set +a
    scripts/heavy-lock 199-e2e -- env HF_HUB_OFFLINE=1 .venv/bin/python \\
        docs/validation/199/run.py OUT CORPUS_MANIFEST ARCHIVE D3_PACKAGE D3_PYTHON INDEX...

OUT (outside the repo) keeps the S3 stand-in's data, the Temporal database, the logs, each
summary's text and the judging sheets. ARCHIVE is the untracked tree with the #84 gold and the
W2 paper; INDEX is a corpus index or `w2`. D3_PACKAGE is the d3-mini model package
(d3_server.py beside the weights), D3_PYTHON the python of its runtime; both outside git.

Ports of its own: S3 stand-in 9199 (RustFS, the image of tests/s3/compose.yaml, data under
OUT/s3), Temporal 7314/7315, fake_admission 8161, VLM stand-in 8162, summary stand-in 8163,
d3 server 8164. It refuses to start when any is taken.

The workers load paper-pdf@1.yaml with two changes, asserted: the components of the methods that
call a company service are the DEV profile's (anthropic/claude-sonnet-5-5 for the summary,
d3-mini on d3_server.py) but for the VLM methods, which use VLM_COMPONENT, and RELAXED. Each
paper is started with start-request, admission's start, on one bucket for the run, one paper at
a time. The corpus papers call Sonnet 5.5 through Anthropic's OpenAI-compatible endpoint, for
the VLM methods and the summary alike; `w2` is not a corpus paper (#129: only those may be
sent), so it runs with the VLM stand-in (t5c's replay of the recordings) and the DEV summary
fake. Before any corpus paper starts, the API key is checked on the models endpoint (free).

A paper already in OUT/requests.json is not run again, so a scorer change reruns only the
scoring: without a paper to run, no stack but the S3 stand-in starts. Writes papers/INDEX.json
(counts, statuses, timings, receipts without content), tokens.json and tokens.md for the corpus
papers run, and accuracy.json (score.py), after the VLM methods ran alone on t4's targets of
the corpus papers run (score.alone_answers; needs t4-seam-b's runs on the S3 stand-in of
tests/s3/compose.yaml, port 9100). The run stops starting papers once the requests'
tokens priced at PRICE_PER_MTOK reach STOP_AT_USD, and at once when a provider refuses the
credentials (a broken environment, not a finding about the paper).
"""

import asyncio
import copy
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
from pathlib import Path

import httpx
import yaml
from temporalio.client import Client

from kp_canonicalization.ports.inference import OpenAIChat

HERE = Path(__file__).resolve().parent
V80 = HERE.parent / "80"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


t5c = load("t5c", V80 / "t5c-seam-b/run.py")
t5, t4, t2 = t5c.t5, t5c.t4, t5c.t2
t5b = load("t5b_seam_b", V80 / "t5b-seam-b/run.py")
sys.path.insert(0, str(HERE))
import score  # noqa: E402
import tokens  # noqa: E402

S3_PORT, TEMPORAL_PORT, ADMISSION_PORT, VLM_PORT, SUMMARY_PORT, D3_PORT = (
    9199, 7314, 8161, 8162, 8163, 8164)  # fmt: skip
t2.TEMPORAL, t2.ADMISSION = f"127.0.0.1:{TEMPORAL_PORT}", f"http://127.0.0.1:{ADMISSION_PORT}"
t5c.D3_PORT = D3_PORT  # wait_for_d3 reads it
t2.BASE_ENV.update(TEMPORAL_ADDRESS=t2.TEMPORAL, KP_ADMISSION_URL=t2.ADMISSION,
                   KP_S3_ENDPOINT=f"http://127.0.0.1:{S3_PORT}")  # fmt: skip
RELEASED = t2.REPO / "src/kp_canonicalization/profiles/paper-pdf@1.yaml"
DEV = t2.REPO / "tests/profiles/paper-pdf-dev.yaml"
# d3_server.py with --batch-size 1 runs one forward at a time: with 4 requests in flight the
# 30 s deadline would time the server's queue. One request took at most 12 s in #161.
RELAXED = {"d3_concurrency_per_document": 1}
ANTHROPIC = t5b.ANTHROPIC
# The user, 2026-11-15: Claude Sonnet 5.5 is the VLM candidate, in place of the DEV profile's
# gpt-6-luna. Its endpoint ignores reasoning_effort; thinking is on, at the default effort high.
VLM_COMPONENT = "anthropic/claude-sonnet-5-5"
PRICE_PER_MTOK = (2.0, 10.0)  # Sonnet 5.5, USD per million input and output tokens
STOP_AT_USD = 20.0
W2 = "docs/research/pdf-core-w2-native-coverage-2026-10-20/corpus/arxiv_gradientdescent/pdf.pdf"
VLM_METHODS = ("picture-interpretation", "formula", "code")


def run_profile(out: Path) -> tuple[Path, dict]:
    """paper-pdf@1 with the DEV components, VLM_COMPONENT and RELAXED, and what differs from the
    released file."""
    released, dev = yaml.safe_load(RELEASED.read_text()), yaml.safe_load(DEV.read_text())
    assert released["methods"].keys() == dev["methods"].keys(), "method sets differ"
    assert RELAXED.keys() <= released["runtime"].keys()
    profile = copy.deepcopy(released)
    differs: dict = {"components": {}, "runtime": {}}
    for name, method in profile["methods"].items():
        if any(c.startswith("company-") for c in method["components"]):
            now = [VLM_COMPONENT] if name.partition("@")[0] in VLM_METHODS else dev["methods"][name]["components"]
            differs["components"][name] = [method["components"], now]
            method["components"] = now
    for key, value in RELAXED.items():
        differs["runtime"][key] = [released["runtime"][key], value]
        profile["runtime"][key] = value
    path = out / "paper-pdf@1-199.yaml"
    path.write_text(yaml.safe_dump(profile, sort_keys=False))
    return path, differs


def s3_up(out: Path) -> str:
    """The S3 stand-in on S3_PORT with its data under OUT/s3; the container's name."""
    image = yaml.safe_load((t2.REPO / "tests/s3/compose.yaml").read_text())["services"]["rustfs"]
    name = f"kp-s3-199-{t2.RUN}"
    (out / "s3").mkdir(exist_ok=True)
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{S3_PORT}:9000",
                    *[a for k, v in image["environment"].items() for a in ("-e", f"{k}={v}")],
                    "-v", f"{out / 's3'}:/data", image["image"]], check=True, capture_output=True)  # fmt: skip
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{S3_PORT}/health", timeout=2):
                return name
        except OSError:
            time.sleep(1)
    raise SystemExit("S3 stand-in not healthy after 60 s")


def priced(sent: list[dict]) -> float:
    """USD of the provider requests; d3 runs locally."""
    (into, out), usd = PRICE_PER_MTOK, 0.0
    for r in sent:
        if not r["method"].startswith("d3-check"):
            usage = r.get("usage") or {}
            usd += ((usage.get("prompt_tokens") or 0) * into
                    + (usage.get("completion_tokens") or 0) * out) / 1e6  # fmt: skip
    return usd


def check_key() -> None:
    """Refuse to start when the provider refuses the key: the models endpoint costs nothing."""
    request = urllib.request.Request(f"{ANTHROPIC}/models/{VLM_COMPONENT.partition('/')[2]}", headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})  # fmt: skip
    try:
        urllib.request.urlopen(request, timeout=10).close()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"the provider refuses the API key: HTTP {exc.code}") from exc


async def run_case(store, bucket: str, sha: str, data: bytes, request_id: str) -> tuple[int, dict, float]:
    """t4-seam-b's run_case, but a workflow that ended failed has no result.json: start-request
    exits 0 then too, and only failure.json is written."""
    start = t2.start_input(sha, data, bucket, request_id)
    begin = time.monotonic()
    code, out = t2.start_request(bucket, start)
    seconds = round(time.monotonic() - begin, 1)
    if code != 0:
        print(out, file=sys.stderr)
    ref = f"requests/{request_id}/result.json"
    found = code == 0 and await store.head(ref) is not None
    return code, json.loads(await store.get(ref)) if found else {}, seconds


async def stages(client: Client, request_id: str) -> dict:
    """Per Activity type: executions, first scheduled to last closed, and the workflow's own
    start to close, in seconds, from the server's history."""
    history = await client.get_workflow_handle(request_id).fetch_history()
    names, spans = {}, {}
    first = last = None
    for event in history.events:
        at = event.event_time.ToDatetime(UTC)
        first, last = first or at, at
        if event.HasField("activity_task_scheduled_event_attributes"):
            names[event.event_id] = event.activity_task_scheduled_event_attributes.activity_type.name
            span = spans.setdefault(names[event.event_id], {"n": 0, "begin": at, "end": at})
            span["n"] += 1
        for kind in ("completed", "failed", "timed_out", "canceled"):
            field = f"activity_task_{kind}_event_attributes"
            if event.HasField(field):
                spans[names[getattr(event, field).scheduled_event_id]]["end"] = at
    out = {name: {"n": s["n"], "seconds": round((s["end"] - s["begin"]).total_seconds(), 1)}
           for name, s in spans.items() if name != "report"}  # fmt: skip
    out["workflow"] = {"n": 1, "seconds": round((last - first).total_seconds(), 1)}
    return out


async def observe(client, store, out: Path, index: str, request_id: str, code: int, result: dict,
                  seconds: float) -> dict:  # fmt: skip
    """One paper's row: no paper text, which goes to OUT/summaries for the summary check."""
    sent = await t4.receipts(store, request_id)
    evidence: dict = {"request_id": request_id, "exit": code, "seconds": seconds,
                      "receipts": {m: t4.receipt_summary([r for r in sent if r["method"] == m])
                                   for m in sorted({r["method"] for r in sent})},
                      "usd": round(priced(sent), 4)}  # fmt: skip
    last = {r["item_id"]: r for r in sent if r["method"].rpartition("@")[0] in VLM_METHODS}
    evidence["vlm_requests_recorded"] = dict(Counter(
        f"{r['method']} {'recorded' if score.recorded(r) else 'new'}" for r in last.values()))  # fmt: skip
    if await store.head(f"requests/{request_id}/failure.json") is not None:
        failure = json.loads(await store.get(f"requests/{request_id}/failure.json"))
        evidence["failure"] = {"stage": failure["stage"], "cause": failure["cause"],
                               "reason": failure["error"]["reason"], **failure["error"]["metadata"]}  # fmt: skip
    try:
        evidence["stages"] = await stages(client, request_id)
    except Exception as exc:  # a start that never reached the server
        evidence["stages"] = {"error": repr(exc)}
    if code != 0 or not result:
        return evidence
    inventory = json.loads(await store.get(result["inventory"]["ref"]))
    methods, _ = await t5c.judged(store, result)
    try:
        found, record = await t5b.summary_of(store, result)
        plan_key = found["enrichment"]["result_ref"].split("/")[3]
        sections = json.loads(await store.get(f"documents/{result['request']['document_uid']}/items/"
                                              f"{plan_key}/sections.json"))  # fmt: skip
    except (KeyError, ValueError) as exc:  # no summary enrichment or no sections.json: say so
        summary = {"error": repr(exc)}
    else:
        summary = t5b.shape(found, record, sections)
        (out / "summaries").mkdir(exist_ok=True)
        (out / "summaries" / f"summary-{index}.json").write_text(json.dumps(
            {"paper": int(index) if index.isdigit() else index,  # t5b-accuracy keys papers by int
             "content": found["outcome"]["content"], "record": record,
             "sections": sections}, indent=1, ensure_ascii=False))  # fmt: skip
    declared = result["profile"]
    evidence |= {
        "outcome": result["outcome"],
        "pages": len(result["native"]["page_images"]),
        "inventory_items": len(inventory["items"]),
        "inventory_counts": result["inventory"]["counts"],
        "statuses": t4.per_method(result),
        "d3": methods,
        "summary": summary,
        "limitations": [limitation["code"] for limitation in result["limitations"]],
        "profile": {"id": declared["id"], "runtime_identity": declared["runtime_identity"],
                    "methods": {f"{m['id']}@{m['version']}": {"components": m["components"],
                                                             "module_digest": m["module_digest"]}
                                for m in declared["methods"]}},
        "vlm_request_cap": 3 * len(inventory["items"]) + 20,
    }  # fmt: skip
    vlm_sent = sum(r["method"].rpartition("@")[0] in VLM_METHODS for r in sent)
    evidence["pass"] = (
        result["outcome"] == "complete"
        and all(s["incomplete"] == 0 for s in evidence["receipts"].values())
        and 0 <= vlm_sent <= evidence["vlm_request_cap"]
    )  # fmt: skip
    return evidence


GOLD = (  # globs under ARCHIVE: the gold and scorers score.py reads
    f"{score.t3.OCR_GOLD}/round2/evaluator/*.json", f"{score.t3.OCR_GOLD}/round4-local-ocr/*",
    f"{score.t3.OCR_GOLD}/round5-strict/*.py", f"{score.t3.OCR_GOLD}/round3-luna/*.py",
    f"{score.t3.CODE_GOLD}/per-unit.*", f"{score.t3.CODE_GOLD}/metrics.py",
    f"{score.t3.CODE_GOLD}/native-evidence/*.json",
    f"{score.t3.TABLE_GOLD}/cell-matching-confirm/per-table-final.json",
    f"{score.t3.TABLE_GOLD}/table/results/E0-v4.json", f"{score.t3.E0_JOBS}/*/document.json",
)  # fmt: skip


async def stored(store, ran: dict) -> dict:
    """Per request, the count of its objects in the S3 stand-in (result and receipts, whose refs
    pin the documents' objects) and the sha256 of their sorted "key sha256" lines."""
    found = {}
    for p in ran.values():
        keys = sorted(await store.list_prefix(f"requests/{p['request_id']}/"))
        lines = [f"{k} {hashlib.sha256(await store.get(k)).hexdigest()}" for k in keys]
        found[p["request_id"]] = {"objects": len(keys),
                                  "sha256": hashlib.sha256("\n".join(lines).encode()).hexdigest()}  # fmt: skip
    return found


def hashes(out: Path, ran: dict, archive: Path, package: Path, profile: Path, requests: dict) -> dict:
    """sha256 of what stays out of git: the papers, the gold, the d3 package's manifest, the
    profile the workers loaded, the requests' objects and the raw outputs under OUT."""
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: E731
    raw = [p for pattern in ("requests.json", "alone/*.json", "summaries/*.json", "judging/*")
           for p in sorted(out.glob(pattern)) if p.is_file()]  # fmt: skip
    return {
        "papers": {i: {"file": Path(p["file"]).name if i != "w2" else W2, "sha256": p["sha256"]}
                   for i, p in sorted(ran.items())},
        "profile": {"file": profile.name, "sha256": digest(profile)},
        "d3_package_manifest": digest(package / "MODEL_MANIFEST.json"),
        "gold": {str(p.relative_to(archive)): digest(p) for pattern in GOLD
                 for p in sorted(archive.glob(pattern)) if p.is_file()},
        "requests": requests,
        "outputs": {str(p.relative_to(out)): digest(p) for p in raw},
    }  # fmt: skip


def worker_env(real: bool, d3_env: dict) -> dict[str, dict]:
    """Per task queue, the variables of its worker: the providers, or the local stand-ins."""
    if real:
        vlm = {"KP_VLM_BASE_URL": ANTHROPIC, "KP_VLM_API_KEY": os.environ["ANTHROPIC_API_KEY"]}
        summary = {"KP_SUMMARY_BASE_URL": ANTHROPIC,
                   "KP_SUMMARY_API_KEY": os.environ["ANTHROPIC_API_KEY"]}  # fmt: skip
    else:
        vlm = {"KP_VLM_BASE_URL": f"http://127.0.0.1:{VLM_PORT}/v1", "KP_VLM_API_KEY": "none"}
        summary = {"KP_SUMMARY_BASE_URL": f"http://127.0.0.1:{SUMMARY_PORT}/v1",
                   "KP_SUMMARY_API_KEY": "none"}  # fmt: skip
    return {"orchestration": {}, "inference": {}, "vlm": vlm, "summary": summary, "d3": d3_env}


async def main(argv: list[str]) -> int:
    out, manifest, archive = Path(argv[0]).expanduser(), Path(argv[1]), Path(argv[2]).expanduser()
    package, python, indices = Path(argv[3]), argv[4], argv[5:]
    ports = (S3_PORT, TEMPORAL_PORT, TEMPORAL_PORT + 1, ADMISSION_PORT, VLM_PORT, SUMMARY_PORT,
             D3_PORT)  # fmt: skip
    if busy := [port for port in ports if t5.taken(port)]:
        raise SystemExit(f"ports already in use: {busy}")
    out.mkdir(parents=True, exist_ok=True)
    t2.LOGS = out / "logs"
    t2.LOGS.mkdir(exist_ok=True)
    (HERE / "papers").mkdir(exist_ok=True)
    state_path = out / "requests.json"
    state = (json.loads(state_path.read_text()) if state_path.exists()
             else {"bucket": f"e2e-199-{t2.RUN}", "papers": {}})  # fmt: skip
    bucket = state["bucket"]
    profile, differs = run_profile(out)
    corpus = {str(p["index"]): p for p in json.loads(manifest.read_text())["papers"]}
    todo = [i for i in indices if i not in state["papers"]]
    if any(i != "w2" for i in todo):
        check_key()

    def paper_of(index: str) -> tuple[dict, bytes]:
        if index == "w2":
            data = (archive / W2).read_bytes()
            return {"index": "w2", "file": W2, "pages": None,
                    "sha256": hashlib.sha256(data).hexdigest()}, data
        paper = corpus[index]
        data = (manifest.parent / paper["file"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == paper["sha256"], "paper differs from manifest"
        return paper, data

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # end the children, which hold the lock
    s3 = s3_up(out)
    processes: list[subprocess.Popen] = []
    workers: dict[str, subprocess.Popen] = {}
    servers = []
    try:
        store = t2.store(bucket)
        client = d3_env = None
        real = None
        for index in todo:
            spent = sum(p["usd"] for p in state["papers"].values())
            if spent >= STOP_AT_USD:
                print(f"stop line: US${spent:.2f} spent; {index} and later not started", flush=True)
                break
            if client is None:
                key = secrets.token_hex(16)
                d3_env = {"KP_D3_BASE_URL": f"http://127.0.0.1:{D3_PORT}", "KP_D3_API_KEY": key}
                command = ["d3_server.py", "--device", "mps", "--batch-size", "1", "--port",
                           str(D3_PORT)]  # fmt: skip
                d3 = subprocess.Popen(
                    [python, str(package / command[0]), *command[1:]],
                    env={**os.environ, "DECISION_API_KEY": key, "HF_HUB_OFFLINE": "1",
                         "TRANSFORMERS_OFFLINE": "1", "PYTORCH_ENABLE_MPS_FALLBACK": "0"},
                    stdout=open(t2.LOGS / "d3-server.log", "a"), stderr=subprocess.STDOUT,
                )  # fmt: skip
                temporal = subprocess.Popen(
                    ["temporal", "server", "start-dev", "--headless", "--port", str(TEMPORAL_PORT),
                     "--ui-port", str(TEMPORAL_PORT + 1), "--db-filename", str(out / "temporal.db"),
                     "--log-level", "warn", *t2.SEARCH_ATTRIBUTE_FLAGS],
                    stdout=open(t2.LOGS / "temporal.log", "a"), stderr=subprocess.STDOUT,
                )  # fmt: skip
                admission = subprocess.Popen(
                    [str(t2.REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server",
                     "--port", str(ADMISSION_PORT), "--log", str(t2.LOGS / "reports.jsonl")],
                    cwd=t2.REPO,
                )  # fmt: skip
                processes += [d3, temporal, admission]
                servers = [t5.stand_in(t5c.Replay, VLM_PORT), t5.stand_in(t5c.Summary, SUMMARY_PORT)]
                state["d3_server"] = {"command": command, "serves": t5c.wait_for_d3(d3, key)}
                print("d3 server ready", json.dumps(state["d3_server"]["serves"]), flush=True)
                for _ in range(60):
                    try:
                        client = await Client.connect(t2.TEMPORAL)
                        break
                    except RuntimeError:
                        await asyncio.sleep(0.5)
                assert client is not None
            if real != (index != "w2"):  # (re)start the workers against the right services
                real = index != "w2"
                t5c.stop(list(workers.values()))
                workers = {q: t5c.worker(bucket, "real" if real else "stand-in", q, profile, extra)
                           for q, extra in worker_env(real, d3_env).items()}  # fmt: skip
            paper, data = paper_of(index)
            sha = hashlib.sha256(data).hexdigest()
            await store.put_if_absent(f"custody/{sha}", data)
            request_id = f"req_{t2.RUN}_p{index}"
            row = HERE / "papers" / f"{index}.json"
            row.unlink(missing_ok=True)  # a row of an earlier run is not this run's
            code, result, seconds = await run_case(store, bucket, sha, data, request_id)
            # saved before observe(), so that an observe error never sends a paper twice
            state["papers"][index] = {"request_id": request_id, "sha256": sha, "file": paper["file"],
                                      "usd": round(priced(await t4.receipts(store, request_id)), 4)}  # fmt: skip
            state_path.write_text(json.dumps(state, indent=2) + "\n")
            evidence = await observe(client, store, out, index, request_id, code, result, seconds)
            evidence |= {"paper": {k: paper[k] for k in ("index", "sha256", "pages")},
                         "bucket": bucket, "services": "providers" if real else "stand-ins",
                         "profile_differs_from_released": differs}  # fmt: skip
            row.write_text(json.dumps(evidence, indent=2) + "\n")
            print(index, json.dumps({k: evidence.get(k) for k in
                                     ("pass", "seconds", "outcome", "failure", "usd")}), flush=True)  # fmt: skip
            failure = evidence.get("failure", {})
            if failure.get("reason") == "INFERENCE_REQUEST_REJECTED" and failure.get("status") in ("401", "403"):
                print(f"stop: the provider refused the credentials on paper {index}", flush=True)
                del state["papers"][index]  # not the paper's fault: a rerun starts it again
                state_path.write_text(json.dumps(state, indent=2) + "\n")
                break
        t5c.stop([*workers.values(), *processes])
        workers, processes = {}, []
        for server in servers:
            server.shutdown()
        servers = []

        ran = {i: p for i, p in state["papers"].items() if i in indices}
        corpus_ids = {p["request_id"]: f"paper {i}" for i, p in ran.items() if i != "w2"}
        if corpus_ids:
            found = tokens.report(await tokens.from_store(store, list(corpus_ids)))
            (HERE / "tokens.json").write_text(json.dumps(found, indent=1) + "\n")
            (HERE / "tokens.md").write_text(tokens.markdown(found, corpus_ids))
        async with httpx.AsyncClient() as http:
            chat = OpenAIChat(http, ANTHROPIC, os.environ["ANTHROPIC_API_KEY"],
                              VLM_COMPONENT.partition("/")[2], 5, 600)  # fmt: skip
            answered = await score.alone_answers(out, {int(i) for i in ran if i != "w2"}, profile, chat)
        accuracy = await score.accuracy(store, ran, archive, out / "judging", answered)
        (HERE / "accuracy.json").write_text(json.dumps(accuracy, indent=1) + "\n")
        print(json.dumps(accuracy["summary"], indent=1), flush=True)
        (HERE / "manifest.json").write_text(json.dumps(
            hashes(out, ran, archive, package, profile, await stored(store, ran)), indent=1) + "\n")  # fmt: skip
    finally:
        t5c.stop([*workers.values(), *processes])
        for server in servers:
            server.shutdown()
        subprocess.run(["docker", "stop", s3], capture_output=True)
    rows = {i: HERE / "papers" / f"{i}.json" for i in indices}
    failed = [i for i, path in rows.items()
              if not path.exists() or not json.loads(path.read_text()).get("pass")]  # fmt: skip
    print("failed:", failed or "none", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
