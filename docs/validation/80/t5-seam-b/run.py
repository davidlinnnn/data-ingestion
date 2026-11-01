"""Seam B for #134: one corpus paper through the real stack with all six enrichment methods, the
VLM and the summary API both served by local stand-ins (no external request).

    env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t5-seam-b/run.py CORPUS_MANIFEST [INDEX]

Same stack as #133's t4-seam-b/run.py (S3 stand-in on port 9100), plus `kp-processing worker
--queue summary`, on ports of its own (Temporal 7254, fake_admission 8101, VLM stand-in 8102,
summary stand-in 8103): it refuses to start when any is taken, since workers on another
session's Temporal would take that session's tasks. INDEX defaults to 20, the paper with
pictures, formulas, code and tables. The VLM stand-in is t4's: the canned answer after 3 s. The
summary stand-in serves the DEV mock (tests/summary.py) under the provisional contract and
records each request's shape.

Cases:
  S  a fresh bucket: the document completes, each of the six enrichment methods has
     enrichments, the summary is one document-scope enrichment from one request
  C  a new request for the same document in S's bucket: no summary request, every enrichment
     reused

evidence.json keeps counts, statuses and shapes only: the paper is third-party.
"""

import asyncio
import hashlib
import importlib.util
import json
import socket
import subprocess
import sys
import threading
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


t4 = load("t4", HERE.parent / "t4-seam-b/run.py")
t2, t3 = t4.t2, t4.t3
from tests.summary import answer  # noqa: E402

TEMPORAL_PORT, ADMISSION_PORT, VLM_PORT, SUMMARY_PORT = 7254, 8101, 8102, 8103
t2.TEMPORAL, t2.ADMISSION = f"127.0.0.1:{TEMPORAL_PORT}", f"http://127.0.0.1:{ADMISSION_PORT}"
t2.BASE_ENV.update(TEMPORAL_ADDRESS=t2.TEMPORAL, KP_ADMISSION_URL=t2.ADMISSION)
METHODS = {"picture-ocr", "picture-interpretation", "formula", "code", "table-status",
           "document-summary"}  # fmt: skip
SENT: list[dict] = []  # the shape of each request the summary stand-in received


