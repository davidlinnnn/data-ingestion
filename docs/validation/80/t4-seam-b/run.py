"""Seam B for #133: the corpus paper with the most pictures through the real stack, with VLM
enrichment against the DEV reference model and against a 3-second stand-in.

    env HF_HUB_OFFLINE=1 OPENAI_API_KEY=... .venv/bin/python docs/validation/80/t4-seam-b/run.py \
        CORPUS_MANIFEST [INDEX]

Same stack as #132's t3-seam-b/run.py (S3 stand-in on port 9100, Temporal dev server on 7244,
fake_admission on 8091), plus a `kp-processing worker --queue vlm` subprocess. INDEX defaults to
20, the paper with the most pictures in t3-seam-b/census.json. Only the 20 public corpus papers
may be sent to the DEV model (#129).

Cases, in this order (F first, so that nothing reaches the real model unless the stack works
and the request count is under MAX_REAL_REQUESTS):
  R  the DEV profile against the real DEV reference model (openai/gpt-6-luna), fresh bucket;
     its responses are the fixtures (tests/fixtures/vlm/<method>/<params_digest>.json)
  C  a new request for the same document in R's bucket: no VLM request, every item reused
  F  a fresh bucket against a local stand-in that answers every request after 3 s; the item,
     enrichment and request counts are compared with R

The Processing Result quotes the paper, so evidence.json keeps statuses, counts, receipts
without content, and content digests only; the fixtures keep the full model responses (#129).
"""

import asyncio
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from temporalio.client import Client

HERE = Path(__file__).resolve().parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


t2 = load("t2", HERE.parent / "t2-tracer-bullet/run.py")
t3 = load("t3", HERE.parent / "t3-seam-b/run.py")
sys.path.insert(0, str(t2.REPO))
from tests.vlm import canned  # noqa: E402

FIXTURES = t2.REPO / "tests/fixtures/vlm"
OPENAI = "https://api.openai.com/v1"
STAND_IN_PORT = 8092
# Stop line before any spend: about US$0.002 per request in the #84 trial with this model.
MAX_REAL_REQUESTS = 150


class StandIn(BaseHTTPRequestHandler):
    """An OpenAI-compatible endpoint that answers every request after 3 s with tests.vlm's
    canned answer for the request's schema."""

    def do_POST(self) -> None:
        request = json.loads(self.rfile.read(int(self.headers["content-length"])))
        time.sleep(3)
        body = canned(request).body
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


def vlm_worker(bucket: str, name: str, url: str, key: str) -> subprocess.Popen:
    log = open(t2.LOGS / f"worker-{name}-vlm.log", "w")
    return subprocess.Popen(
        [*t2.CLI, "worker", "--queue", "vlm", "--profile", t2.PROFILE, "--build-id", "seamb-r1"],
        env={**t2.env(bucket), "KP_VLM_BASE_URL": url, "KP_VLM_API_KEY": key},
        stdout=log, stderr=subprocess.STDOUT, cwd=t2.REPO,
    )  # fmt: skip


async def receipts(store, request_id: str) -> list[dict]:
    keys = await store.list_prefix(f"requests/{request_id}/attempts/")
    return [json.loads(await store.get(k)) for k in sorted(keys) if "/receipts/" in k]


