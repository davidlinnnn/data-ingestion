"""Offline checks of frozen evidence; no inference, installation or network."""

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
assert sha(HERE / "inputs/input-manifest.json") == "4fd11ccacd2819d0eb44461974315f217dee12e3fc58308b28875b0964e00ccf"
prior = {}
for name in ["pdf-core-g2-local-cpu-2026-10-14", "pdf-core-g2-round2-2026-10-14",
             "pdf-core-g2-round3-2026-10-14", "pdf-core-g2-api-2026-10-14",
             "pdf-core-g2-images-2026-10-14", "pdf-core-g2-heading-2026-10-15",
             "pdf-core-g2-orientation-2026-10-15"]:
    records = read(REPO / "docs/research" / name / "artifacts.json")["files"]
    for record in records:
        path = REPO / record["path"]
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
    prior[name] = len(records)
assert sum(prior.values()) == 871

lanes = {}
for lane in ("inputs", "reinsertion"):
    manifest = read(HERE / lane / "artifact-sha256.json")
    for name, expected in manifest.items():
        assert sha(HERE / lane / name) == expected, (lane, name)
    lanes[lane] = len(manifest)
vlm_manifest = read(HERE / "vlm/artifacts.json")["files"]
for record in vlm_manifest:
    path = REPO / record["path"]
    assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
lanes["vlm"] = len(vlm_manifest)

inputs = read(HERE / "inputs/input-manifest.json")
assert not inputs["oracle_content_or_boxes_used_for_selection"]
assert inputs["counts"] == {"ordinary_paragraphs_inventoried": 28,
    "ordinary_selected_by_character_gate": 11,
    "inference_candidates_including_controls_regression": 17, "candidate_page_fragments": 19}
for source in inputs["sources"]:
    assert sha(REPO / source["source"]["path"]) == source["source"]["sha256"]
    for snapshot in source["snapshots"]:
        assert sha(REPO / snapshot["original_path"]) == snapshot["sha256"]

model = read(HERE / "vlm/verification.json")
assert model["checks"] == "passed" and model["total_model_calls"] == 22
assert model["all_last_token_eos"] and not model["any_token_cap"]
assert model["assembly_replay"]["model_calls"] == 0 and len(model["assembly_replay"]["variants"]) == 2
assert read(HERE / "reinsertion/verification.json")["passed"]
selfcheck = read(HERE / "reinsertion/selfcheck.json")
assert selfcheck["passed"] and len(selfcheck["negative_controls"]) == 7
assert read(HERE / "reinsertion/component/summary.json")["status_counts"] == {"not_applied": 17}
assert read(HERE / "reinsertion/token-aware/summary.json")["status_counts"] == {
    "structurally_applied_semantic_quality_unverified": 9, "not_applied": 8}
review = read(HERE / "review/output-review.json")
assert review["checker_sha256"] == sha(HERE / "review/check.py")
assert not review["inputs"]["errors"] and len(review["inputs"]["candidate_checks"]) == 17
assert len(review["input_pixel_checks"]["candidates"]) == 17
assert review["selfchecks"]["all_rejected"] and len(review["selfchecks"]["controls"]) == 17
assert all(review["selfchecks"]["controls"].values())
assert review["model_outputs"]["run_count"] == 22
assert all(value for key, value in review["model_outputs"].items() if key.startswith("all_"))
assert review["geometry"]["documents_checked"] == 44 and not review["geometry"]["errors"]
assert not review["reinsertion"]["errors"]
for route in ("page", "paragraph"):
    assert review["frozen_case_semantics"]["G1-E04"][route]["score"]["F14_bounded_token_binding_prose_fidelity_pass"]
ticket = read(HERE / "ticket-update.json")
assert ticket["comment_exact_readback"] and ticket["issue_body_exact_readback"]
assert ticket["feature_rows_unchanged"] == 44 and ticket["issue_state"] == "OPEN"

# Source-derived Markdown can contain example links unrelated to this experiment.
human_docs = [REPORT, HERE / "inline-primary.md", HERE / "reinsertion/README.md",
              *HERE.joinpath("review").glob("*.md"),
              *(HERE.parent / name for name in ("README.md", "docling-pdf-core-capability-validation-plan-2026-10-14.md", "docling-pdf-core-g2-pipeline-start-2026-10-14.md"))]
links = 0
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
save(HERE / "artifacts.json", {"scope": "Owned inline report and payloads, independent review and retained attempts; existing model cache and Python caches excluded", "files": files})
save(HERE / "validation.json", {"g1_and_source_hashes_unchanged": True,
    "prior_payloads_unchanged": prior, "lane_payloads_unchanged": lanes,
    "model_calls": 22, "assembly_replay_model_calls": 0, "all_eos_no_token_cap": True,
    "producer_inventory_and_input_pixels_checked": True, "reinsertion_negative_controls": 7,
    "independent_tamper_controls": 17, "independent_geometry_sidecars_checked": 44,
    "structural_application_is_not_semantic_acceptance": True,
    "ticket_summary_exact_readback_and_44_feature_rows_preserved": True,
    "credential_pattern_scan_clean": True, "local_markdown_links_checked": links,
    "payload_files": len(files), "payload_bytes": sum(r["bytes"] for r in files)})
print(json.dumps(read(HERE / "validation.json")))
