"""Seam B for #132: the corpus paper with the most pictures through the real stack, with local
enrichment.

    env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t3-seam-b/run.py CORPUS_MANIFEST [INDEX]

Same stack as #131's t2-tracer-bullet/run.py, whose helpers it reuses: the S3 stand-in
(tests/s3/compose.yaml, port 9100), a Temporal dev server (port 7244), fake_admission (port
8091), and one kp-processing worker subprocess per task queue on the DEV profile. INDEX defaults
to 20, the paper with the most pictures (22) in census.json (census.py).

Cases:
  A  uninterrupted run in a fresh bucket; the objects it adds under documents/ are the
     negative control for C's listing
  C  a new request for the same document: every item, enrichment included, is reused and no
     object is added under documents/

The Processing Result carries text from the paper (OCR, code, table HTML), so evidence.json
keeps statuses, counts and content digests only; the full result stays outside git.
"""

import asyncio
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

from temporalio.client import Client

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("t2", HERE.parent / "t2-tracer-bullet/run.py")
assert spec and spec.loader
t2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t2)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def summary(result: dict) -> dict:
    """The result without third-party text: statuses, counts and content digests."""
    return {
        "outcome": result["outcome"],
        "profile": {k: result["profile"][k] for k in ("id", "status_rule", "methods")},
        "native": {"page_images": len(result["native"]["page_images"]),
                   "picture_images": len(result["native"]["picture_images"]),
                   "page_groups": len(result["native"]["page_groups"])},
        "inventory_counts": result["inventory"]["counts"],
        "enrichments": [
            {"item_id": e["item_id"], "status": e["status"], "status_reason": e["status_reason"],
             "reused": e["reused"], "inline": e["content"] is not None,
             "content_sha256": digest(e["content"]) if e["content"] is not None else None,
             "evidence_refs": len(e["evidence_refs"]), "signals": e["signals"]}
            for e in result["enrichments"]
        ],
        "limitations": [lim["code"] for lim in result["limitations"]],
    }  # fmt: skip


async def enrich_local_reuse(client: Client, request_id: str) -> list[bool]:
    """The reused flags of the outcomes enrich_local returned, from the workflow history."""
    history = await client.get_workflow_handle(request_id).fetch_history()
    scheduled = {}
    for event in history.events:
        if event.HasField("activity_task_scheduled_event_attributes"):
            attrs = event.activity_task_scheduled_event_attributes
            scheduled[event.event_id] = attrs.activity_type.name
        elif event.HasField("activity_task_completed_event_attributes"):
            attrs = event.activity_task_completed_event_attributes
            if scheduled[attrs.scheduled_event_id] == "enrich_local":
                return [o["reused"] for o in json.loads(attrs.result.payloads[0].data)]
    return []


async def main(manifest: Path, index: int) -> int:
    t2.LOGS.mkdir(parents=True)
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
    workers = []
    try:
        for _ in range(60):
            try:
                client = await Client.connect(t2.TEMPORAL)
                break
            except RuntimeError:
                await asyncio.sleep(0.5)
        bucket = f"seamb-{t2.RUN}-t3"
        store = t2.store(bucket)
        await store.put_if_absent(f"custody/{sha}", data)
        workers = t2.workers_for(bucket, "t3")

        empty = set(await store.list_prefix(f"documents/{uid}/"))
        a = t2.start_input(sha, data, bucket, f"req_{t2.RUN}_a")
        begin = time.monotonic()
        code, out = t2.start_request(bucket, a)
        result_a = json.loads(await store.get(f"requests/{a['request_id']}/result.json"))
        (t2.LOGS / "result-A.json").write_text(json.dumps(result_a, indent=2))
        evidence["A"] = {"exit": code, "seconds": round(time.monotonic() - begin, 1),
                         "outcome": out.strip().splitlines()[-1],
                         "reports": t2.shape(await t2.reports(a["request_id"])),
                         "activities": [x["activity"] for x in
                                        await t2.activity_history(client, a["request_id"])],
                         "enrich_local_reused": await enrich_local_reuse(client, a["request_id"]),
                         "result": summary(result_a)}  # fmt: skip
        before = set(await store.list_prefix(f"documents/{uid}/"))
        reused_a = evidence["A"]["enrich_local_reused"]
        evidence["A"]["objects_added_under_documents"] = len(before - empty)
        evidence["A"]["pass"] = (
            code == 0
            and len(reused_a) == len(result_a["enrichments"]) > 0
            and not any(reused_a)
            and len(before - empty) > len(reused_a)
        )

        c = t2.start_input(sha, data, bucket, f"req_{t2.RUN}_c")
        begin = time.monotonic()
        code, out = t2.start_request(bucket, c)
        result_c = json.loads(await store.get(f"requests/{c['request_id']}/result.json"))
        evidence["C"] = {"exit": code, "seconds": round(time.monotonic() - begin, 1),
                         "enrich_local_reused": await enrich_local_reuse(client, c["request_id"]),
                         "objects_added_under_documents": sorted(
                             set(await store.list_prefix(f"documents/{uid}/")) - before),
                         "enrichments_reused": all(e["reused"] for e in result_c["enrichments"]),
                         "statuses_equal_A": [(e["item_id"], e["status"]) for e in
                                              result_c["enrichments"]] ==
                                             [(e["item_id"], e["status"]) for e in
                                              result_a["enrichments"]]}  # fmt: skip
        reused_c = evidence["C"]["enrich_local_reused"]
        evidence["C"]["pass"] = (
            code == 0
            and len(reused_c) == len(reused_a)
            and all(reused_c)
            and evidence["C"]["objects_added_under_documents"] == []
            and evidence["C"]["enrichments_reused"]
            and evidence["C"]["statuses_equal_A"]
        )
    finally:
        for process in [*workers, admission, temporal]:
            process.terminate()
            process.wait()
    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({k: v for k, v in evidence.items() if k != "A"}, indent=1))
    print("A", {k: v for k, v in evidence["A"].items() if k not in ("result", "activities")})
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 20)))
