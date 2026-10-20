"""Recompute the frozen two-arm diagnosis without loading inference models."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

from run import HERE, TRACE, crop, read, rects, verify
from capture import write


def analyze():
    verify()
    amendment = read(HERE / "evaluator-schema-amendment.json")
    for relative, expected in amendment["A_collection_seal"].items():
        assert hashlib.sha256((HERE / relative).read_bytes()).hexdigest() == expected
    assert read(HERE / "A/reader-config.json") == read(HERE / "B/reader-config.json")
    source = np.load(TRACE / "live/trace/ocr-engine-001.npy", allow_pickle=False)
    result = {"state": "DIAGNOSED_NOT_ACCEPTED", "reader_configs_equal": True,
              "source_pixels_verified": True, "arms": {}, "inference_retries": 0, "API_calls": 0,
              "scope": "one clean raster page; cached Heron; native OCR mapping and downstream replay; no full-pipeline or production qualification"}
    for arm, score_name in (("A", "score-schema-amended.json"), ("B", "score.json")):
        out = HERE / arm
        traces = sorted((out / "trace").glob("reader-*"))
        assert len(traces) == len(rects(arm))
        native_seconds = np.zeros(3)
        reader_seconds, empty = 0., []
        for index, (trace, box) in enumerate(zip(traces, rects(arm)), 1):
            start, final = read(trace / "start.json"), read(trace / "result.json")
            expected = crop(source, box, 3)
            actual = np.load(out / "trace" / start["input"]["npy"], allow_pickle=False)
            np.testing.assert_array_equal(actual, expected)
            assert start["kwargs"] == {"use_det": True, "use_cls": True, "use_rec": True}
            reader_seconds += final["instrumented_reader_seconds"]
            values = final["elapse_list"] or []
            assert len(values) in (0, 3)
            if values:
                native_seconds += values
            if final["txts"] is None:
                empty.append(index)
            if (trace / "recognize.json").exists():
                cls, rec = read(trace / "classify.json"), read(trace / "recognize.json")
                assert cls["after"] == rec["inputs"]
        scoring = read(out / score_name)
        execution, completed = read(out / "execution.json"), read(out / "completed.json")
        assert execution["status"] == "completed"
        result["arms"][arm] = {
            "reader_calls": len(traces), "empty_reader_indices_1based": empty,
            "raw_cell_count": len(read(out / "ocr-cells.json")),
            "raw_cross_column_cells": [x["index"] for x in scoring["raw_cells"]["cross_column_mixed_elements"]],
            "document_cross_column_elements": [x["index"] for x in scoring["document"]["cross_column_mixed_elements"]],
            "omission_candidates": scoring["document"]["whole_paragraph_omissions_candidates"],
            "duplicate_candidates": scoring["document"]["whole_paragraph_duplicates_candidates"],
            "order_inversions_confirmed_by_review": scoring["document"]["body_order_inversions_candidates"],
            "cost": {"whole_worker_seconds": execution["seconds"],
                "initialization_seconds": read(out / "initialization.json")["seconds"],
                "instrumented_OCR_seconds": completed["instrumented_ocr_seconds"],
                "instrumented_reader_seconds": reader_seconds,
                "native_det_cls_rec_seconds": native_seconds.tolist(),
                "native_elapsed_sum_seconds": float(native_seconds.sum()),
                "official_downstream_seconds": completed["official_downstream_cost"]["total_seconds"],
                "peak_sampled_tree_rss_bytes": execution["peak_sampled_tree_rss_bytes"]}}
    mixed = []
    trace = HERE / "A/trace/reader-001"
    detected, recognized = read(trace / "detector-crops.json"), read(trace / "recognize.json")
    for index in result["arms"]["A"]["raw_cross_column_cells"]:
        quad = np.asarray(detected["boxes"][index])
        assert detected["crops"][index] == recognized["inputs"][index]
        mixed.append({"index_0based": index, "detector_quad_bounds": [float(quad[:, 0].min()), float(quad[:, 1].min()),
            float(quad[:, 0].max()), float(quad[:, 1].max())], "detector_image_width": detected["input"]["shape"][1],
            "actual_rec_crop": recognized["inputs"][index], "text": recognized["texts"][index]})
    rotations = []
    for arm, reader, line in (("A", 1, 39), ("B", 9, 0)):
        trace = HERE / arm / "trace" / f"reader-{reader:03}"
        cls, rec = read(trace / "classify.json"), read(trace / "recognize.json")
        before, after = cls["before"][line], cls["after"][line]
        a = np.load(HERE / arm / "trace" / before["npy"], allow_pickle=False)
        b = np.load(HERE / arm / "trace" / after["npy"], allow_pickle=False)
        assert np.array_equal(np.rot90(a, 2), b)
        assert after == rec["inputs"][line]
        rotations.append({"arm": arm, "reader_1based": reader, "line_0based": line,
            "label_score": cls["labels"][line], "before": before, "after": after,
            "recognized_text": rec["texts"][line], "recognition_score": rec["scores"][line]})
    result["wide_crop_pre_recognition_mixed_quads"] = mixed
    result["preexisting_false_rotations"] = rotations
    result["control_exact_reproduction"] = read(HERE / "A/reproduction.json")
    result["evaluator_amendment"] = "A/score.json is invalid document scoring; final A uses score-schema-amended.json, same evaluator as B; no OCR repeated"
    assert sum(v["reader_calls"] for v in result["arms"].values()) == 16
    assert result["arms"]["B"]["empty_reader_indices_1based"] == [1, 7]
    return result


if __name__ == "__main__":
    result = analyze()
    if sys.argv[1:] == ["--check"]:
        assert result == read(HERE / "analysis.json")
    elif not sys.argv[1:]:
        write(HERE / "analysis.json", result)
    else:
        raise SystemExit("use no arguments once, or --check for a read-only replay")
    print(json.dumps({"state": result["state"], "reader_calls": 16,
        "raw_cross_column_A_B": [result["arms"][a]["raw_cross_column_cells"] for a in ("A", "B")],
        "document_order_inversions_A_B": [len(result["arms"][a]["order_inversions_confirmed_by_review"]) for a in ("A", "B")]}))
