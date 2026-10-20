"""Cross-check saved final products only. Does not rerun conversion or scoring."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_exists(value):
    path = Path(value)
    return path.is_file() if path.is_absolute() else (HERE / path).is_file()


def main():
    checks = {}
    semantic = load("comparison/V4-adjudicated.json")
    limits = load("selected-limitations.json")
    metrics = load("comparison/metric-summary.json")
    mapper = load("mapper/summary.json")
    checks["conversion_and_freeze_verification"] = load("verification.json")["status"] == "PASS"
    checks["all_changed_identities_adjudicated"] = semantic["changed_identity_coverage"] == "COMPLETE" and semantic["changed_identity_rows_reviewed"] == 135
    groups = semantic["baseline_group_checks"]
    checks["original_event_partition"] = len(groups) == 26 and sum(g.get("q4_fixed", False) for g in groups) == 5 and semantic["partial_fixed_groups"] == 8 and 26 - 5 - 8 == 13
    checks["new_event_partition"] = len(semantic["new_groups"]) == 6 and semantic["new_blocking_documents"] == 6 and semantic["new_blocking_job_pages"] == 16
    checks["reject_rule"] = semantic["recommendation"] == "DO_NOT_ADOPT" and semantic["new_blocking_groups"] > 0
    image_rows = semantic["changed_records"] + groups + load("comparison/newly-discovered-baseline.json")
    missing_images = [(r.get("candidate_id",r.get("source_rootcause_group",r.get("group_id"))), img) for r in image_rows for img in r.get("page_images",[]) if not image_exists(img)]
    checks["page_evidence_exists"] = not missing_images
    checks["all_new_blocking_rows_visually_reviewed"] = all(r["reviewed_visual"] and r["reviewed_native_and_markdown"] and r.get("page_images") for r in semantic["changed_records"] if r.get("q4_new_bad"))
    checks["newly_discovered_baseline_not_in_original_denominator"] = limits["original_comparison_denominator"] == 26 and limits["newly_discovered_preexisting_events"] == 5 and limits["events"] == 31
    papers = limits["papers"]
    checks["paper_classification_scope"] = len(papers) == 36 and sum(p["pages"] for p in papers) == 715 and sum(p["status"] == "CONFIRMED_BLOCKING" for p in papers) == 13 and sum(p["status"] == "CLEAN_AFTER_ADJUDICATION" for p in papers) == 23
    pages = {(p["job_id"],pg) for p in papers for pg in p["confirmed_affected_pages"]}
    checks["affected_pages_crosscheck"] = len(pages) == 40 and sum(f["affected_job_pages"] for f in limits["families"]) == 40
    checks["family_scope_crosscheck"] = sum(f["pages"] for f in limits["families"]) == 715 and sum(f["documents"] for f in limits["families"]) == 36
    checks["category_events_crosscheck"] = sum(c["events"] for c in limits["categories"]) == 31
    checks["metric_scope_crosscheck"] = all(metrics["total"][name]["documents"] == 36 and metrics["total"][name]["pages"] == 715 and metrics["total"][name]["trusted_prose"] == 6097 for name in ("baseline","V4"))
    checks["mapper_scope_and_units"] = mapper["documents"] == 36 and mapper["counts"]["fallback_text_items"] == 366 and mapper["counts"]["merged_cells"] == 282 and mapper["same_ref_duplicate_deliveries"] == 0
    mcheck = load("mapper/selfcheck.json")
    checks["mapper_selfchecks"] = mcheck["source_hashes_verified_unchanged"] and mcheck["all_source_native_text_cells_once"] and mcheck["render_refs_once"]
    current_sources = []
    for row in load("mapper/counts.json")["jobs"]:
        value = row["input"]
        current_sources.append(sha(Path(value["path"])) == value["sha256"])
    checks["mapper_input_hashes_still_unchanged"] = len(current_sources) == 36 and all(current_sources)
    checks["mapper_outputs_complete"] = all((HERE / "mapper/outputs" / row["id"] / filename).is_file() for row in load("mapper/counts.json")["jobs"] for filename in ("mapped.json","document.html","document.md","counts.json"))
    checks["original30_review_seal"] = all(sha(HERE / name) == expected for name,expected in load("comparison/original30-seal.json").items())
    heading = load("heading-outline.json")
    checks["outline_scope"] = sum(g["documents"] for g in heading["groups"]) == 36 and next(g["documents"] for g in heading["groups"] if not g["has_outline"]) == 10
    documents = ["report.md","decision-record.md","mapper/README.md","heading-outline.md","comparison/original30-summary.md","comparison/recovery-report.md"]
    missing_links = []
    for name in documents:
        path = HERE / name
        for value in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if value.startswith(("http:", "https:", "#")):
                continue
            if not (path.parent / value.split("#")[0]).exists():
                missing_links.append((name,value))
    checks["report_links_exist"] = not missing_links
    status = "PASS" if all(checks.values()) else "FAIL"
    output = dict(status=status, checks=checks, missing_images=missing_images, missing_links=missing_links,
                  method="Read saved outputs, verify counts/source hashes/review evidence/link targets. No conversion, oracle editing, analyzer rerun or semantic extrapolation.")
    (HERE / "final-verification.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    manifest_files = documents + ["comparison/V4-adjudicated.json","selected-limitations.json","mapper/summary.json","mapper/selfcheck.json","verification.json","final-verification.json","resources.json"]
    (HERE / "completion-manifest.json").write_text(json.dumps(dict(status=status, sha256={name:sha(HERE/name) for name in manifest_files}), ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(status=status, checks=len(checks), failed=[k for k,v in checks.items() if not v], missing_images=missing_images, missing_links=missing_links), ensure_ascii=False))


if __name__ == "__main__":
    main()
