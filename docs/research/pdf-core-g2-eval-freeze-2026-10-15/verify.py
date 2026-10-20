"""Offline custody, split, retention and scorecard checks; no inference or PDF parsing."""
import copy
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REPORT = HERE.with_suffix(".md")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def validate_split(audit, custody):
    excluded_groups = {r["group_id"] for r in audit["excluded_document_groups"]}
    excluded_hashes = {m["sha256"] for r in audit["excluded_document_groups"] for m in r["members"]}
    rows = custody["documents"]
    assert custody["status"] == "custody_only_acquired" and len(rows) == 6
    assert len({r["work_group"] for r in rows}) == len({r["sha256"] for r in rows}) == 6
    assert not excluded_groups.intersection(r["work_group"] for r in rows)
    assert not excluded_hashes.intersection(r["sha256"] for r in rows)
    assert all(r["split"] == "holdout" and r["acquisition_status"] == "acquired" for r in rows)
    assert all(r["text_reference_matches_before_fetch"] == r["filename_reference_matches_before_fetch"] == 0 for r in rows)
    assert not custody["custody_policy"]["pdf_content_inspected"]
    assert not custody["custody_policy"]["labels_created"]
    assert custody["custody_policy"]["model_calls"] == 0


def sampled_pages(document_sha256, page_count):
    assert re.fullmatch(r"[0-9a-f]{64}", document_sha256) and page_count >= 1
    chosen = {1, page_count}
    ranked = sorted((hashlib.sha256(f"{document_sha256}:{p}".encode()).hexdigest(), p)
                    for p in range(2, page_count))
    return sorted(chosen | {p for _, p in ranked[:2]})


def score(outcomes):
    allowed = {"delivered_source_pass", "delivered_source_fail", "explicit_abstention",
               "execution_failure", "not_attempted_or_missing"}
    assert all(value in allowed for value in outcomes)
    n = len(outcomes)
    accepted = sum(value.startswith("delivered_") for value in outcomes)
    ratio = lambda count, denominator: count / denominator if denominator else None
    return {"eligible": n, "accepted": accepted,
            "coverage": ratio(accepted, n),
            "selective_error": ratio(outcomes.count("delivered_source_fail"), accepted),
            "faithful_delivery": ratio(outcomes.count("delivered_source_pass"), n),
            "false_abstention": ratio(outcomes.count("explicit_abstention"), n),
            "technical_failure_rate": ratio(outcomes.count("execution_failure"), n),
            "not_attempted_rate": ratio(outcomes.count("not_attempted_or_missing"), n)}


def selfchecks(audit, custody):
    rejected = []
    mutations = {
        "exposed_work_in_holdout": lambda d: d["documents"][0].update(work_group=audit["excluded_document_groups"][0]["group_id"]),
        "exposed_bytes_in_holdout": lambda d: d["documents"][0].update(sha256=audit["excluded_document_groups"][0]["members"][0]["sha256"]),
        "duplicate_work": lambda d: d["documents"][0].update(work_group=d["documents"][1]["work_group"]),
        "duplicate_bytes": lambda d: d["documents"][0].update(sha256=d["documents"][1]["sha256"]),
        "wrong_role": lambda d: d["documents"][0].update(split="development"),
        "missing_acquisition": lambda d: d["documents"][0].update(acquisition_status="reserved"),
        "content_already_inspected": lambda d: d["custody_policy"].update(pdf_content_inspected=True),
        "model_already_called": lambda d: d["custody_policy"].update(model_calls=1),
        "prior_work_reference_found": lambda d: d["documents"][0].update(text_reference_matches_before_fetch=1),
    }
    for name, mutate in mutations.items():
        changed = copy.deepcopy(custody)
        mutate(changed)
        try:
            validate_split(audit, changed)
        except AssertionError:
            rejected.append(name)
        else:
            raise AssertionError("Mutation unexpectedly accepted: " + name)
    none = score([])
    assert none["coverage"] is none["selective_error"] is none["faithful_delivery"] is None
    all_abstain = score(["explicit_abstention"] * 4)
    assert all_abstain["coverage"] == all_abstain["faithful_delivery"] == 0
    assert all_abstain["selective_error"] is None and all_abstain["false_abstention"] == 1
    mixed = score(["delivered_source_pass", "delivered_source_fail", "explicit_abstention",
                   "execution_failure", "not_attempted_or_missing"])
    assert mixed == {"eligible": 5, "accepted": 2, "coverage": .4, "selective_error": .5,
                     "faithful_delivery": .2, "false_abstention": .2,
                     "technical_failure_rate": .2, "not_attempted_rate": .2}
    assert sampled_pages("0" * 64, 1) == [1]
    assert sampled_pages("0" * 64, 3) == [1, 2, 3]
    assert sampled_pages("0" * 64, 10) == [1, 5, 8, 10]
    return {"passed": True, "rejected_split_mutations": rejected,
            "arithmetic_examples_are_not_model_results": True,
            "all_abstain_example": all_abstain, "mixed_outcome_example": mixed,
            "sampling_examples": {"one_page": [1], "three_pages": [1, 2, 3], "ten_pages": [1, 5, 8, 10]}}


