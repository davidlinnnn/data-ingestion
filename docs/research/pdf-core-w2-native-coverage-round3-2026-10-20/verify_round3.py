"""Verify persisted research evidence; does not rerun conversion or inference."""
import collections
import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PREV = ROOT.parent / "pdf-core-w2-native-coverage-round2-2026-10-20"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_count(obj):
    if isinstance(obj, list):
        return sum(image_count(v) for v in obj)
    if isinstance(obj, dict):
        return sum((int(v is not None) if k == "image" else image_count(v)) for k, v in obj.items())
    return 0


def main():
    registration = read(ROOT / "registration.json")
    assert sha(PREV / "analyze_full.py") == registration["analyzer_v3_sha256"]
    assert sha(PREV / "oracle/freeze.json") == registration["oracle_freeze_sha256"]
    seal = read(PREV / "oracle/freeze.json")
    oracle_files = []
    for relative, expected in seal["files"].items():
        candidates = [PREV / "oracle" / relative, PREV / relative]
        path = next(p for p in candidates if p.is_file())
        assert sha(path) == expected, path
        oracle_files.append(str(path))
    jobs = read(ROOT / "jobs.json")["jobs"]
    assert len(jobs) == 36
    assert sum(j["last"] - j["first"] + 1 for j in jobs) == 715
    assert all(sha(Path(j["pdf"])) == j["pdf_sha256"] for j in jobs)
    controls = read(ROOT / "controls-equivalence.json")
    assert controls["equivalent"] and all(c["equivalent"] for c in controls["cases"])
    assert max(c["pages"] for c in controls["cases"]) >= 25
    conversions = []
    for name, expected_papers, expected_pages in (("controls-v1", 2, 39), ("recovery", 6, 216),
                                                  ("V1", 36, 715), ("V2-official", 36, 715)):
        folder = ROOT / "runs" / name
        execution = read(folder / "execution.json")
        records = execution["records"]
        assert len(records) == expected_papers
        assert sum(r["pages"] for r in records) == expected_pages
        assert all(r["status"] == "success" and r["exit_code"] == 0 and r["stop"] is None
                   and r["retries"] == 0 for r in records)
        assert max(s["rss"] for s in execution["samples"]) <= 12 * 2**30
        assert min(s["available"] for s in execution["samples"]) >= 4 * 2**30
        for record in records:
            source = folder / "jobs" / record["id"]
            opts = read(source / "effective-options.json")
            assert opts["generate_page_images"] is False and opts["generate_picture_images"] is False
            for key in ("do_code_enrichment", "do_formula_enrichment", "do_picture_classification",
                        "do_picture_description", "do_chart_extraction", "enable_remote_services", "allow_external_plugins"):
                assert opts[key] is False
            assert opts["accelerator_options"]["num_threads"] == 4
            assert opts["accelerator_options"]["device"] == "cpu"
            assert all(opts[key] == 1 for key in ("ocr_batch_size", "layout_batch_size", "table_batch_size"))
            assert opts["use_reading_order_separators"] is (name != "V1")
            assert image_count(read(source / "document.json")) == 0
            assert (source / "document.md").exists() and (source / "result.json").exists()
            conversions.append({"run": name, "id": record["id"], "pages": record["pages"],
                                "document_sha256": sha(source / "document.json"),
                                "markdown_sha256": sha(source / "document.md")})
    catalog = read(ROOT / "analysis/baseline/candidate-catalog.json")
    records = read(ROOT / "adjudication/records.json")
    assert len(catalog) == len(records) == 875
    assert {x["id"] for x in catalog} == {x["candidate_id"] for x in records}
    assert len({x["candidate_id"] for x in records}) == len(records)
    assert all(x["status"] in ("CLEAN_AFTER_ADJUDICATION", "CONFIRMED_BLOCKING") for x in records)
    assert all(x["source_reason"] and x["output_reason"] for x in records)
    adam_missing = [x for x in records if x["job_id"] == "F-iclr_adam" and x["kind"] == "missing_anchor"]
    assert len(adam_missing) == 45
    papers = read(ROOT / "adjudication/papers.json")
    assert collections.Counter(p["status"] for p in papers) == {"CONFIRMED_BLOCKING": 13,
                                                               "CLEAN_AFTER_ADJUDICATION": 23}
    headings = read(ROOT / "heading/summary.json")
    assert headings["completed_documents"] == 36
    for combination, summary in headings["totals"].items():
        assert summary["documents"] == 36 and summary["level_only"]
        assert summary["text_sequence_unchanged"] and summary["actual_parents_unchanged"]
        for job in jobs:
            assert image_count(read(ROOT / "heading/jobs" / job["id"] / combination / "document.json")) == 0
    assert headings["totals"]["b1-n0-s0"]["versus_baseline"]["fixed"] == 175
    assert headings["totals"]["b1-n0-s0"]["versus_baseline"]["new_bad"] == 0
    pdfium = read(ROOT / "heading/pdfium-integration/summary.json")
    assert pdfium["documents"] == 36 and pdfium["all_documents_identical_to_doclingparse_outline"]
    assert pdfium["all_markdown_identical_to_doclingparse_outline"]
    for variant in ("baseline", "V1", "V2-official", "V3_B"):
        summaries = read(ROOT / "analysis" / variant / "summary.json")
        assert len(summaries) == 36 and sum(s["selected_pages"] for s in summaries) == 715
        assert all(s["metric_status"] == "SCORED_CANDIDATES" for s in summaries)
    assert read(ROOT / "comparison/V3_B.json")["removed"] == 0
    assert read(ROOT / "comparison/V3_B.json")["added"] == 0
    semantic = read(ROOT / "comparison/semantic-summary.json")
    assert semantic["V2_delta_rows"] == 330 and semantic["V2_delta_coverage_complete"]
    assert semantic["V2_baseline_groups_checked"] == 26
    assert semantic["V1"] == {"fixed": 1, "new_bad": 3}
    assert semantic["V2"]["fixed"] == 3 and semantic["V2"]["new_bad"] == 13
    all_records = read(ROOT / "comparison/V2-semantic-all-records.json")
    key = lambda x: (x["direction"], x["job_id"], x["kind"], json.dumps(x["identity"], sort_keys=True))
    assert {key(x) for x in all_records} == {key(x) for x in read(ROOT / "comparison/V2-official-changed-cases.json")}
    assert len(all_records) == len({key(x) for x in all_records}) == 330
    groups = read(ROOT / "adjudication/root-groups.json")
    assert len(groups) == 26
    assert len({(g["job_id"], p) for g in groups for p in g["confirmed_affected_pages"]}) == 35
    assert sum(f["confirmed_affected_job_pages"] for f in read(ROOT / "adjudication/families.json")) == 35
    assert read(ROOT / "comparison/V2-Bonly-candidate-equivalence.json")["exact_candidate_json_equal"]
    documents = ["report.md", "papers.md", "remaining-blockers.md", "recommended-profile.json",
                 "comparison/semantic-summary.md", "comparison/automatic-family-type.md", "heading/family-comparison.md"]
    for name in documents:
        path = ROOT / name
        assert path.exists()
        if path.suffix == ".md":
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                assert (path.parent / target).exists(), (name, target)
    now = datetime.datetime.now(datetime.timezone.utc)
    assert now < datetime.datetime.fromisoformat(registration["deadline_utc"].replace("Z", "+00:00"))
    result = {"verified_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "status": "PASS", "actual_conversions": len(conversions),
              "actual_page_attempts": sum(x["pages"] for x in conversions),
              "oracle_sealed_files_unchanged": len(oracle_files), "source_pdf_hashes_unchanged": 36,
              "analyzer_v3_unchanged": True, "generated_candidates_adjudicated": 875,
              "adam_missing_candidates_adjudicated": len(adam_missing),
              "baseline_confirmed_source_events": len(groups), "baseline_confirmed_affected_job_pages": 35,
              "V2_changed_identities_adjudicated": 330, "V2_baseline_source_groups_rechecked": 26,
              "final_deliverable_hashes": {name: sha(ROOT / name) for name in documents},
              "within_2_5_hour_budget": True,
              "heading_documents_by_combinations": "36 x 8 = 288; image fields empty",
              "scope": "Evidence validation only; no conversion, stage execution, inference or external service call.",
              "actual_conversion_artifacts": conversions}
    (ROOT / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "actual_conversion_artifacts"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
