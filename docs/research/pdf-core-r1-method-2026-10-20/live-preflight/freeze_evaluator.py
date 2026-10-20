"""Evaluator-only freeze: source snapshots, all-job QA obligations and answer refs."""
from copy import deepcopy
import datetime
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import protocol as p


def unit(value):
    result=deepcopy(value)
    # Image pixels are already immutable artifacts; retain their hash, not a
    # second base64 copy in the text/table/source-ownership QA manifest.
    if result.get("image"):
        result["image"]={"original_field_sha256":p.m.digest(result["image"])}
    return result


def main():
    out=HERE/"evaluator"
    if (out/"freeze.json").exists():raise ValueError("already frozen; do not reseal")
    jobs=p.read(p.R1/"planning/jobs.json")["jobs"]
    snapshots={};qa=[]
    for job in jobs:
        baseline=job["baseline"]
        if baseline not in snapshots:
            raw=p.read(p.ROOT/baseline)
            snapshots[baseline]={"baseline_file_sha256":p.sha((p.ROOT/baseline).read_bytes()),
                "document_revision":p.m.digest(raw),
                "body":deepcopy(raw["body"]),"groups":deepcopy(raw["groups"]),
                "units":{x["self_ref"]:unit(x) for array in ("texts","tables","pictures") for x in raw[array]}}
        qa.append({"job_id":job["job_id"],"task":job["task"],"baseline":baseline,
            "native_snapshot":baseline,"scope_pages":job["binding"]["pages"],
            "full_document_non_target_regression_required":True,
            "all_consumed_ordinary_prose_still_source_checked":True,
            "tables_and_picture_identity_read_only":True,
            "caption_and_footnote_edges_preserved":True,
            "generated_text_in_primary_Markdown_forbidden":True,
            "C_original_source_document_read_only":job["task"]!="source_reconstruction"})
    (out/"non-target-manifest.json").write_text(json.dumps({"role":"evaluator-only regression snapshots, NOT semantic source golden",
        "snapshots":snapshots,"all_43_job_obligations":qa},ensure_ascii=False,indent=2)+"\n")
    old=[
        "docs/research/pdf-core-stage1-2026-10-17/A-evaluator/source-census.json",
        "docs/research/pdf-core-stage1-2026-10-17/A-evaluator/source-census.freeze.json",
        "docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json",
        "docs/research/pdf-core-eval-interfaces-2026-10-18/C/source-contract-index.json",
        "docs/research/pdf-core-eval-interfaces-2026-10-18/C/evaluator-wikiskill-figure1-contract.json",
        "docs/research/pdf-core-eval-interfaces-2026-10-18/C/evaluator-wikiskill-figure3-contract.json",
        "docs/research/pdf-core-eval-interfaces-2026-10-18/C/evaluator-memory-r1-contract.json"]
    files={str(x.relative_to(p.ROOT)):p.sha(x.read_bytes()) for x in sorted(out.iterdir()) if x.is_file()}
    files.update({name:p.sha((p.ROOT/name).read_bytes()) for name in old})
    for record in p.read(out/"source-index.json"):
        path=p.R1/"production"/record["image"]["asset"]
        files[str(path.relative_to(p.ROOT))]=p.sha(path.read_bytes())
        files[record["source_pdf"]["path"]]=record["source_pdf"]["sha256"]
    frozen={"frozen_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "new_model_outputs_seen":0,"new_source_job_sheets":11,"new_source_pages_visually_reviewed":14,
        "all_job_non_target_QA_count":len(qa),"complete_semantic_gold":False,
        "pending":"Complete occurrence inventory and partial C OCR gold listed in expected-answers.json/rubric.md",
        "files":files}
    (out/"freeze.json").write_text(json.dumps(frozen,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":"SOURCE_ONLY_PARTIAL_GOLD_FROZEN","files":len(files),"jobs_with_QA":43,
        "freeze_sha256":p.sha((out/"freeze.json").read_bytes())}))


if __name__=="__main__":main()