def main():
    audit = read(HERE / "exposure-audit.json")
    custody = read(HERE / "holdout-custody.json")
    protocol = read(HERE / "protocol.json")
    regression = read(HERE / "regression-manifest.json")
    assert sha(HERE / "exposure-audit.json") == "d2305dde17916583504a8f3e64cf0ae3f4b977671f595443cdeb042b379fcf02"
    assert sha(HERE / "holdout-custody.json") == "bab607c1ca785fa21a0e6e682185ef2c5deb4aa5a64e148911add965b4e8f932"
    assert sha(HERE / "protocol.json") == "56e0c5f9b8a061e50765b56f1ddd7c07c09c87ba77e0c3f3430957c2202ee5fe"
    assert sha(HERE / "regression-manifest.json") == "508ad60768d8777d7d4e92666123135c4acb34da5a44cdaea5dc59c6059d4c75"
    assert sha(HERE / "independent-review.md") == "a586caf1f87ae2c8b6ef9f2d131fca5360a3fd6c1f9552a8373baa987673a118"
    validate_split(audit, custody)
    refs = {}

    def check_refs(value):
        if isinstance(value, dict):
            if "path" in value and re.fullmatch(r"[0-9a-f]{64}", value.get("sha256", "")):
                path = REPO / value["path"]
                assert path.is_file() and sha(path) == value["sha256"], path
                refs[value["path"]] = value["sha256"]
            for child in value.values():
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)

    for value in (audit, custody, regression, protocol):
        check_refs(value)
    for row in custody["documents"]:
        path = REPO / row["path"]
        with path.open("rb") as stream:
            assert stream.read(5) == b"%PDF-"
        assert path.stat().st_size == row["size_bytes"] and row["pdf_magic_valid"]
    assert sum(r["size_bytes"] for r in custody["documents"]) == custody["total_size_bytes"] == 3113292
    g1 = read(REPO / regression["registry_ref"]["path"])
    retained = regression["all_g1_cases_retained"]
    assert len(retained) == len({r["id"] for r in retained}) == 57
    assert retained == [{k: c[k] for k in retained[0]} for c in g1["cases"]]
    assert regression["all_validation_groups_retained"] == g1["coverage"] and len(g1["coverage"]) == 19
    prior = read(REPO / regression["prior_paragraph_outputs_ref"]["path"])
    assert regression["paragraph_output_ids"] == [r["id"] for r in prior["prior_17"]]
    assert len(regression["paragraph_output_ids"]) == 17
    expected_anchors = [{k: v for k, v in r.items() if k not in {"guard_decision", "guard_reason"}}
                        for r in prior["positive_anchors"]]
    assert regression["protected_positive_anchors"] == expected_anchors and len(expected_anchors) == 4
    assert not regression["historical_guard_global_adoption_allowed"]
    assert protocol["development_search"]["candidate_budget"] == 3
    assert protocol["paired_run"]["challenger_count"] == 1
    assert protocol["current_readiness"] == {
        "evaluation_protocol_frozen": True, "holdout_source_inventory_frozen": False,
        "candidate_lock_frozen": False, "applicable_behavioral_regressions_rerun_for_new_candidate": False,
        "holdout_run_permitted": False, "g2_passed": False}
    ticket = read(HERE / "ticket-update.json")
    assert ticket["comment_exact_readback"] and ticket["issue_body_exact_readback"]
    assert ticket["feature_rows_unchanged"] == 44 and ticket["issue_state"] == "OPEN"
    assert ticket["comment_url"] == "https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6193047443"
    prior_payloads = {}
    for name in ["pdf-core-g2-local-cpu-2026-10-14", "pdf-core-g2-round2-2026-10-14",
                 "pdf-core-g2-round3-2026-10-14", "pdf-core-g2-api-2026-10-14",
                 "pdf-core-g2-images-2026-10-14", "pdf-core-g2-heading-2026-10-15",
                 "pdf-core-g2-orientation-2026-10-15", "pdf-core-g2-inline-2026-10-15",
                 "pdf-core-g2-inline-api-2026-10-15", "pdf-core-g2-inline-boundary-2026-10-15"]:
        records = read(HERE.parent / name / "artifacts.json")["files"]
        for record in records:
            path = REPO / record["path"]
            assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
        prior_payloads[name] = len(records)
    assert sum(prior_payloads.values()) == 1816
    save(HERE / "selfchecks.json", selfchecks(audit, custody))
    links = 0
    human_docs = [REPORT, *HERE.glob("*.md"), *(HERE.parent / name for name in (
        "README.md", "docling-pdf-core-capability-validation-plan-2026-10-14.md",
        "docling-pdf-core-g2-pipeline-start-2026-10-14.md"))]
    for path in human_docs:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            linked = (path.parent / target.split("#")[0]).resolve()
            assert linked.exists() or linked in {HERE / "artifacts.json", HERE / "validation.json"}, (path, target)
            links += 1
    files = []
    custody_files = [REPO / r["path"] for r in custody["documents"]]
    custody_files.append(custody_files[0].parent / ".gitignore")
    for path in sorted([REPORT, *HERE.rglob("*"), *custody_files]):
        if not path.is_file() or "__pycache__" in path.parts or path.name in {"artifacts.json", "validation.json"}:
            continue
        if path.suffix in {".md", ".json", ".py", ".txt"}:
            assert not re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", path.read_text()), "Possible credential; never print matching text"
        files.append({"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size, "sha256": sha(path)})
    save(HERE / "artifacts.json", {"scope": "Evaluation protocol and metadata plus six custody PDF hashes; no PDF semantic inspection", "files": files})
    result = {"passed": True, "prior_payloads_unchanged": prior_payloads,
              "metadata_source_refs_checked": len(refs), "retained_g1_cases": 57,
              "retained_validation_groups": 19, "retained_prior_paragraph_outputs": 17,
              "protected_positive_anchors": 4, "holdout_documents": 6,
              "holdout_exposed_group_and_byte_overlap": 0,
              "holdout_content_inspected": False, "model_calls": 0,
              "holdout_run_permitted": False, "split_negative_controls": 9,
              "ticket_summary_and_body_exact_readback": True, "ticket_feature_rows_unchanged": 44,
              "scorecard_and_sampling_selfchecks": True, "local_markdown_links_checked": links,
              "payload_files": len(files), "credential_pattern_scan_clean": True}
    save(HERE / "validation.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
