"""Verify frozen heading-stage inputs; no PDF parsing or model execution."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTROL = HERE / "controls/runs/controls-p1"
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def exported(value):
    # Docling save_as_json uses aliases and excludes None; preserve the raw provider result separately.
    if isinstance(value, dict):
        return {("$ref" if key == "cref" else key): exported(item)
                for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [exported(item) for item in value]
    return value


def main():
    wiki = read(HERE / "wikiskill/manifest.json")
    source = next(s for s in read(REGISTRY)["sources"] if s["id"] == "SRC05")
    assert sha(REPO / wiki["source_path"]) == wiki["source_sha256"]
    for row in wiki["snapshots"]:
        assert sha(REPO / row["original_path"]) == row["sha256"]
        assert sha(REPO / row["snapshot_path"]) == row["sha256"]
    for row in wiki["assembled_page_checkpoint_references"]:
        assert sha(REPO / row["original_path"]) == row["sha256"]
    assert sha(REPO / source["path"]) == source["sha256"]
    raw = read(CONTROL / "conversion-result.json")
    document = read(CONTROL / "document.json")
    method = read(CONTROL / "method.json")
    metrics = read(CONTROL / "metrics.json")
    summary = read(HERE / "controls/summary.json")
    assert raw["status"] == "success" and raw["errors"] == []
    assert [p["page_no"] for p in raw["pages"]] == [1]
    assert all(p["parsed_page"] is None for p in raw["pages"])
    assert set(document["pages"]) == {"1"}
    assert exported(raw["document"]) == document
    assert method["packages"]["docling"] == "2.102.0"
    assert method["packages"]["docling-core"] == "2.96.0"
    assert method["options"]["accelerator_options"] == {
        "cuda_use_flash_attention2": False, "device": "cpu", "num_threads": 4}
    assert all(method["options"][key] == 1 for key in
               ("layout_batch_size", "ocr_batch_size", "table_batch_size"))
    assert method["options"]["do_ocr"] is False
    assert method["options"]["generate_parsed_pages"] is False
    assert metrics["source_sha256"] == source["sha256"]
    assert metrics["document_sha256"] == sha(CONTROL / "document.json")
    assert metrics["mode"] == "baseline" and metrics["page_stage_inputs"]["LayoutModel"] == 1
    assert summary["execution_status"] == "completed" and summary["exit_code"] == 0
    assert summary["stopped"] is None
    assert summary["offline"] is True and summary["device"] == "cpu"
    assert summary["sampled_tree_peak_rss_bytes"] < summary["sampled_tree_rss_stop_bytes"]
    files = [{"path": str(path.relative_to(REPO)), "sha256": sha(path), "bytes": path.stat().st_size}
             for path in [CONTROL / name for name in
                          ("conversion-result.json", "document.json", "method.json", "metrics.json",
                           "events.jsonl", "document.md", "child.log")]]
    control = {"source_id": "SRC05", "source_path": source["path"], "source_sha256": source["sha256"],
               "source_pages": 8, "baseline_kind": "new_bounded_stock_docling_2.102_core_2.96_cpu_conversion",
               "baseline_pages": [1], "review_target_original_physical_pages": [1],
               "source_page_remap": [{"document_page_no": 1, "original_physical_page": 1}],
               "result_captured_before_document_exports": True,
               "full_provider_result_path": str((CONTROL / "conversion-result.json").relative_to(REPO)),
               "parsed_pages_in_old_baseline": False,
               "raw_provider_document_equals_export_after_alias_and_none_rules": True,
               "files": files, "resource_summary": summary}
    manifest = {"format": "g2-heading-stage-inputs-v1", "registry_path": str(REGISTRY.relative_to(REPO)),
                "registry_sha256": sha(REGISTRY), "sources": [wiki, control],
                "method_boundary": "Candidate heading stage replays complete old baseline documents with separately captured native parsed pages/outline; not a fresh Docling 2.132 pipeline comparison",
                "original_json_preserved": True,
                "source_pages_remain_original_physical_numbers": True,
                "verification_script_sha256": sha(Path(__file__))}
    (HERE / "input-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    validation = {"passed": True, "frozen_source_hashes_match": True, "wikiskill_pages": 28,
                  "wikiskill_original_and_snapshot_sha256": wiki["snapshots"][0]["sha256"],
                  "wikiskill_all_28_checkpoint_hashes_match": True,
                  "controls_full_provider_result_sha256": sha(CONTROL / "conversion-result.json"),
                  "controls_export_document_sha256": sha(CONTROL / "document.json"),
                  "controls_original_physical_pages": [1],
                  "controls_raw_export_document_equivalent": True,
                  "controls_cpu_four_threads_batch_one_offline": True,
                  "input_manifest_sha256": sha(HERE / "input-manifest.json")}
    (HERE / "validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    print(json.dumps(validation))


if __name__ == "__main__":
    main()
