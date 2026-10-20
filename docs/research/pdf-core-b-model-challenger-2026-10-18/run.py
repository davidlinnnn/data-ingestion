"""Single model-only challenger through the existing bounded seven-job runner."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys

import httpx
import psutil

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
B=ROOT/"docs/research/pdf-core-eval-interfaces-2026-10-18/B"
sys.path.insert(0,str(B))
spec=importlib.util.spec_from_file_location("challenger_bridge",B/"runner.py")
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)


def read(path):return json.loads(Path(path).read_text())


def write(path,data):
    with Path(path).open("x") as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2);stream.write("\n")


def prepare():
    old=bridge.verify()
    access=read(HERE/"model-access.json")
    assert access["status_code"]==200 and access["returned_model_id"]=="gpt-6.1-sol"
    gates=read(ROOT/"docs/research/pdf-core-offline-gates-2026-10-18/tests-v2.json")
    assert gates["run"]==19 and gates["failures"]==gates["errors"]==0
    reg=deepcopy(old);reg["model"]="gpt-6.1-sol"
    diffs=[];(HERE/"requests").mkdir()
    for before,job in zip(old["jobs"],reg["jobs"],strict=True):
        job["body_without_image"]["model"]=reg["model"]
        comparison=deepcopy(job["body_without_image"]);comparison["model"]=old["model"]
        assert comparison==before["body_without_image"],"only model may change"
        job.pop("http_body_sha256")
        raw=bridge.body(job);job["http_body_sha256"]=sha256(raw).hexdigest()
        (HERE/"requests"/(job["name"]+".json")).write_bytes(raw)
        diffs.append(dict(job=job["name"],only_request_change="model",source_image_unchanged=True,
                          prompt_schema_options_unchanged=True,http_body_sha256=job["http_body_sha256"]))
    reg.update(frozen_at=datetime.now(timezone.utc).isoformat(),
        authorization="User chose to complete B as an independent capability after AC offline decision",
        profile_qualification_claim=False)
    own=[HERE/"run.py",ROOT/"docs/research/pdf-core-offline-gates-2026-10-18/scoring.py",
         ROOT/"docs/research/pdf-core-offline-gates-2026-10-18/table_seam.py",
         ROOT/"docs/research/pdf-core-offline-gates-2026-10-18/test_gates.py"]
    reg["method_files"].update({str(p):bridge.sha(p) for p in own})
    write(HERE/"candidate.json",reg)
    write(HERE/"request-diff.json",diffs)
    print(json.dumps(dict(calls_max=reg["calls_max"],model=reg["model"],
        input_reservation=reg["total_input_budget"],completion_cap=reg["total_completion_budget"],
        offline_controls=19,new_inference_calls=0)))


def verify():
    reg=read(HERE/"candidate.json")
    old=bridge.verify()
    assert len(reg["jobs"])==reg["calls_max"]==7
    for path,expected in reg["method_files"].items():assert bridge.sha(path)==expected,path
    for before,job in zip(old["jobs"],reg["jobs"],strict=True):
        assert bridge.body(job)==(HERE/"requests"/(job["name"]+".json")).read_bytes()
        body=deepcopy(job["body_without_image"]);body["model"]=old["model"]
        assert body==before["body_without_image"]
        assert bridge.sha(job["baseline"])==job["baseline_sha256"]
        assert bridge.sha(job["source_path"])==job["source_sha256"]
    return reg


def live():
    reg=verify()
    assert psutil.virtual_memory().available>=reg["prelaunch_available_bytes"],"requires 10GiB available"
    transport=bridge.legacy(reg)
    with httpx.Client(timeout=httpx.Timeout(reg["request_seconds"],connect=20),
                      follow_redirects=False,trust_env=False) as client:
        result=transport.execute(reg,client,os.environ.get("OPENAI_API_KEY",""),HERE/"live")
    verify()
    model_ok=all(r.get("model")==reg["model"] or str(r.get("model","")).startswith(reg["model"]+"-")
                 for r in result["records"] if r.get("http_status")==200)
    write(HERE/"model-identity-check.json",dict(requested=reg["model"],all_received_identities_match=model_ok,
        observed=sorted({str(r.get("model")) for r in result["records"]}),immutable_weights_claim=False))
    print(json.dumps(dict(ledger=result["ledger"],stopped=result["stopped"],model_identity_valid=model_ok)))


if __name__=="__main__":
    if sys.argv[1:]==["--prepare"]:prepare()
    elif sys.argv[1:]==["--verify"]:verify();print("Seven model-only request changes verified; no inference")
    elif sys.argv[1:]==["--live"]:live()
    else:raise SystemExit("Use --prepare, --verify or --live")
