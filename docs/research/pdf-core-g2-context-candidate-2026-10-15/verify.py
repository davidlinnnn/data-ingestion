"""Verify frozen development evidence without inference or holdout PDF access."""
import ast
import hashlib
import importlib.util
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


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    experiment = read(HERE / "experiment.json")
    assert sha(HERE / "experiment.json") == "5206989bb23bd0bad73a97665e4d0913ac10c7de5089d007ebc989c501c299ca"
    execution = read(HERE / "execution-config.json")
    assert execution["registration_sha256"] == sha(HERE / "experiment.json")
    assert execution["planner_sha256"] == sha(HERE / "candidate.py")
    assert execution["preparer_sha256"] == sha(HERE / "prepare.py")
    assert execution["frozen_before_dataset_execution"]
    assert execution["render_scale"] == 3 and execution["padding_points"] == 2 and execution["stitch_gap_pixels"] == 24
    spec = importlib.util.spec_from_file_location("verified_context_candidate", HERE / "candidate.py")
    planner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(planner)
    assert planner.CONFIG == experiment["candidate_config"]
    assert read(HERE / "planner-selfchecks.json")["passed"]
    # Source-specific refs may appear in synthetic tests, never in the reusable planner.
    tree = ast.parse((HERE / "candidate.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name != "selfcheck":
            constants = [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            assert not any(re.search(r"#/(?:texts|pictures|groups)/\d+|wikiskill|seal|dgm|controls", v, re.I) for v in constants)
    prior_counts = {}
    for name in ["pdf-core-g2-local-cpu-2026-10-14", "pdf-core-g2-round2-2026-10-14",
                 "pdf-core-g2-round3-2026-10-14", "pdf-core-g2-api-2026-10-14",
                 "pdf-core-g2-images-2026-10-14", "pdf-core-g2-heading-2026-10-15",
                 "pdf-core-g2-orientation-2026-10-15", "pdf-core-g2-inline-2026-10-15",
                 "pdf-core-g2-inline-api-2026-10-15", "pdf-core-g2-inline-boundary-2026-10-15",
                 "pdf-core-g2-eval-freeze-2026-10-15"]:
        records = read(HERE.parent / name / "artifacts.json")["files"]
        checked, skipped = 0, 0
        for record in records:
            # Keep the fresh pool untouched, including its raw bytes; only its frozen metadata is checked.
            if record["path"].startswith("docs/fixtures/pdf-core-g2-holdout-") and record["path"].endswith(".pdf"):
                skipped += 1
                continue
            path = REPO / record["path"]
            assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
            checked += 1
        prior_counts[name] = {"checked": checked, "holdout_pdf_bytes_not_accessed": skipped}
    assert sum(v["checked"] for v in prior_counts.values()) == 1829
    assert sum(v["holdout_pdf_bytes_not_accessed"] for v in prior_counts.values()) == 6
    verified_refs = set()

    def check_refs(value):
        if isinstance(value, dict):
            if "path" in value and re.fullmatch(r"[0-9a-f]{64}", value.get("sha256", "")):
                assert not value["path"].startswith("docs/fixtures/pdf-core-g2-holdout-")
                path = REPO / value["path"]
                assert sha(path) == value["sha256"], path
                verified_refs.add(value["path"])
            for child in value.values():
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)

    manifest = read(HERE / "input-manifest.json")
    check_refs(manifest)
    check_refs(read(HERE / "runtime.json"))
    assert manifest["model_calls"] == manifest["holdout_reads"] == 0 and manifest["prepared_jobs"] == 36
    total_items, total_groups, total_rows = 0, 0, 0
    status_counts = {}
    for source in manifest["sources"]:
        plan = read(HERE / "plans" / (source["source"] + ".json"))
        check_refs(plan)
        raw = read(REPO / plan["provider_document_ref"]["path"])
        assert planner.plan(raw) == plan["rows"] and digest(raw) == plan["provider_canonical_sha256"]
        by_ref = {i["self_ref"]: i for key in ("texts", "pictures", "tables", "key_value_items", "form_items") for i in raw[key]}
        inventory = plan["native_item_inventory"]
        assert len(inventory) == len({r["item_ref"] for r in inventory}) == len(by_ref)
        assert {r["item_ref"] for r in inventory} == set(by_ref)
        assert all(r["original_preserved"] and r["native_item_sha256"] == digest(by_ref[r["item_ref"]]) for r in inventory)
        assert plan["groups_preserved"] == [{"item_ref": g["self_ref"], "sha256": digest(g)} for g in raw["groups"]]
        total_items += len(inventory)
        total_groups += len(raw["groups"])
        total_rows += len(plan["rows"])
        for row in plan["rows"]:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
            assert not set(row["target_item_refs"]) & set(row["context_only_refs"])
    assert (total_items, total_groups, total_rows) == (1594, 60, 816)
    assert status_counts == {"ready": 390, "abstain": 58, "unsupported": 365, "member": 3}
    for job in manifest["inputs"]:
        contract = read(REPO / job["request_contract_ref"]["path"])
        expected = dict(contract)
        saved_digest = expected.pop("input_contract_sha256")
        assert digest(expected) == saved_digest
        assert contract["status"] == "prepared_not_sent" and contract["changed_prompt_or_context_requires_new_inference"]
        assert contract["scope"]["target_item_refs"] == job["target_item_refs"]
        assert contract["scope"]["context_only_refs"] == job["context_only_refs"]
        assert hashlib.sha256(contract["prompt"].encode()).hexdigest() == contract["prompt_sha256"]
        assert any(f["role"] == "target" for f in job["fragments"])
    replay = read(HERE / "legacy-replay/results.json")
    check_refs(replay)
    assert len(replay["outcomes"]) == 17 and replay["structurally_applied"] == 11
    assert len(replay["protected_positive_anchors"]) == 4
    assert all(r["structurally_eligible"] and not r["semantic_rubric_retested"] for r in replay["protected_positive_anchors"])
    assert not replay["lexical_gate"] and not replay["candidate_context_jobs_replay_compatible"]
    assert replay["provider_graphs_and_original_model_artifacts_unchanged"]
    adapter_checks = read(HERE / "legacy-replay/selfcheck.json")
    assert adapter_checks["passed"] and len(adapter_checks["negative_controls"]) == 19
    review = read(HERE / "review/output-review.json")
    assert review["passed"]
    assert sha(HERE / "review/evaluation-contract.json") == "99cd3de3f2f91ade459b28587e5fdfa3553776463412ecd2db69bb3664201868"
    assert sha(HERE / "review/check.py") == "64265964ceb7f55355dfae2cec5bc4f913d571aaccfc3308a1ae3ea4fa4b7913"
    assert sha(HERE / "review/output-review.json") == "229b23861cd8f1ace18e323d5d7a4d4a7214e5f77e6ee8ce080f1776c986b287"
    check_refs(review)
    ticket = read(HERE / "ticket-update.json")
    assert ticket["comment_exact_readback"] and ticket["issue_body_exact_readback"]
    assert ticket["feature_rows_unchanged"] == 44 and ticket["issue_state"] == "OPEN"
    assert ticket["comment_url"] == "https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6194719552"
    links = 0
    human_docs = [REPORT, *(p for p in HERE.rglob("*.md") if p.name not in {"baseline.md", "working.md"}),
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
    save(HERE / "artifacts.json", {"scope": "Candidate1 development planning and legacy replay only; no fresh holdout access", "files": files})
    result = {"passed": True, "frozen_prior_payloads": prior_counts, "referenced_files_checked": len(verified_refs),
              "candidate_configurations_executed": 1, "native_items_preserved": total_items,
              "native_groups_preserved": total_groups, "planner_records": total_rows,
              "planner_status_counts": status_counts, "prepared_new_inputs": 36,
              "legacy_paragraph_outputs_replayed": 17, "legacy_structural_applications": 11,
              "protected_positive_anchors_structurally_eligible": 4,
              "new_model_calls": 0, "holdout_reads": 0, "selected_holdout_challenger": False,
              "g2_passed": False, "adapter_negative_controls": 19,
              "new_input_semantic_quality_verified": False, "local_markdown_links_checked": links,
              "ticket_summary_and_body_exact_readback": True, "ticket_feature_rows_unchanged": 44,
              "credential_pattern_scan_clean": True, "payload_files": len(files),
              "payload_bytes": sum(r["bytes"] for r in files)}
    save(HERE / "validation.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
