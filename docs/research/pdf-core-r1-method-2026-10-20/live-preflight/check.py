"""Read-only preflight evidence validation; no seal refresh, model or transport."""
import os
from pathlib import Path
import sys

import protocol as p
import runner


def main():
    seal=p.read(p.HERE/"artifact-seal.json")
    if not seal:raise ValueError("empty preflight seal")
    for name,expected in seal.items():
        path=(p.HERE/name).resolve()
        if not path.is_relative_to(p.HERE) or p.sha(path.read_bytes())!=expected:
            raise ValueError("changed preflight artifact: "+name)
    for name,expected in p.read(p.R1/"artifact-seal.json").items():
        if p.sha((p.R1/name).read_bytes())!=expected:raise ValueError("historical R1 modified")
    frozen=p.read(p.HERE/"evaluator/freeze.json")
    for name,expected in frozen["files"].items():
        if p.sha((p.ROOT/name).read_bytes())!=expected:raise ValueError("changed frozen source/gold: "+name)
    jobs=p.read(p.R1/"planning/jobs.json")["jobs"]
    budgets=p.read(p.HERE/"token-budget.json")
    by_id={r["job_id"]:r for r in budgets["jobs"]}
    ledger=p.read(p.HERE/"dry-run/final-ledger.json")
    if len(jobs)!=43 or len(ledger)!=43 or {r["job_id"] for r in ledger}!=set(by_id):
        raise ValueError("scope mismatch")
    if budgets["totals"]["input_tokens_estimate"] is not None or budgets["live_ready"]:
        raise ValueError("unverified token mapping promoted")
    for job,row in zip(jobs,ledger,strict=True):
        body=p.materialize(job)
        if p.sha(p.encoded(body))!=by_id[job["job_id"]]["request_sha256"] or row["request_sha256"]!=by_id[job["job_id"]]["request_sha256"]:
            raise ValueError("request binding changed")
        if row["state"]!="MOCK_VALIDATED" or row["attempts"]!=1 or row["new_inference_calls"]:
            raise ValueError("unexpected dispatch/state")
        response=p.read(p.HERE/"dry-run"/(job["job_id"]+".json"))
        runner.validate_provider(job,body,response["raw_provider_response"],row["input_reservation"])
    delivery=p.HERE/"dry-run/delivery"
    source_files=list(delivery.glob("*.source.json"))
    C_files=list(delivery.glob("*.supplement.json"))
    if len(source_files)!=11 or len(C_files)!=14:raise ValueError("missing deliveries")
    for path in source_files:
        value=p.read(path);result=value["result"]
        regenerated=p.m.apply(p.read(p.ROOT/value["baseline"]),result["binding"]["group"],result["raw_response"])
        if regenerated["document"]!=result["document"] or regenerated["markdown"]!=result["markdown"]:
            raise ValueError("source writeback differs")
    if sum(len(p.read(path)["supplement"]["images"]) for path in C_files)!=29:
        raise ValueError("native image work lost")
    qa=p.read(p.HERE/"evaluator/non-target-manifest.json")["all_43_job_obligations"]
    if {x["job_id"] for x in qa}!={x["job_id"] for x in jobs}:raise ValueError("non-target QA lost")
    summary=p.read(p.HERE/"dry-run/summary.json")
    if summary["stop"] or summary["validated"]!=43 or summary["new_inference_calls"]:
        raise ValueError("dry-run failed or ran inference")
    print({"status":"passed","preflight_sealed_files":len(seal),"frozen_source_and_gold_files":len(frozen["files"]),
        "MOCK_jobs":43,"source_deliveries":11,"C_supplements":14,"native_images":29,
        "live_ready":False,"new_inference_calls":0})


if __name__=="__main__":
    os.environ.pop("OPENAI_API_KEY",None)
    def guard(event,args):
        if event in {"socket.connect","socket.getaddrinfo"}:raise RuntimeError("network forbidden")
        if event=="open" and isinstance(args[0],(str,bytes)):
            name=os.fsdecode(args[0])
            if "holdout" in name or "pdf-core-w2-native-coverage" in name or any(c in (args[1] or "") for c in "wax+"):
                raise RuntimeError("read-only non-holdout preflight checker")
    sys.addaudithook(guard)
    main()
