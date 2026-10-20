"""Check saved evidence and associate the five central oracle locations only."""

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized(text):
    return re.sub(r"\s+", "", text.translate(str.maketrans({"“": '"', "”": '"', "＂": '"'})))


registry = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
data = json.loads(registry.read_text())
case = next(c for c in data["cases"] if c["id"] == "G1-O01")
region = case["details"]["region"]
summary = json.loads((HERE / "summary.json").read_text())
assert sha(registry) == summary["registry_sha256"]
assert sha(HERE / "run.py") == summary["runner_sha256"]
assert len(summary["jobs"]) == 3
reviews = []
for row in summary["jobs"]:
    assert row["exit_code"] == 0 and row["stopped"] is None
    folder = HERE / "runs" / row["job"]
    raw = json.loads((folder / "raw-stages.json").read_text())
    final = json.loads((folder / "ocr.json").read_text())
    producer = json.loads((folder / "producer.json").read_text())
    mapping = json.loads((folder / "source-mapping.json").read_text())
    assert sha(REPO / mapping["source_path"]) == mapping["source_sha256"]
    assert sha(folder / "figure.png") == final["crop_sha256"]
    assert all(s["providers"] == ["CPUExecutionProvider"] and s["intra_op_num_threads"] == 4
               and s["inter_op_num_threads"] == 1 for s in producer["actual_sessions"].values())
    assert producer["resolved_config"]["Rec"]["rec_batch_num"] == 1
    assert producer["resolved_config"]["Cls"]["cls_batch_num"] == 1
    for name, digest in producer["model_sha256"].items():
        model = Path(producer["params"][next(k for k, v in producer["params"].items()
                                               if k.endswith("model_path") and Path(v).name == name)])
        assert sha(model) == digest
    assert len(raw["detector_boxes_crop_pixels"]) == len(raw["recognizer_texts"]) == len(raw["recognizer_scores"])
    transform = mapping["pixel_to_pdf_top_left"]
    placement = region["image_placement_pdf_points_top_left"]
    sx, sy = (placement[2]-placement[0])/1262, (placement[3]-placement[1])/731
    items = []
    for item in case["details"]["expected"]["items"]:
        b = item["region_relative_bbox_px_top_left"]
        expected = [placement[0]+(region["bbox"][0]+b[0])*sx,
                    placement[1]+(region["bbox"][1]+b[1])*sy,
                    placement[0]+(region["bbox"][0]+b[2])*sx,
                    placement[1]+(region["bbox"][1]+b[3])*sy]
        matches = []
        for i, (box, text, score) in enumerate(zip(raw["detector_boxes_crop_pixels"],
                                                  raw["recognizer_texts"], raw["recognizer_scores"])):
            x = sum(p[0] for p in box)/4*transform["x_scale"]+transform["x_offset"]
            y = sum(p[1] for p in box)/4*transform["y_scale"]+transform["y_offset"]
            # Source envelopes are approximate: this associates locations, not an IoU quality metric.
            if expected[0] <= x <= expected[2] and expected[1] <= y <= expected[3]:
                matches.append({"raw_index": i, "text": text, "score": score,
                                "box_crop_pixels": box, "center_pdf_top_left_points": [x, y]})
        assert len(matches) == 1, (row["job"], item["id"], matches)
        match = matches[0]
        assert match["text"] == "" or match["text"] in final["texts"]
        verdict = "exact_after_allowed_normalization" if normalized(match["text"]) == normalized(item["text"]) else (
            "recognizer_empty_removed_by_library" if not match["text"] else "recognizer_mismatch")
        items.append({"id": item["id"], "expected": item["text"], "expected_pdf_envelope": expected,
                      "observation": match, "verdict": verdict})
    reviews.append({"job": row["job"], "items": items,
                    "all_five_exact_after_allowed_normalization": all(
                        x["verdict"] == "exact_after_allowed_normalization" for x in items),
                    "detector_regions_associated_to_all_five_source_items": True})

report = {"case_id": "G1-O01", "scope": case["details"]["oracle_scope"],
          "association": "Raw box centroid inside each approximate fixed source envelope, checked against viewed crops; no invented location tolerance or quality metric.",
          "normalization": "Whitespace and typographic double quotes only; no traditional/simplified conversion.",
          "registry_sha256": sha(registry), "run_summary_sha256": sha(HERE / "summary.json"),
          "reviews": reviews}
assert all(not r["all_five_exact_after_allowed_normalization"] for r in reviews)
(HERE / "selection-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({r["job"]: {i["id"]: i["verdict"] for i in r["items"]} for r in reviews}, ensure_ascii=False))
