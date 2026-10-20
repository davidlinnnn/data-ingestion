"""Freeze the complete old restored WikiSkill input without conversion or schema rewriting."""

import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SOURCE = REPO / "docs/fixtures/agent-self-evolution-pilot-2026-10-11/01-2608.27454v1.pdf"
OLD = REPO / "docs/research/paper-pdf-functional-2026-10-11/remaining-group5/01-2608.27454v1"
OUT = HERE / "wikiskill"
SOURCE_SHA = "65afc6e12f6f707483fe1b79a97ab67c03abf4b4992f82fde03eb7b8d9ad4a69"
DOC_SHA = "4f0693659e6bb1dc8d13456f17a9d8c0a4b0604ed682cc4eee7d0bdaf63f4371"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert sha(SOURCE) == SOURCE_SHA
    assert sha(OLD / "native/document.json") == DOC_SHA
    method = json.loads((OLD / "native/method.json").read_text())
    metrics = json.loads((OLD / "native/metrics.json").read_text())
    complete = json.loads((OLD / "merged/complete.json").read_text())
    document = json.loads((OLD / "native/document.json").read_text())
    assert metrics["source_sha256"] == complete["source_sha256"] == SOURCE_SHA
    assert metrics["mode"] == "restore"
    assert method["continuation"]["version"] == "column-edge-continuation-v3"
    assert method["options"]["accelerator_options"]["device"] == "cpu"
    assert method["options"]["generate_parsed_pages"] is False
    assert set(document["pages"]) == {str(i) for i in range(1, 29)}
    assert complete["method_sha256"] == sha(OLD / "native/method.json")
    files = []
    OUT.mkdir(exist_ok=False)
    for source, name in [(OLD / "native/document.json", "document.json"),
                         (OLD / "native/method.json", "method.json"),
                         (OLD / "native/metrics.json", "metrics.json"),
                         (OLD / "merged/complete.json", "checkpoint-complete.json")]:
        target = OUT / name
        shutil.copyfile(source, target)
        assert sha(source) == sha(target)
        files.append({"original_path": str(source.relative_to(REPO)),
                      "snapshot_path": str(target.relative_to(REPO)),
                      "sha256": sha(target), "bytes": target.stat().st_size,
                      "byte_identical": True})
    checkpoints = []
    for entry in complete["pages"]:
        path = OLD / "merged/checkpoints" / entry["file"]
        assert sha(path) == entry["sha256"]
        data = json.loads(path.read_text())
        assert data["source_sha256"] == SOURCE_SHA
        assert data["method_sha256"] == complete["method_sha256"]
        checkpoints.append({"original_path": str(path.relative_to(REPO)),
                            "sha256": sha(path), "original_physical_page": data["page_no"]})
    assert [row["original_physical_page"] for row in checkpoints] == list(range(1, 29))
    manifest = {
        "source_id": "SRC01", "source_path": str(SOURCE.relative_to(REPO)),
        "source_sha256": SOURCE_SHA, "source_pages": 28,
        "baseline_kind": "old_complete_docling_2.102_core_2.96_continuation_v3_checkpoint_restore",
        "baseline_is_fresh_stock_2_132_conversion": False,
        "baseline_original_mode": metrics["mode"],
        "baseline_continuation_method": method["continuation"],
        "baseline_document_schema_version": document["version"],
        "baseline_pages": list(range(1, 29)),
        "review_target_original_physical_pages": [1, 4, 5, 7, 19],
        "source_page_remap": [{"document_page_no": i, "original_physical_page": i}
                              for i in range(1, 29)],
        "snapshots": files, "assembled_page_checkpoint_references": checkpoints,
        "parsed_pages_in_old_baseline": False,
        "old_checkpoint_style_limit": "TextCell serialization retains boxes and text but not PdfTextCell font_name",
        "native_backend_reparse": "Separately captured by candidate runtime from same complete source PDF; no layout/OCR/table rerun",
        "new_inference_performed_by_preparation": False,
        "new_conversion_performed_by_preparation": False,
        "preparation_script_sha256": sha(Path(__file__)),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    assert sha(OLD / "native/document.json") == DOC_SHA
    print(json.dumps({"manifest": str(OUT / "manifest.json"), "full_pages": 28,
                      "document_sha256": DOC_SHA, "snapshot_files": len(files)}))


if __name__ == "__main__":
    main()
