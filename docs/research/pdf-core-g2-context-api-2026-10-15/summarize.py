"""Keep raw source verdicts, parser outcomes and unattempted scope as separate measures."""
import collections
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def read(path):
    return json.loads(path.read_text())


def ref(path):
    return {"path": str(path.relative_to(REPO)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    a_path, b_path = HERE / "review-wiki-dgm/reviewresults.json", HERE / "review-seal-controls/results.json"
    a, b = read(a_path), read(b_path)
    rows = a["results"] + b["jobs"]
    identities = [(r["source"], r["job_id"]) for r in rows]
    manifest = read(REPO / "docs/research/pdf-core-g2-context-candidate-2026-10-15/input-manifest.json")
    assert len(rows) == len(set(identities)) == 36
    assert set(identities) == {(r["source"], r["job_id"]) for r in manifest["inputs"]}
    assert all(r["sourcegradable"] for r in rows)
    raw = dict(collections.Counter(r["status"] for r in rows))
    assert raw == {"pass": 25, "minor": 5, "material": 6}
    integration = read(HERE / "integration/results.json")
    structural = {(r["source"], r["job_id"]): r for r in integration["outcomes"]}
    assert len(structural) == 36 and integration["structurally_applied"] == 34
    prepared = []
    for row in rows:
        identity = row["source"], row["job_id"]
        prepared.append({"source": row["source"], "job_id": row["job_id"],
                         "raw_source_status": row["status"],
                         "reviewer_full_target_flag": row["full_target_source_pass"],
                         "structural_status": structural[identity]["status"],
                         "source_review_ref": ref(a_path if row["source"] in {"wikiskill", "dgm"} else b_path)})
    native_plan = read(REPO / "docs/research/pdf-core-g2-context-candidate-2026-10-15/plans/seal.json")
    selected_pages = {3, 4}
    document = read(REPO / native_plan["provider_document_ref"]["path"])
    by_ref = {r["self_ref"]: r for r in document["texts"]}
    unprepared = [r for r in native_plan["rows"] if r["status"] == "abstain"
                  and any(p["page_no"] in selected_pages for p in by_ref[r["target_item_refs"][0]].get("prov", []))]
    assert len(unprepared) == 5
    assert {r["target_item_refs"][0] for r in unprepared} == {f"#/texts/{i}" for i in (33, 34, 48, 50, 51)}
    by_source = {}
    for source in ("wikiskill", "dgm", "seal", "controls"):
        selected = [r for r in rows if r["source"] == source]
        by_source[source] = {"prepared_requests": len(selected),
            "raw_source_status_counts": dict(collections.Counter(r["status"] for r in selected)),
            "structurally_applied": sum(structural[(r["source"], r["job_id"])]["status"] == "structurally_applied_semantics_unverified" for r in selected)}
    content = sum(r["source_content_words_tokens_and_values_pass"] for r in a["results"])
    content += sum(r["complete_visible_content_and_math_meaning_pass"] for r in b["jobs"])
    assert content == 32
    result = {"scope": "Candidate1 fresh development results only; no unseen test or selected profile",
        "source_review_refs": [ref(a_path), ref(b_path)], "integration_ref": ref(HERE / "integration/results.json"),
        "summarizer_ref": ref(Path(__file__).resolve()),
        "prepared_requests": 36, "source_gradable_prepared_targets": 36,
        "raw_source_status_counts": raw, "visible_content_and_math_meaning_pass": {"numerator": content, "denominator": 36,
            "limit": "Excludes typed/source-block delivery requirements; not full canonical success"},
        "source_verdict_limit": "Raw pass/minor labels preserve each pre-output rubric. Extra SE-typing annotations differ from original G1-E13 policy. Do not pool reviewer_full_target_flag as a uniform acceptance metric.",
        "reviewer_full_target_flags_by_shard": {"wiki_dgm": sum(r["full_target_source_pass"] for r in a["results"]),
                                                "seal_controls": sum(r["full_target_source_pass"] for r in b["jobs"])},
        "structural_delivery": {"numerator": 34, "denominator": 36, "strict_parse_failures": 2,
            "limit": "Structure only; includes source-wrong results and provides no Canonical Acceptance"},
        "selected_logical_work_scope": {"total": 41, "prepared_attempted": 36, "not_attempted": 5,
            "member_refs_not_double_counted": 3, "all_source_clear_unprepared": True,
            "unprepared": [{"source": "seal", "target_item_refs": r["target_item_refs"], "reason": r["reason"]} for r in unprepared]},
        "context_sensitive_requests": 2, "observed_context_leakage": 0,
        "by_source": by_source, "prepared_outcomes": prepared,
        "new_candidate_configuration": False, "model_reruns": 0, "holdout_reads": 0,
        "selected_holdout_challenger": False, "canonical_acceptance": False, "g2_passed": False}
    (HERE / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: result[k] for k in ("prepared_requests", "raw_source_status_counts",
        "visible_content_and_math_meaning_pass", "structural_delivery", "selected_logical_work_scope", "by_source")}))


if __name__ == "__main__":
    main()
