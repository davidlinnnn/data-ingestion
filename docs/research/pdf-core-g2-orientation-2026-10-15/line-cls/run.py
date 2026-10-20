"""Two exact-input OCR diagnostics; only per-call use_cls changes from baseline."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "baseline"
spec = importlib.util.spec_from_file_location("frozen_baseline_guard", BASELINE / "run.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
baseline.HERE = HERE
baseline.JOBS = [("controls-p7-selective", 7, False, ["chinese"]), ("controls-p8-full", 8, True, ["chinese"])]
baseline.__file__ = str(Path(__file__).resolve())


def check():
    for name, digest in json.loads((BASELINE / "artifact-sha256.json").read_text()).items():
        assert baseline.sha(BASELINE / name) == digest, f"Frozen baseline changed: {name}"
    files = baseline.frozen_files()
    for path in [BASELINE / "run.py", BASELINE / "artifact-sha256.json"]:
        files[str(path.relative_to(baseline.REPO))] = baseline.sha(path)
    return files


def worker(job):
    import numpy as np
    from omegaconf import OmegaConf
    from PIL import Image
    from rapidocr import RapidOCR
    from rapidocr.utils.process_img import map_boxes_to_original
    from rapidocr.utils.typings import EngineType
    name, page, _, _ = job
    folder = HERE / "runs" / name
    original = BASELINE / "runs" / name
    image_path = original / "raw-ocr-calls/000.png"
    saved_output = json.loads((original / "raw-ocr-calls/000.output.json").read_text())
    producer = json.loads((original / "producer.json").read_text())
    image = np.array(Image.open(image_path))
    assert image.dtype == np.uint8 and image.shape[2] == 3
    # Baseline passed an ndarray; preserve its channel values and input type exactly.
    params = copy.deepcopy(producer["constructor_params"])
    for key in ("Det.engine_type", "Cls.engine_type", "Rec.engine_type"):
        assert params[key] == "EngineType.ONNXRUNTIME"
        params[key] = EngineType.ONNXRUNTIME

    def plain(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, (list, tuple)):
            return [plain(v) for v in value]
        if isinstance(value, dict):
            return {key: plain(v) for key, v in value.items()}
        return value

    calls = []
    class ObservedOCR(RapidOCR):
        def cls_and_rotate(self, *args, **kwargs):
            raise AssertionError("Line classification must not execute in this diagnostic")

        def build_final_output(self, image, det, cls, rec, crops, record):
            calls.append(1)
            mapped = None if det.boxes is None else map_boxes_to_original(copy.deepcopy(det.boxes), record, *image.shape[:2])
            baseline.save(folder / "raw.json", plain({"source_mapping": saved_output["source_mapping"],
                "detector_boxes_before_mapping": det.boxes, "detector_boxes_crop_pixels": mapped,
                "detector_scores": det.scores, "recognizer_texts": rec.txts, "recognizer_scores": rec.scores,
                "classifier_results": cls.cls_res, "stage_seconds": [det.elapse, cls.elapse, rec.elapse],
                "preprocessing_coordinate_record": record, "input_image_shape_hwc": image.shape}))
            return super().build_final_output(image, det, cls, rec, crops, record)

    start = time.perf_counter()
    engine = ObservedOCR(params=params)
    resolved = json.loads(json.dumps(OmegaConf.to_container(engine.cfg, resolve=True, enum_to_str=True), default=str))
    assert resolved == producer["resolved_config"], "Only per-call use_cls may change"
    assert engine.use_cls is True
    sessions = {name: obj.session.session for name, obj in (("det", engine.text_det), ("cls", engine.text_cls), ("rec", engine.text_rec))}
    assert all(s.get_providers() == ["CPUExecutionProvider"] for s in sessions.values())
    for session in sessions.values():
        session.disable_fallback()
    dictionary = engine.text_rec.session.get_character_list()
    dictionary_hash = hashlib.sha256("\n".join(dictionary).encode()).hexdigest()
    assert dictionary_hash == producer["recognizer_dictionary"]["utf8_newline_joined_sha256"]
    started_call = time.perf_counter()
    result = engine(image, use_cls=False)
    call_seconds = time.perf_counter() - started_call
    assert engine.use_cls is False and calls == [1]
    baseline.save(folder / "output.json", plain({"source_mapping": saved_output["source_mapping"],
        "effective_call_kwargs": {"use_cls": False}, "boxes_crop_pixels": result.boxes,
        "texts": result.txts, "scores": result.scores, "stage_seconds": result.elapse_list,
        "call_seconds_including_observation": call_seconds, "seconds_including_engine_load": time.perf_counter() - start}))
    baseline.save(folder / "producer.json", {"baseline_producer_path": str((original / "producer.json").relative_to(baseline.REPO)),
        "baseline_producer_sha256": baseline.sha(original / "producer.json"), "resolved_config": resolved,
        "call_use_cls": False, "effective_use_cls_after_call": engine.use_cls,
        "actual_sessions": {key: {"providers": s.get_providers(), "provider_options": s.get_provider_options(),
             "intra_op_num_threads": s.get_session_options().intra_op_num_threads,
             "inter_op_num_threads": s.get_session_options().inter_op_num_threads} for key, s in sessions.items()},
        "model_sha256": {p.name: baseline.sha(p) for p in baseline.MODELS.glob("*.onnx")},
        "recognizer_dictionary": {"origin": "same embedded ONNX metadata as frozen baseline", "character_count": len(dictionary),
                                  "utf8_newline_joined_sha256": dictionary_hash},
        "input_png_path": str(image_path.relative_to(baseline.REPO)), "input_png_sha256": baseline.sha(image_path),
        "input_array_type": "numpy.ndarray uint8; same channel order as saved baseline array", "input_array_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        "input_shape_hwc": list(image.shape), "physical_page_1based": page, "ocr_calls": len(calls), "line_classifier_inference_calls": 0})


baseline.check = check
baseline.worker = worker


if __name__ == "__main__":
    if sys.argv[1:] == ["--freeze"]:
        assert not (HERE / "frozen-inputs.json").exists()
        baseline.save(HERE / "frozen-inputs.json", check())
        baseline.save(HERE / "method.json", {"scope": "Two exact baseline PNG OCR calls changing only per-call use_cls=False; no oracle input, no pipeline rerun or policy recommendation",
            "runner_sha256": baseline.sha(Path(__file__)), "guard_runner_sha256": baseline.sha(BASELINE / "run.py"),
            "guard": {"lock": str(baseline.LOCK), "timeout_seconds": baseline.TIMEOUT, "sampled_tree_rss_limit_bytes": baseline.LIMIT,
                      "available_before_min_bytes": 8 * 1024**3, "sample_seconds": .25},
            "input_policy": "Reuse byte-identical saved PNG as ndarray, preserving exact channel values/type from baseline; no resampling/crop or oracle boxes/text",
            "jobs": [{"name": j[0], "physical_page_1based": j[1], "input_png": str((BASELINE / 'runs' / j[0] / 'raw-ocr-calls/000.png').relative_to(baseline.REPO)),
                      "input_png_sha256": baseline.sha(BASELINE / 'runs' / j[0] / 'raw-ocr-calls/000.png')} for j in baseline.JOBS]})
        print("Two exact inputs and reused guard frozen; no inference.")
    elif len(sys.argv) == 3 and sys.argv[1] == "--worker":
        assert check() == json.loads((HERE / "frozen-inputs.json").read_text())
        worker(next(j for j in baseline.JOBS if j[0] == sys.argv[2]))
    else:
        baseline.main()
        summary = json.loads((HERE / "summary.json").read_text())
        summary["scope"] = "Two exact saved baseline PNG OCR diagnostics changing only per-call use_cls=False; not Docling pipeline output"
        baseline.save(HERE / "summary.json", summary)
