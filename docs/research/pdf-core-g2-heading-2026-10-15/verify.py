"""Offline payload and evidence checks; no PDF conversion, model, or API execution."""

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
prior = {}
for name in ["pdf-core-g2-local-cpu-2026-10-14", "pdf-core-g2-round2-2026-10-14",
             "pdf-core-g2-round3-2026-10-14", "pdf-core-g2-api-2026-10-14",
             "pdf-core-g2-images-2026-10-14"]:
    records = read(REPO / "docs/research" / name / "artifacts.json")["files"]
    for record in records:
        path = REPO / record["path"]
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
    prior[name] = len(records)

inputs = read(HERE / "inputs/validation.json")
assert inputs["passed"] and inputs["input_manifest_sha256"] == sha(HERE / "inputs/input-manifest.json")
for source in read(HERE / "inputs/input-manifest.json")["sources"]:
    assert sha(REPO / source["source_path"]) == source["source_sha256"]
    for record in source.get("snapshots", []):
        assert sha(REPO / record["original_path"]) == sha(REPO / record["snapshot_path"]) == record["sha256"]

evidence = read(HERE / "runtime/runtime-evidence.json")
for name, record in evidence["source_checks"].items():
    assert record["identical"]
    assert sha(HERE / "runtime/source" / name) == sha(Path(record["installed_path"])) == record["tag_sha256"]
for lane in ["wikiskill-final", "controls-p1-final"]:
    folder = HERE / "runtime" / lane
    for name, expected in evidence["checks"][lane]["final_output_hashes"].items():
        assert sha(folder / name) == expected, (lane, name)
    bounded = read(folder / "bounded-execution.json")
    assert bounded["status"] == "success" and bounded["stop_reason"] is None
    assert bounded["available_memory_bytes_prelaunch"] >= 8 * 1024**3
    assert bounded["seconds"] < 180 and bounded["max_sampled_rss_bytes"] < 6 * 1024**3
    assert len(bounded["children"]) == 2 and all(c["exit_code"] == 0 for c in bounded["children"])
    for name, expected in bounded["runner_sha256"].items():
        assert sha(HERE / "runtime" / name) == expected
    manifest = read(folder / "input-manifest.json")
    for name, expected in manifest["input_hashes"].items():
        assert sha(folder / name) == expected
    assert sha(folder / "outline.json") == manifest["outline_sha256"]
    reload = read(folder / "reload-equivalence.json")
    assert reload["document_json_equal"] and reload["markdown_equal"]
    assert reload["pdf_font_cells_after_reload"] == {n: d["pdf_font_cells"] for n, d in manifest["textline_cells"].items()}
    for suffix in ["json", "md"]:
        assert (folder / f"document-fresh.{suffix}").read_bytes() == (folder / f"document-reloaded.{suffix}").read_bytes()

review = read(HERE / "review/output-review.json")
assert review["checker_sha256"] == sha(HERE / "review/check.py")
baseline_site = REPO / "docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages"
baseline = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions(path=[str(baseline_site)])}
assert baseline["docling"] == baseline["docling-slim"] == "2.102.0" and baseline["docling-core"] == "2.96.0"

links = 0
# Provider Markdown contains source-document example links, not local artifact links.
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
    if path.suffix not in {".png", ".pdf"}:
        assert not re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", path.read_text()), "Possible credential; never print matching text"
    files.append({"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size, "sha256": sha(path)})
save(HERE / "artifacts.json", {"scope": "Heading report, inputs, official source/runtime evidence, final runs, retained attempts and independent review; excludes scratch venv/cache and Python caches", "files": files})
save(HERE / "validation.json", {"g1_registry_unchanged": True, "prior_payloads_unchanged": prior,
    "input_manifest_and_source_snapshots_match": True, "official_installed_sources_match_tag": True,
    "final_execution_runner_and_output_hashes_match": True, "two_bounded_cpu_stage_lanes_completed": True,
    "persisted_stage_inputs_preserve_fonts_json_and_markdown": True, "baseline_docling_2_102_core_2_96_preserved": True,
    "independent_checker_sha256": review["checker_sha256"], "credential_pattern_scan_clean": True,
    "local_markdown_links_checked": links, "payload_files": len(files), "payload_bytes": sum(r["bytes"] for r in files)})
print(json.dumps(read(HERE / "validation.json")))
