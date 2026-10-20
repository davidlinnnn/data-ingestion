"""Verify exact-input diagnostics and compare every saved raw line; no model runs."""

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("line_cls_frozen_runner", HERE / "run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
baseline = runner.baseline


def main():
    assert runner.check() == json.loads((HERE / "frozen-inputs.json").read_text())
    method = json.loads((HERE / "method.json").read_text())
    assert method["runner_sha256"] == baseline.sha(HERE / "run.py")
    summary = json.loads((HERE / "summary.json").read_text())
    assert len(summary["jobs"]) == 2
    results = []
    for job in summary["jobs"]:
        assert job["execution_status"] == "completed" and job["stopped"] is None and job["exit_code"] == 0
        assert job["available_before_bytes"] >= 8 * 1024**3
        assert job["sampled_tree_peak_rss_bytes"] <= 6 * 1024**3
        assert job["seconds_including_process_start_exit"] < 180
        name = job["name"]
        old = runner.BASELINE / "runs" / name
        new = HERE / "runs" / name
        before = json.loads((old / "raw-ocr-calls/000.raw.json").read_text())
        after = json.loads((new / "raw.json").read_text())
        output = json.loads((new / "output.json").read_text())
        producer = json.loads((new / "producer.json").read_text())
        assert producer["ocr_calls"] == 1 and producer["line_classifier_inference_calls"] == 0
        assert producer["effective_use_cls_after_call"] is False and producer["call_use_cls"] is False
        assert after["classifier_results"] is None and after["stage_seconds"][1] is None
        assert producer["resolved_config"] == json.loads((old / "producer.json").read_text())["resolved_config"]
        assert producer["input_png_sha256"] == baseline.sha(old / "raw-ocr-calls/000.png")
        assert all(s["providers"] == ["CPUExecutionProvider"] for s in producer["actual_sessions"].values())
        assert all(s["intra_op_num_threads"] == 4 and s["inter_op_num_threads"] == 1 for s in producer["actual_sessions"].values())
        for key in ["source_mapping", "detector_boxes_before_mapping", "detector_boxes_crop_pixels", "detector_scores",
                    "preprocessing_coordinate_record", "input_image_shape_hwc"]:
            assert before[key] == after[key], f"Detection/input changed: {name} {key}"
        assert len(before["recognizer_texts"]) == len(after["recognizer_texts"])
        rows = [{"index_in_raw_producer_order": i, "box_crop_pixels": after["detector_boxes_crop_pixels"][i],
                 "baseline_classifier": before["classifier_results"][i],
                 "baseline_text": a, "baseline_score": before["recognizer_scores"][i],
                 "without_line_classifier_text": b, "without_line_classifier_score": after["recognizer_scores"][i],
                 "text_changed": a != b}
                for i, (a, b) in enumerate(zip(before["recognizer_texts"], after["recognizer_texts"]))]
        results.append({"job": name, "input_png_sha256": producer["input_png_sha256"], "detector_outputs_identical": True,
                        "constructor_config_identical": True, "changed_raw_line_indices": [r["index_in_raw_producer_order"] for r in rows if r["text_changed"]],
                        "raw_lines": rows, "final_output_count": len(output["texts"])})
    result = {"scope": "Two same-input single-variable raw OCR diagnostics; no semantic oracle scoring or Docling integration",
              "checks": "passed", "total_new_ocr_calls": 2, "total_line_classifier_inference_calls": 0,
              "method_sha256": baseline.sha(HERE / "method.json"), "jobs": results}
    baseline.save(HERE / "comparison.json", result)
    print(json.dumps({"checks": "passed", "jobs": [{"name": r["job"], "changed_raw_line_indices": r["changed_raw_line_indices"]} for r in results]}))


if __name__ == "__main__":
    main()
