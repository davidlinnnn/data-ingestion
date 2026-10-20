"""Read-only boundary checks plus one no-inference geometry counterfactual."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image
from docling.models.base_ocr_model import BaseOcrModel
from docling_core.types.doc import BoundingBox, Size

from run import HERE, OLD, verify, write
from check import inspect


def read(path):
    return json.loads(Path(path).read_text())


def analyze():
    verify()
    live = HERE / "live"
    trace = live / "trace"
    raw = read(trace / "layout-clusters-001.json")
    dedup = read(trace / "ocr-dedup-001.json")
    actual = read(trace / "ocr-rects-001.json")
    engine = read(trace / "ocr-engine-001.json")
    old, new = read(OLD / "S0/scan/result.json"), read(live / "result.json")
    assert dedup["candidates"] == [c["bbox"] for c in raw["clusters"]]
    assert actual["rects"] == dedup["rects"]
    center = raw["page_size"]["width"] / 2
    left = [c for c in raw["clusters"] if c["bbox"]["r"] < center]
    right = [c for c in raw["clusters"] if c["bbox"]["l"] > center]
    assert len(left) + len(right) == len(raw["clusters"]), "raw layout also crosses gutter"
    page_size = Size.model_validate(dedup["page_size"])
    boxes = [BoundingBox.model_validate(v) for v in dedup["candidates"]]
    replay = {}
    for dilation in (20, 0):
        coverage, rects = BaseOcrModel._deduplicate_rects(SimpleNamespace(), page_size, boxes, dilation_size=dilation)
        replay[str(dilation)] = {"coverage": coverage, "rects": [b.model_dump(mode="json") for b in rects]}
    assert replay["20"]["rects"] == actual["rects"]
    assert len(replay["20"]["rects"]) == 1
    assert all(not (b["l"] < center < b["r"]) for b in replay["0"]["rects"])
    image = np.load(trace / "ocr-engine-001.npy", allow_pickle=False)
    assert list(image.shape) == engine["input_shape"]
    assert hashlib.sha256(image.tobytes()).hexdigest() == engine["input_pixel_sha256"]
    np.testing.assert_array_equal(image, np.asarray(Image.open(trace / "ocr-engine-001.png")))
    rect = actual["rects"][0]
    assert image.shape[:2] == (round((rect["b"]-rect["t"])*actual["scale"]), round((rect["r"]-rect["l"])*actual["scale"]))
    mixed = [i for i, text in enumerate(engine["texts"]) if "or LLMs" in text and "introduced by" in text]
    assert mixed, "raw OCR no longer reproduces exact mixed source line"
    before = read(trace / "ocr-cells-before-merge-001.json")
    after = read(trace / "ocr-cells-after-merge-001.json")
    assert before == after, "PDF merge changes cells and needs separate analysis"
    preservation = {
        "parsed_cells_equal": old["pages"][0]["parsed_page"]["textline_cells"] == new["pages"][0]["parsed_page"]["textline_cells"],
        "postprocessed_layout_equal": old["pages"][0]["predictions"]["layout"] == new["pages"][0]["predictions"]["layout"],
        "assembled_page_equal": old["pages"][0]["assembled"] == new["pages"][0]["assembled"],
        "provider_document_equal": old["document"] == new["document"],
        "markdown_bytes_equal": (OLD / "S0/scan/document.md").read_bytes() == (live / "document.md").read_bytes()}
    assert all(preservation.values()), "instrumented output differs from original case"
    verdict = inspect(new)
    assert not verdict["paragraph_integrity_pass"] and verdict["foror_present"]
    result = {"raw_cluster_count": len(raw["clusters"]), "left_clusters": len(left), "right_clusters": len(right),
        "raw_cross_column_clusters": 0,
        "minimum_column_gap_points": min(c["bbox"]["l"] for c in right)-max(c["bbox"]["r"] for c in left),
        "dedup": replay, "actual_crop_width_height": [image.shape[1], image.shape[0]],
        "raw_OCR_lines": len(engine["texts"]),
        "raw_mixed_lines": [{"index": i, "text": engine["texts"][i], "quad_crop_pixels": engine["boxes"][i]} for i in mixed],
        "PDF_merge_cells_unchanged": True, "OCR_cell_count": len(before),
        "matches_original_S0": preservation, "paragraph_verdict": verdict,
        "counterfactual_scope": "dilation=0 geometry only; no OCR run on these 15 rectangles; not a selected fix",
        "inference_scope": "one unchanged S0 conversion; no version/model/options comparison"}
    return result


if __name__ == "__main__":
    result = analyze()
    if sys.argv[1:] == ["--check"]:
        assert result == read(HERE / "analysis.json"), "saved analysis changed"
    elif not sys.argv[1:]:
        write(HERE / "analysis.json", result)
    else:
        raise SystemExit("use no arguments once, or --check for read-only replay")
    print(json.dumps({"raw_clusters": result["raw_cluster_count"], "raw_cross_column": 0,
        "rects_default20": len(result["dedup"]["20"]["rects"]),
        "rects_offline0": len(result["dedup"]["0"]["rects"]),
        "raw_mixed_line_indices": [v["index"] for v in result["raw_mixed_lines"]],
        "original_S0_preserved": all(result["matches_original_S0"].values())}))
