"""Check this bounded repair and all frozen earlier evidence offline."""

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
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


assert sha(REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json") == "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
assert sha(HERE / "inputs/input-manifest.json") == "9cbaf2d1e31dc8fca9820c75f5c7b14d3a08f4bf8909698e39f3f6466856e22b"
prior = {}
for name in ["pdf-core-g2-local-cpu-2026-10-14", "pdf-core-g2-round2-2026-10-14",
             "pdf-core-g2-round3-2026-10-14", "pdf-core-g2-api-2026-10-14",
             "pdf-core-g2-images-2026-10-14", "pdf-core-g2-heading-2026-10-15",
             "pdf-core-g2-orientation-2026-10-15", "pdf-core-g2-inline-2026-10-15",
             "pdf-core-g2-inline-api-2026-10-15"]:
    records = read(REPO / "docs/research" / name / "artifacts.json")["files"]
    for record in records:
        path = REPO / record["path"]
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
    prior[name] = len(records)
assert sum(prior.values()) == 1717
lanes = {}
for lane in ("inputs", "parsed", "reinsertion", "regression"):
    manifest = read(HERE / lane / "artifact-sha256.json")
    for name, expected in manifest.items():
        assert sha(HERE / lane / name) == expected, (lane, name)
    lanes[lane] = len(manifest)
for record in read(HERE / "source-audit.json")["source_files"]:
    assert sha(REPO / record["path"]) == record["sha256"]

api = read(HERE / "api/verification.json")
assert api["checks"] == "passed" and api["selected"] == api["observed_responses"] == 6
assert api["all_selected_completed_contract_valid"]
for key, name in [("verifier_sha256", "api/verify.py"), ("runner_sha256", "api/run.py"),
                  ("method_sha256", "api/method.json"), ("observations_sha256", "api/observations.json")]:
    assert api[key] == sha(HERE / name)
observations = read(HERE / "api/observations.json")
assert len(observations) == 6 and len({r["request_id"] for r in observations}) == 6
assert all(r["http_status"] == 200 and r["finish_reason"] == "stop" and r["attempts"] == 1 for r in observations)
assert {r["returned_model"] for r in observations} == {"gpt-6-luna"}
for lane in ("parsed", "reinsertion"):
    assert read(HERE / lane / "selfcheck.json")["passed"]
summary = read(HERE / "reinsertion/summary.json")
assert summary["proposal_count"] == 8 and summary["status_counts"] == {
    "applied_model_structure_semantics_unverified": 4, "not_applied": 2,
    "applied_native_boundary_only": 1, "applied_frozen_role_override": 1}
assert summary["adapter_ref"]["sha256"] == sha(HERE / "reinsertion/apply.py")
review = read(HERE / "review/output-review.json")
assert review["checker_sha256"] == sha(HERE / "review/check.py")
assert review["completed_runs"] == review["expected_runs"] == 6
assert review["parsed"]["documents_checked"] == 6
assert review["negative_control_count"] == 21
assert review["selfchecks"]["all_rejected"] and review["integration_selfchecks"]["all_rejected"]
assert review["working"]["native34_all_characters_and_title_and_continuation_once"]
assert not review["working"]["native34_F13_completion_claim"]
assert review["working"]["native32_and_context33_and_algorithm_items35_to44_unchanged"]
assert review["working"]["raw_provider_graph_and_all_assets_unchanged"]
regression = read(HERE / "regression/results.json")
assert regression["runner_sha256"] == sha(HERE / "regression/regression.py")
assert regression["guard_ref"]["sha256"] == sha(HERE / "reinsertion/apply.py")
assert regression["decision"] == "do_not_promote_as_global_rejection_gate"
assert not regression["global_adoption_allowed"] and regression["no_guard_regex_or_threshold_changes"]
assert regression["prior_17_summary"]["selected"] == 17
positive = regression["existing_positive_anchor_summary"]
assert positive["review_positive_anchors"] == 4 and positive["guard_passes"] == positive["false_abstentions"] == 2
assert positive["all_existing_positive_labels_retained"]
assert regression["frozen_hash_checks"]["all_passed"] and read(HERE / "regression/selfchecks.json")["passed"]
ticket = read(HERE / "ticket-update.json")
assert ticket["comment_exact_readback"] and ticket["issue_body_exact_readback"]
assert ticket["feature_rows_unchanged"] == 44 and ticket["issue_state"] == "OPEN"
assert ticket["comment_url"] == "https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6192739352"

links = 0
human_docs = [REPORT, *(p for p in HERE.rglob("*.md") if p.name not in {"document.md", "working.md", "baseline.md"}),
    *(HERE.parent / name for name in ("README.md", "docling-pdf-core-capability-validation-plan-2026-10-14.md", "docling-pdf-core-g2-pipeline-start-2026-10-14.md"))]
for path in human_docs:
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        target = re.sub(r":\d+$", "", target.split("#")[0])
        linked = (path.parent / target).resolve()
        assert linked.exists() or linked in {HERE / "artifacts.json", HERE / "validation.json"}, (path, target)
        links += 1

files = []
for path in sorted([REPORT, *HERE.rglob("*")]):
    if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts:
        continue
    if path in {HERE / "artifacts.json", HERE / "validation.json"}:
        continue
    if path.suffix in {".md", ".json", ".jsonl", ".log", ".py", ".yaml", ".yml", ".txt", ".toml"}:
        assert not re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", path.read_text()), "Possible credential; never print matching text"
    files.append({"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size, "sha256": sha(path)})
save(HERE / "artifacts.json", {"scope": "Owned boundary report and payloads; frozen prior evidence referenced unchanged; Python caches excluded", "files": files})
save(HERE / "validation.json", {"g1_registry_and_prior_payloads_unchanged": prior,
    "lane_payloads_unchanged": lanes, "new_context_api_calls_one_attempt_each": 6,
    "schema_valid_does_not_establish_semantic_quality": True,
    "independent_negative_controls": 21, "old_output_shadow_regressions": 17,
    "positive_anchors_retained_by_shadow_guard": "2/4; false abstentions retained and global gate rejected",
    "token_guard_global_adoption_allowed": False,
    "ticket_summary_and_body_exact_readback": True, "ticket_feature_rows_unchanged": 44,
    "working_proposals": summary["status_counts"], "credential_pattern_scan_clean": True,
    "local_markdown_links_checked": links, "payload_files": len(files),
    "payload_bytes": sum(r["bytes"] for r in files)})
print(json.dumps(read(HERE / "validation.json")))
