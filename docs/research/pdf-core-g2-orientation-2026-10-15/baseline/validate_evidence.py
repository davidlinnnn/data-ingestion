"""Validate saved evidence and list exact repeated instances; performs no inference."""

import collections
import hashlib
import importlib.util
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location("frozen_rotation_baseline", HERE / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    assert run.check() == read(HERE / "frozen-inputs.json")
    summary = read(HERE / "summary.json")
    assert len(summary["jobs"]) == 7
    inventory = []
    for job in summary["jobs"]:
        assert job["execution_status"] == "completed" and job["stopped"] is None
        assert job["sampled_tree_peak_rss_bytes"] < run.LIMIT
        folder = HERE / "runs" / job["name"]
        document = read(folder / "document.json")
        raw = read(folder / "conversion-result.json")
        assert DoclingDocument.model_validate(raw["document"]) == DoclingDocument.model_validate(document)
        page = job["original_physical_page"]
        assert set(document["pages"]) == {str(page)}
        method, producer = read(folder / "method.json"), read(folder / "producer.json")
        options = method["options"]
        assert options["accelerator_options"] == {
            "device": "cpu", "num_threads": 4, "cuda_use_flash_attention2": False}
        assert options["layout_batch_size"] == options["ocr_batch_size"] == options["table_batch_size"] == 1
        assert producer["effective_use_cls"] is True
        assert all(s["providers"] == ["CPUExecutionProvider"] for s in producer["actual_sessions"].values())
        cells = read(folder / "cell-merge.json")
        assert cells["physical_page_1based"] == page
        calls = list(folder.glob("raw-ocr-calls/*.raw.json"))
        assert calls
        for call in calls:
            data = read(call)
            assert data["source_mapping"]["physical_page_1based"] == page
            assert len(data["recognizer_texts"]) == len(data["recognizer_scores"])
            assert len(data["recognizer_texts"]) == len(data["detector_boxes_crop_pixels"])
        groups = collections.defaultdict(list)
        for text in document["texts"]:
            candidates = [{"index": cell["index"], "from_ocr": cell["from_ocr"], "rect": cell["rect"]}
                          for cell in cells["merged_after"] if cell["text"] == text["orig"]]
            groups[text["text"]].append({"self_ref": text["self_ref"], "parent": text["parent"],
                "provenance": text["prov"], "same_text_cell_candidates": candidates})
        inventory.append({"job": job["name"], "physical_page_1based": page,
            "native_cells_before": len(cells["native_before"]),
            "ocr_cells_before": len(cells["ocr_before"]),
            "merged_cells_after": len(cells["merged_after"]),
            "merged_cells_by_origin": dict(collections.Counter(c["from_ocr"] for c in cells["merged_after"])),
            "raw_ocr_calls": len(calls),
            "document_text_instances": dict(groups),
            "exact_duplicate_document_texts": {t: instances for t, instances in groups.items() if len(instances) > 1},
            "pictures": [{k: v for k, v in p.items() if k != "image"} for p in document["pictures"]],
            "markdown_image_markers": (folder / "document.md").read_text().count("<!-- image -->")})
    sources = REPO / "docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages"
    source_paths = ["docling/models/stages/ocr/rapid_ocr_model.py", "docling/models/base_ocr_model.py",
        "docling/backend/docling_parse_backend.py", "docling/document_converter.py",
        "rapidocr/main.py", "rapidocr/config.yaml", "rapidocr/ch_ppocr_rec/main.py",
        "pypdfium2/_helpers/page.py"]
    result = {"scope": "Evidence integrity and exact-instance inventory only; no semantic pass verdict",
        "frozen_inputs_unchanged": True, "seven_completed_jobs": True,
        "installed_primary_source_sha256": {p: sha(sources / p) for p in source_paths},
        "instance_policy": "Exact text only; same-text cell candidates are not an authoritative origin alignment",
        "jobs": inventory}
    (HERE / "evidence-inventory.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"validated_jobs": len(inventory), "frozen_inputs_unchanged": True}))


if __name__ == "__main__":
    main()