def receipt_summary(sent: list[dict]) -> dict:
    latencies = sorted(r["latency_ms"] for r in sent if "latency_ms" in r)
    return {
        "requests": len(sent),
        "results": {k: sum(r.get("result") == k for r in sent)
                    for k in ("ok", "unavailable", "invalid", "refused")},
        "reasons": sorted({r.get("reason") for r in sent} - {None}),
        "incomplete": sum("result" not in r for r in sent),
        "latency_ms": {"min": latencies[0], "median": latencies[len(latencies) // 2],
                       "max": latencies[-1]} if latencies else None,
        "tokens": {k: sum((r.get("usage") or {}).get(k, 0) for r in sent)
                   for k in ("prompt_tokens", "completion_tokens")},
        "models": sorted({r.get("model") for r in sent} - {None}),
        "system_fingerprints": sorted({str(r.get("system_fingerprint")) for r in sent}),
    }  # fmt: skip


def per_method(result: dict) -> dict:
    counts: dict = {}
    for e in result["enrichments"]:
        key = (e["method_ref"]["id"], e["status"], e["status_reason"])
        counts[" ".join(map(str, key))] = counts.get(" ".join(map(str, key)), 0) + 1
    return dict(sorted(counts.items()))


async def run_case(bucket: str, sha: str, data: bytes, request_id: str) -> tuple[int, dict, float]:
    start = t2.start_input(sha, data, bucket, request_id)
    begin = time.monotonic()
    code, out = t2.start_request(bucket, start)
    seconds = round(time.monotonic() - begin, 1)
    store = t2.store(bucket)
    result = json.loads(await store.get(f"requests/{request_id}/result.json")) if code == 0 else {}
    (t2.LOGS / f"result-{request_id}.json").write_text(json.dumps(result, indent=2))
    if code != 0:
        print(out, file=sys.stderr)
    return code, result, seconds


async def save_fixtures(store, result: dict, sent: list[dict]) -> int:
    """Each provider artifact under tests/fixtures/vlm/<method>/<params_digest of its last
    receipt>.json; returns the number saved."""
    by_item = {r["item_id"]: r for r in sent}
    saved = 0
    for e in result["enrichments"]:
        ref, item_id = e["provider_artifact_ref"], e["item_id"].split("/caption")[0]
        if not ref or e["item_id"].endswith(("/chart_values", "/description", "/figure_type")):
            continue
        receipt = by_item.get(item_id)
        if receipt is None:
            continue
        folder = FIXTURES / e["method_ref"]["id"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{receipt['params_digest']}.json").write_bytes(await store.get(ref))
        saved += 1
    return saved


async def main(manifest: Path, index: int) -> int:
    t2.LOGS.mkdir(parents=True)
    key = os.environ["OPENAI_API_KEY"]
    paper = next(p for p in json.loads(manifest.read_text())["papers"] if p["index"] == index)
    data = (manifest.parent / paper["file"]).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    assert sha == paper["sha256"], "paper does not match the corpus manifest"
    uid = f"doc_{sha[:16]}"
    evidence: dict = {"run": t2.RUN,
                      "paper": {k: paper[k] for k in ("index", "file", "sha256", "pages")}}  # fmt: skip
    temporal = subprocess.Popen(
        ["temporal", "server", "start-dev", "--headless", "--port", "7244", "--ui-port", "7245",
         "--db-filename", str(t2.LOGS / "temporal.db"), "--log-level", "warn"],
        stdout=open(t2.LOGS / "temporal.log", "w"), stderr=subprocess.STDOUT,
    )  # fmt: skip
    admission = subprocess.Popen(
        [str(t2.REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server", "--port", "8091",
         "--log", str(t2.LOGS / "reports.jsonl")], cwd=t2.REPO,
    )  # fmt: skip
    stand_in = ThreadingHTTPServer(("127.0.0.1", STAND_IN_PORT), StandIn)
    threading.Thread(target=stand_in.serve_forever, daemon=True).start()
    workers: list[subprocess.Popen] = []
    try:
        for _ in range(60):
            try:
                await Client.connect(t2.TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)

        # F: the 3-second stand-in, fresh bucket.
        bucket = f"seamb-{t2.RUN}-t4f"
        store = t2.store(bucket)
        await store.put_if_absent(f"custody/{sha}", data)
        workers = [*t2.workers_for(bucket, "f"),
                   vlm_worker(bucket, "f", f"http://127.0.0.1:{STAND_IN_PORT}/v1", "none")]
        request_f = f"req_{t2.RUN}_f"
        code_f, result_f, seconds_f = await run_case(bucket, sha, data, request_f)
        sent_f = await receipts(store, request_f)
        if code_f != 0:
            raise SystemExit("F failed; nothing sent to the real model")
        if len(sent_f) > MAX_REAL_REQUESTS:
            raise SystemExit(f"F needed {len(sent_f)} requests, over the stop line")
        for process in workers:
            process.terminate()
            process.wait()

        # R: the real DEV model.
        bucket = f"seamb-{t2.RUN}-t4r"
        store = t2.store(bucket)
        await store.put_if_absent(f"custody/{sha}", data)
        workers = [*t2.workers_for(bucket, "r"), vlm_worker(bucket, "r", OPENAI, key)]
        empty = set(await store.list_prefix(f"documents/{uid}/"))
        request_r = f"req_{t2.RUN}_r"
        code, result_r, seconds = await run_case(bucket, sha, data, request_r)
        sent_r = await receipts(store, request_r)
        evidence["R"] = {"exit": code, "seconds": seconds,
                         "reports": t2.shape(await t2.reports(request_r)),
                         "receipts": receipt_summary(sent_r),
                         "statuses": per_method(result_r),
                         "inventory_counts": result_r.get("inventory", {}).get("counts"),
                         "fixtures_saved": await save_fixtures(store, result_r, sent_r),
                         "result": t3.summary(result_r) if result_r else None}  # fmt: skip
        vlm_items = {e["item_id"].rsplit("/", 1)[0] if e["method_ref"]["id"] ==
                     "picture-interpretation" else e["item_id"]
                     for e in result_r.get("enrichments", [])
                     if e["method_ref"]["id"] in ("picture-interpretation", "formula", "code")}  # fmt: skip
        before = set(await store.list_prefix(f"documents/{uid}/"))
        evidence["R"]["objects_added_under_documents"] = len(before - empty)
        evidence["R"]["pass"] = (
            code == 0
            and result_r["outcome"] == "complete"
            and evidence["R"]["receipts"]["incomplete"] == 0
            and 0 < len(sent_r) <= 3 * len(json.loads(await store.get(
                result_r["inventory"]["ref"]))["items"]) + 20
        )  # fmt: skip

        # C: a new request for the same document reuses everything.
        request_c = f"req_{t2.RUN}_c"
        code, result_c, seconds = await run_case(bucket, sha, data, request_c)
        evidence["C"] = {"exit": code, "seconds": seconds,
                         "vlm_requests": len(await receipts(store, request_c)),
                         "objects_added_under_documents": sorted(
                             set(await store.list_prefix(f"documents/{uid}/")) - before),
                         "enrichments_reused": all(e["reused"] for e in result_c["enrichments"]),
                         "statuses_equal_R": per_method(result_c) == per_method(result_r)}  # fmt: skip
        evidence["C"]["pass"] = (
            code == 0 and evidence["C"]["vlm_requests"] == 0
            and evidence["C"]["objects_added_under_documents"] == []
            and evidence["C"]["enrichments_reused"] and evidence["C"]["statuses_equal_R"]
        )  # fmt: skip
        for process in workers:
            process.terminate()
            process.wait()

        items_r = {k: sum(v.values()) for k, v in result_r["inventory"]["counts"].items()}
        items_f = {k: sum(v.values()) for k, v in result_f["inventory"]["counts"].items()}
        evidence["F"] = {"exit": code_f, "seconds": seconds_f,
                         "receipts": receipt_summary(sent_f),
                         "statuses": per_method(result_f),
                         "enrichments": len(result_f["enrichments"]),
                         "enrichments_R": len(result_r["enrichments"]),
                         "counts_per_method": items_f, "counts_per_method_R": items_r,
                         "vlm_items_R": len(vlm_items)}  # fmt: skip
        evidence["F"]["pass"] = (
            code_f == 0
            and items_f == items_r
            and len(result_f["enrichments"]) == len(result_r["enrichments"])
            and evidence["F"]["receipts"]["results"]["ok"] == len(sent_f)
            and 3000 <= evidence["F"]["receipts"]["latency_ms"]["min"]
            and evidence["F"]["receipts"]["latency_ms"]["max"] <= 4000
        )  # fmt: skip
    finally:
        for process in [*workers, admission, temporal]:
            process.terminate()
            process.wait()
        stand_in.shutdown()
    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    for case in ("R", "C", "F"):
        print(case, {k: v for k, v in evidence.get(case, {}).items() if k != "result"})
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 20)))
