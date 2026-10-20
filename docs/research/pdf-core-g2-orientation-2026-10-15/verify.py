"""Offline integrity checks for this round; never invokes a model or network."""

import hashlib
import importlib.metadata
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REPORT = HERE.with_suffix(".md")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


assert sha(REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json") == "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
assert sha(REPO / "docs/fixtures/pdf-core-g1-controls-2026-10-14/controls.pdf") == "8ddae37b0461b3749402e44b4a40b0e65b3d6b9ad78cf2f03ed20d1950faba90"
prior = {}
for name in ["pdf-core-g2-local-cpu-2026-10-14", "pdf-core-g2-round2-2026-10-14",
             "pdf-core-g2-round3-2026-10-14", "pdf-core-g2-api-2026-10-14",
             "pdf-core-g2-images-2026-10-14", "pdf-core-g2-heading-2026-10-15"]:
    records = read(REPO / "docs/research" / name / "artifacts.json")["files"]
    for record in records:
        path = REPO / record["path"]
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
    prior[name] = len(records)

lane_files = {}
for lane in ["baseline", "normalized"]:
    manifest = read(HERE / lane / "artifact-sha256.json")
    for name, expected in manifest.items():
        assert sha(HERE / lane / name) == expected, (lane, name)
    lane_files[lane] = len(manifest)
for lane in ["orientation", "line-cls"]:
    records = read(HERE / lane / "artifacts.json")["files"]
    for record in records:
        path = REPO / record["path"]
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
    lane_files[lane] = len(records)
for lane in ["baseline", "normalized", "line-cls"]:
    for name, expected in read(HERE / lane / "frozen-inputs.json").items():
        assert sha(REPO / name) == expected, name

job_counts = {}
for lane, count in [("baseline", 7), ("orientation", 4), ("normalized", 4), ("line-cls", 2)]:
    summary = read(HERE / lane / "summary.json")
    assert sha(HERE / lane / "run.py") == summary["runner_sha256"]
    assert len(summary["jobs"]) == count
    for job in summary["jobs"]:
        assert job["exit_code"] == 0 and job["stopped"] is None
        assert job["available_before_bytes"] >= 8 * 1024**3
        assert job["sampled_tree_peak_rss_bytes"] < 6 * 1024**3
        elapsed = job.get("seconds_including_process_start_exit", job.get("wall_seconds_including_process_start_exit"))
        assert elapsed < 180
    job_counts[lane] = count

model = read(HERE / "orientation-model-integrity.json")
model_path = Path(model["local_model_path"])
assert model["matches_official_lfs"] and sha(model_path) == model["local_sha256"] == model["official_model_entry"]["lfs"]["oid"]
for record in read(HERE / "orientation/model-download.json")["files"]:
    path = model_path.parent / record["filename"]
    assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"]
orientation = read(HERE / "orientation/verification.json")
assert orientation["all_four_ocr_text_outputs_identical"] and len(orientation["normalized_image_hashes"]) == 1
assert len(orientation["results"]) == 4 and sum(r["saved_boxes_checked"] for r in orientation["results"]) == 936
comparison = read(HERE / "line-cls/comparison.json")
assert comparison["checks"] == "passed" and comparison["total_new_ocr_calls"] == 2
assert comparison["total_line_classifier_inference_calls"] == 0
normalized = read(HERE / "normalized/verification.json")
assert normalized["original_registry_and_92_baseline_files_unchanged"]
assert normalized["frozen_derived_inputs_unchanged"] and len(normalized["completed_jobs"]) == 4
review = read(HERE / "review/output-review.json")
assert review["checker_sha256"] == sha(HERE / "review/check.py")
assert len(review["self_checks"]) == 7 and all(review["self_checks"].values())
assert len(review["orientation"]) == len(review["normalized_standard_integration"]) == 4

site = REPO / "docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages"
packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions(path=[str(site)])}
assert packages["docling"] == packages["docling-slim"] == "2.102.0" and packages["docling-core"] == "2.96.0"

links = 0
# Provider Markdown contains source-example links rather than local artifact links.
for path in [REPORT, *(p for p in HERE.rglob("*.md") if not p.name.startswith("document"))]:
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        linked = (path.parent / target.split("#")[0]).resolve()
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
save(HERE / "artifacts.json", {"scope": "Owned orientation/mixed report and payloads, retained attempts and independent review; model scratch cache and Python caches excluded", "files": files})
save(HERE / "validation.json", {"g1_registry_and_source_unchanged": True, "prior_payloads_unchanged": prior,
    "lane_payloads_unchanged": lane_files, "completed_scored_jobs_or_calls": job_counts,
    "runner_input_and_guard_records_match": True, "baseline_environment_and_model_cache_preserved": True,
    "orientation_model_matches_official_lfs": True, "inverse_polygons_verified": 936,
    "independent_negative_checks": 7, "checker_sha256": review["checker_sha256"],
    "credential_pattern_scan_clean": True, "local_markdown_links_checked": links,
    "payload_files": len(files), "payload_bytes": sum(r["bytes"] for r in files)})
print(json.dumps(read(HERE / "validation.json")))