class SummaryStandIn(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        request = json.loads(self.rfile.read(int(self.headers["content-length"])))
        SENT.append({"path": self.path, "keys": sorted(request),
                     "document_uid": request.get("document_uid"),
                     "sections": len(request.get("sections", [])),
                     "section_keys": sorted({k for s in request.get("sections", []) for k in s}),
                     "text_chars": sum(len(s["text"]) for s in request.get("sections", [])),
                     "max_sentences": request.get("max_sentences")})  # fmt: skip
        body = json.dumps(answer(request)).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


def worker(bucket: str, name: str, queue: str, extra: dict) -> subprocess.Popen:
    log = open(t2.LOGS / f"worker-{name}-{queue}.log", "w")
    return subprocess.Popen(
        [*t2.CLI, "worker", "--queue", queue, "--profile", t2.PROFILE, "--build-id", "seamb-r1"],
        env={**t2.env(bucket), **extra}, stdout=log, stderr=subprocess.STDOUT, cwd=t2.REPO,
    )  # fmt: skip


def stand_in(handler, port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def taken(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) == 0


async def main(manifest: Path, index: int) -> int:
    ports = (TEMPORAL_PORT, TEMPORAL_PORT + 1, ADMISSION_PORT, VLM_PORT, SUMMARY_PORT)
    if busy := [port for port in ports if taken(port)]:
        raise SystemExit(f"ports already in use: {busy}")
    t2.LOGS.mkdir(parents=True)
    paper = next(p for p in json.loads(manifest.read_text())["papers"] if p["index"] == index)
    data = (manifest.parent / paper["file"]).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    assert sha == paper["sha256"], "paper does not match the corpus manifest"
    uid = f"doc_{sha[:16]}"
    evidence: dict = {"run": t2.RUN,
                      "paper": {k: paper[k] for k in ("index", "file", "sha256", "pages")}}  # fmt: skip
    temporal = subprocess.Popen(
        ["temporal", "server", "start-dev", "--headless", "--port", str(TEMPORAL_PORT),
         "--ui-port", str(TEMPORAL_PORT + 1),
         "--db-filename", str(t2.LOGS / "temporal.db"), "--log-level", "warn"],
        stdout=open(t2.LOGS / "temporal.log", "w"), stderr=subprocess.STDOUT,
    )  # fmt: skip
    admission = subprocess.Popen(
        [str(t2.REPO / ".venv/bin/python"), "-m", "tools.fake_admission.server",
         "--port", str(ADMISSION_PORT),
         "--log", str(t2.LOGS / "reports.jsonl")], cwd=t2.REPO,
    )  # fmt: skip
    servers = [stand_in(t4.StandIn, VLM_PORT), stand_in(SummaryStandIn, SUMMARY_PORT)]
    bucket = f"seamb-{t2.RUN}-t5"
    workers = [
        *t2.workers_for(bucket, "s"),
        worker(bucket, "s", "vlm", {"KP_VLM_BASE_URL": f"http://127.0.0.1:{VLM_PORT}/v1",
                                    "KP_VLM_API_KEY": "none"}),
        worker(bucket, "s", "summary", {"KP_SUMMARY_BASE_URL": f"http://127.0.0.1:{SUMMARY_PORT}",
                                        "KP_SUMMARY_API_KEY": "none"}),
    ]  # fmt: skip
    try:
        for _ in range(60):
            try:
                await Client.connect(t2.TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        store = t2.store(bucket)
        await store.put_if_absent(f"custody/{sha}", data)

        # S: the whole profile, fresh bucket.
        request_s = f"req_{t2.RUN}_s"
        code, result, seconds = await t4.run_case(bucket, sha, data, request_s)
        sent = await t4.receipts(store, request_s)
        enrichments = result.get("enrichments", [])
        methods = {e["method_ref"]["id"] for e in enrichments}
        summaries = [e for e in enrichments if e["method_ref"]["id"] == "document-summary"]
        summary_receipts = [r for r in sent if r["method"] == "document-summary@1"]
        evidence["S"] = {"exit": code, "seconds": seconds,
                         "reports": t2.shape(await t2.reports(request_s)),
                         "statuses": t4.per_method(result) if result else None,
                         "methods_with_enrichments": sorted(methods),
                         "summary_requests": list(SENT),
                         "summary_receipts": t4.receipt_summary(summary_receipts),
                         "vlm_receipts": t4.receipt_summary(
                             [r for r in sent if r["method"] != "document-summary@1"]),
                         "summary": [{k: e[k] for k in ("item_id", "scope", "origin",
                                                        "target_refs", "input_refs", "status",
                                                        "status_reason")}
                                     | {"supports": [s["support"] for s in
                                                     (e["content"] or {}).get("sentences", [])]}
                                     for e in summaries],
                         "result": t3.summary(result) if result else None}  # fmt: skip
        assembly_ref = result.get("native", {}).get("assembly_ref")
        evidence["S"]["pass"] = (
            code == 0
            and result["outcome"] == "complete"
            and methods == METHODS
            and "document-summary" in result["inventory"]["counts"]
            and len(SENT) == 1
            and SENT[0]["path"] == "/v1/summaries"
            and SENT[0]["keys"] == ["document_uid", "max_sentences", "sections"]
            and SENT[0]["document_uid"] == uid
            and SENT[0]["section_keys"] == ["heading", "section_id", "text"]
            and 0 < SENT[0]["sections"] and 0 < SENT[0]["text_chars"]
            and len(summaries) == 1
            and evidence["S"]["summary"][0]["scope"] == "document"
            and evidence["S"]["summary"][0]["target_refs"] == ["#"]
            and evidence["S"]["summary"][0]["input_refs"] == [assembly_ref]
            and (summaries[0]["status"], summaries[0]["status_reason"]) == ("unverified", None)
            and evidence["S"]["summary_receipts"]["results"]["ok"] == 1
            and evidence["S"]["summary_receipts"]["requests"] == 1
        )  # fmt: skip

        # C: a second request reuses everything, the summary included.
        before = set(await store.list_prefix(f"documents/{uid}/"))
        request_c = f"req_{t2.RUN}_c"
        code, result_c, seconds = await t4.run_case(bucket, sha, data, request_c)
        evidence["C"] = {"exit": code, "seconds": seconds,
                         "summary_requests": len(SENT) - 1,
                         "external_receipts": len(await t4.receipts(store, request_c)),
                         "objects_added_under_documents": sorted(
                             set(await store.list_prefix(f"documents/{uid}/")) - before),
                         "enrichments_reused": all(e["reused"] for e in result_c["enrichments"]),
                         "statuses_equal_S": t4.per_method(result_c) == t4.per_method(result)}  # fmt: skip
        evidence["C"]["pass"] = (
            code == 0 and evidence["C"]["summary_requests"] == 0
            and evidence["C"]["external_receipts"] == 0
            and evidence["C"]["objects_added_under_documents"] == []
            and evidence["C"]["enrichments_reused"] and evidence["C"]["statuses_equal_S"]
        )  # fmt: skip
    finally:
        for process in [*workers, admission, temporal]:
            process.terminate()
            process.wait()
        for server in servers:
            server.shutdown()
    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    for case in ("S", "C"):
        print(case, {k: v for k, v in evidence.get(case, {}).items() if k != "result"})
    return 0 if all(evidence.get(c, {}).get("pass") for c in ("S", "C")) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 20)))
