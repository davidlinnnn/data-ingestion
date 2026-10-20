"""Read-only integrity checks; emits only into this W3 experiment directory."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_options(value):
    # Pinned stage_model_specs.py:162 declares this field Set[VlmEngineType].
    # JSON array order varies across Python hash seeds; do not ignore other lists.
    if isinstance(value, dict):
        return {k: sorted(v) if k == "supported_engines" and isinstance(v, list)
                else semantic_options(v) for k, v in value.items()}
    if isinstance(value, list):
        return [semantic_options(v) for v in value]
    return value


def main():
    checks = []

    def check(name, condition, detail=None):
        checks.append(dict(name=name, passed=bool(condition), detail=detail))

    for name in ("oracle-freeze.json", "selection-freeze.json", "selection-freeze-v2.json"):
        seal = load(HERE / name)
        for relative, expected in seal["files"].items():
            path = HERE / relative
            check(f"{name}:{relative}", path.exists() and sha(path) == expected)
    e0 = load(HERE / "E0-inputs.json")
    check("E0_documents", len(e0["jobs"]) == 36)
    check("E0_pages", sum(j["pages"] for j in e0["jobs"]) == 715)
    for job in e0["jobs"]:
        for key in ("selected_document", "selected_markdown"):
            path = ROOT / job[key]
            check(f"{job['job_id']}:{key}", sha(path) == job[key + "_sha256"])
        check(f"{job['job_id']}:E0_reused", job["new_E0_conversion"] is False)
    table = load(HERE / "table/E0-results-v2.json")
    check("table_source_count", len(table["tables"]) == 252)
    check("table_gold_seal", table["oracle_sha256"] == sha(HERE / "table/oracle.json"))
    image = load(HERE / "image/summary.json")
    check("image_scope", image["documents"] == 36 and image["selected_pages"] == 715)
    check("image_mapper_geometry_unchanged", image["RAW_MAPPED_raster_geometry_identical"])
    check("image_mapper_detection_unchanged", image["RAW_MAPPED_detection_label_bbox_identical"])
    fc = HERE / "formula-code"
    assessment_seal = load(fc / "assessment-freeze.json")
    for relative, expected in assessment_seal["files_sha256"].items():
        path = fc / relative
        check("formula_assessment_seal:" + relative, path.exists() and sha(path) == expected)
    summary = load(fc / "assessment-summary.json")
    audit = summary["formula_audit"]
    check("formula50_complete", audit["selection_final"] and audit["selected_formula_blocks"] == 50
          and audit["reviewed_selected"] == 50 and audit["confirmed_blocking_selected"] == 15)
    check("formula50_status_sum", sum(audit["statuses"].values()) == 50)
    check("E1_success_scope", summary["E1"]["completed_jobs"] == 17
          and summary["E1"]["actual_processed_native_refs"] == 85)
    coverage = load(fc / "final-processing-coverage.json")
    check("gate_coverage_conservation", coverage["gate_native_refs_total"] == 211
          and coverage["processed_gate_native_refs"] == 84 and coverage["remaining_gate_native_refs"] == 127)
    cases = load(fc / "blocking-cases.json")
    check("case_counts", [len(cases[k]) for k in ("formula_selected", "code_manual", "algorithm_manual")] == [15, 6, 1])
    check("case_schemas_and_mode_equality", all(c.get("source_pages") and c["RAW_verdict"] == c["MAPPED_verdict"]
          for k in ("formula_selected", "code_manual", "algorithm_manual") for c in cases[k]))
    families = load(HERE / "family-summary.json")["families"]
    check("family_scope_conservation", len(families) == 10 and sum(f["documents"] for f in families) == 36
          and sum(f["pages"] for f in families) == 715)
    for field, expected in (("E1_formula_selected_Q31_blocking", 15), ("E1_code_literal_or_log_Q4_blocking", 6),
                            ("E1_algorithm_static_Q33_blocking", 1), ("E0_table_Q13_failed_tables", 5),
                            ("E0_image_Q4_blocking", 2)):
        check("family_block_conservation:" + field, sum(f["adjudication"][field] for f in families) == expected)
    canonical_options = None
    for run in ("E1_pilot", "E1_sampled_v2"):
        for directory in sorted((HERE / "runs" / run / "jobs").iterdir()):
            conversion = directory / "conversion.json"
            if not conversion.exists() or load(conversion).get("status") != "success":
                continue
            options = load(directory / "effective-options.json")
            if canonical_options is None:
                canonical_options = options
            check(f"{run}:{directory.name}:same_semantic_effective_options",
                  semantic_options(options) == semantic_options(canonical_options),
                  "Only supported_engines Set serialization order normalized; raw effective-options.json preserved.")
            check(f"{run}:{directory.name}:CPU4", options["accelerator_options"]["num_threads"] == 4
                  and options["accelerator_options"]["device"] == "cpu")
            check(f"{run}:{directory.name}:E1_flags", options["do_formula_enrichment"]
                  and options["do_code_enrichment"] and not options["generate_page_images"]
                  and not options["generate_picture_images"])
            check(f"{run}:{directory.name}:other_enrichments_off", not any(options[k] for k in
                  ("do_picture_description", "do_picture_classification", "do_chart_extraction", "enable_remote_services")))
            heading = options["heading_hierarchy_options"]
            check(f"{run}:{directory.name}:selected_E0_configuration", options["use_reading_order_separators"]
                  and options["layout_options"]["model_spec"]["name"] == "layout_heron"
                  and options["layout_options"]["model_spec"]["revision"].startswith("8f39ad3c")
                  and heading["enabled"] and heading["use_bookmarks"]
                  and not heading["use_numbering"] and not heading["use_style"])
            selection = directory / "sample-selection-observed.json"
            if selection.exists():
                observed = load(selection)
                check(f"{run}:{directory.name}:frozen_gate_exact", sorted(observed["selected_refs"]) == sorted(observed["expected_refs"]))
    for filename in ("table/report-v2.md", "image/report.md", "method.md", "resources.json", "report.md",
                     "family-summary.md", "table-status.md", "blocking-list.md", "official-next-options.md", "budget-stop.json"):
        check("deliverable:" + filename, (HERE / filename).exists())
    result = dict(checked_utc=datetime.now(timezone.utc).isoformat(),
                  scope="Frozen inputs, saved E0 identity, source counts and completed deliverables. Not a semantic acceptance test.",
                  passed=sum(c["passed"] for c in checks), failed=sum(not c["passed"] for c in checks), checks=checks)
    (HERE / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("checked_utc", "passed", "failed")}))
    if result["failed"]:
        print(json.dumps([c for c in checks if not c["passed"]], ensure_ascii=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
