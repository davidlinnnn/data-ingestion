"""Offline final checks for36 fresh development exchanges; no requests or holdout reads."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REPORT = HERE.with_suffix(".md")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")


def main():
    prior = {}
    for name in ["pdf-core-g2-local-cpu-2026-10-14", "pdf-core-g2-round2-2026-10-14",
                 "pdf-core-g2-round3-2026-10-14", "pdf-core-g2-api-2026-10-14",
                 "pdf-core-g2-images-2026-10-14", "pdf-core-g2-heading-2026-10-15",
                 "pdf-core-g2-orientation-2026-10-15", "pdf-core-g2-inline-2026-10-15",
                 "pdf-core-g2-inline-api-2026-10-15", "pdf-core-g2-inline-boundary-2026-10-15",
                 "pdf-core-g2-eval-freeze-2026-10-15", "pdf-core-g2-context-candidate-2026-10-15"]:
        records = read(HERE.parent / name / "artifacts.json")["files"]
        checked, untouched = 0, 0
        for record in records:
            if record["path"].startswith("docs/fixtures/pdf-core-g2-holdout-") and record["path"].endswith(".pdf"):
                untouched += 1
                continue
            path = REPO / record["path"]
            assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
            checked += 1
        prior[name] = {"checked": checked, "holdout_pdf_bytes_not_accessed": untouched}
    assert sum(v["checked"] for v in prior.values()) == 2022
    assert sum(v["holdout_pdf_bytes_not_accessed"] for v in prior.values()) == 6
    refs = set()

    def check_refs(value):
        if isinstance(value, dict):
            if "path" in value and re.fullmatch(r"[0-9a-f]{64}", value.get("sha256", "")):
                assert not value["path"].startswith("docs/fixtures/pdf-core-g2-holdout-")
                path = REPO / value["path"]
                assert path.is_file() and sha(path) == value["sha256"], path
                refs.add(value["path"])
            for child in value.values():
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)

    registration = read(HERE / "run-registration.json")
    check_refs(registration)
    assert registration["independent_source_contracts_frozen_before_inference"]
    assert len(registration["source_contract_refs"]) == 2 and registration["target_count"] == 36
    assert registration["new_candidate_configuration"] is False and registration["holdout_reads"] == 0
    api = read(HERE / "api/verification.json")
    check_refs(api)
    assert api["passed"] and api["verified_exchanges"] == 36
    assert api["all_http_bodies_reconstructed"] and api["all_raw_messages_match_saved_outputs"]
    assert api["unique_request_ids"] and api["unique_response_ids"]
    parsed = read(HERE / "parsed/summary.json")
    check_refs(parsed)
    assert parsed["output_count"] == 36 and not parsed["model_text_repaired"]
    integrated = read(HERE / "integration/results.json")
    check_refs(integrated)
    assert integrated["inputs"] == 36 and integrated["structurally_applied"] == 34
    assert integrated["negative_controls"] == 23 and not integrated["canonical_acceptance"]
    assert integrated["all_original_inputs_and_provider_graphs_unchanged"] and integrated["all_outside_serialized_literals_unchanged"]
    assert not integrated["lexical_truth_gate"] and not integrated["semantic_quality_assessed"]
    a = read(HERE / "review-wiki-dgm/reviewresults.json")
    b = read(HERE / "review-seal-controls/results.json")
    check_refs(a)
    check_refs(b)
    assert len(a["results"]) == 13 and len(b["jobs"]) == 23
    assert sha(HERE / "review-wiki-dgm/source-contract.json") == "effca07ba2779bfd49e0610fead6d121f4feeba783575956dc852465c06b567f"
    assert sha(HERE / "review-seal-controls/source-contract.json") == "825be8ee51991187d439ad4c28549746dd6ec7927ea9c8cec347e5aff9c643bb"
    assert sha(HERE / "review-wiki-dgm/reviewresults.json") == "344e35c4cb8d4b42818e4f900ded702f3cd042c778b7ea12ee65c5149fdb83bd"
    assert sha(HERE / "review-seal-controls/results.json") == "53c9a26faee8e1b9f3913c9a23832d57e470efa389e11c8b1fe4b2bf00f38743"
    consistency = read(HERE / "integration/source-review-consistency.json")
    check_refs(consistency)
    assert consistency["passed"] and consistency["all_four_protected_bounded_positives_preserved"]
    assert consistency["original_rubrics_unchanged"] and consistency["raw_shard_contracts_results_and_outputs_unchanged"]
    assert consistency["four_content_or_math_material_jobs"] == 4 and consistency["two_additional_material_typed_delivery_jobs"] == 2
    assert not consistency["accepted_working_projection_created"] and not consistency["whole_run_adoption_supported"]
    summary = read(HERE / "summary.json")
    check_refs(summary)
    assert summary["raw_source_status_counts"] == {"pass": 25, "minor": 5, "material": 6}
    assert summary["visible_content_and_math_meaning_pass"]["numerator"] == 32
    assert summary["selected_logical_work_scope"]["total"] == 41
    assert summary["selected_logical_work_scope"]["not_attempted"] == 5
    assert not summary["g2_passed"] and not summary["selected_holdout_challenger"]
    usage = read(HERE / "usage.json")
    check_refs(usage)
    assert usage["request_count"] == 36 and usage["each_request_one_attempt"] and usage["all_finish_stop"]
    assert usage["tokens"] == {"prompt": 25720, "cached_prompt": 0, "completion": 13643,
                               "reasoning_included_in_completion": 7143, "total": 39363}
    assert abs(usage["standard_token_rate_estimate_usd"]-.0093935) < 1e-12
    ticket = read(HERE / "ticket-update.json")
    assert ticket["comment_exact_readback"] and ticket["issue_body_exact_readback"]
    assert ticket["feature_rows_unchanged"] == 44 and ticket["issue_state"] == "OPEN"
    assert ticket["comment_url"] == "https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6195331080"
    links = 0
    human_docs = [REPORT, *(p for p in HERE.rglob("*.md") if p.name not in {"document.md", "working.md", "baseline.md"}),
                  *(HERE.parent / n for n in ("README.md", "docling-pdf-core-g2-pipeline-start-2026-10-14.md",
                                             "docling-pdf-core-capability-validation-plan-2026-10-14.md"))]
    for path in human_docs:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            linked = (path.parent / target.split("#")[0]).resolve()
            assert linked.exists() or linked in {HERE / "artifacts.json", HERE / "validation.json"}, (path, target)
            links += 1
    files = []
    for path in sorted([REPORT, *HERE.rglob("*")]):
        if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts or path.name in {"artifacts.json", "validation.json"}:
            continue
        if path.suffix in {".py", ".json", ".md", ".txt"}:
            assert not re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", path.read_text()), "Possible credential; never print matching text"
        files.append({"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size, "sha256": sha(path)})
    save(HERE / "artifacts.json", {"scope": "Candidate1 fresh36 development exchanges, independent source assessment and structural overlay; no holdout access", "files": files})
    result = {"passed": True, "prior_payloads_unchanged": prior, "evidence_refs_checked": len(refs),
        "source_contracts_frozen_before_inference": True, "fresh_api_calls": 36, "attempts_each": 1,
        "strict_parse_and_structural_applications": 34, "parse_failures": 2,
        "raw_source_review_statuses": summary["raw_source_status_counts"],
        "source_gradable_prepared_targets": 36, "selected_logical_work_scope": 41, "unattempted_scope_units": 5,
        "protected_bounded_positive_checks": 4, "raw_reviews_and_original_rubrics_unchanged": True,
        "source_full_target_flags_pooled_as_acceptance": False, "adapter_negative_controls": 23,
        "new_candidate_configurations": 0, "new_candidate_or_response_tuning": False,
        "model_reruns": 0, "holdout_reads": 0, "canonical_acceptance": False,
        "selected_holdout_challenger": False, "g2_passed": False,
        "ticket_summary_and_body_exact_readback": True, "ticket_feature_rows_unchanged": 44,
        "credential_pattern_scan_clean": True, "local_markdown_links_checked": links,
        "payload_files": len(files), "payload_bytes": sum(r["bytes"] for r in files)}
    save(HERE / "validation.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
