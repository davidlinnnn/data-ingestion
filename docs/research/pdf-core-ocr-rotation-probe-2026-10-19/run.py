"""One bounded causal probe: two native recognizer calls, cached S0 line crops."""
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import sys
import time

import numpy as np
import psutil

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "pdf-core-ocr-crop-ablation-2026-10-19"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def deadline(*_):
    raise TimeoutError("90-second cap")


def main():
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert psutil.virtual_memory().available >= 10 * 2**30, "insufficient available memory"
        signal.signal(signal.SIGALRM, deadline)
        signal.alarm(90)
        assert not (HERE / "result.json").exists(), "fixed probe already ran; no repeat"
        sys.path.insert(0, str(PRIOR))
        spec = importlib.util.spec_from_file_location("retained_crop_run", PRIOR / "run.py")
        retained = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(retained)
        from capture import plain
        registration = retained.verify()
        trace = PRIOR / "A/trace"
        classification = json.loads((trace / "reader-001/classify.json").read_text())
        saved = json.loads((trace / "reader-001/recognize.json").read_text())
        before = [np.load(trace / v["npy"], allow_pickle=False) for v in classification["before"]]
        after = [np.load(trace / v["npy"], allow_pickle=False) for v in classification["after"]]
        for side, arrays in (("before", before), ("after", after)):
            for item, array in zip(classification[side], arrays):
                assert list(array.shape) == item["shape"] and str(array.dtype) == item["dtype"]
                assert hashlib.sha256(array.tobytes()).hexdigest() == item["pixel_sha256"]
        assert saved["inputs"] == classification["after"]
        assert len(before) == len(after) == 114
        changed_pixels = [i for i, (a, b) in enumerate(zip(before, after)) if not np.array_equal(a, b)]
        assert changed_pixels == [39] and np.array_equal(np.rot90(before[39], 2), after[39])
        source_paths = [PRIOR / "A/reader-config.json", trace / "reader-001/classify.json", trace / "reader-001/recognize.json",
            *{trace / v["npy"] for side in ("before", "after") for v in classification[side]}]
        hashes = {str(p): sha(p) for p in source_paths}
        frozen = {"scope": "S0 line-crop causal probe, not a full use_cls=False pipeline or accuracy qualification",
            "recognizer_calls": 2, "line_crops_per_call": 114, "detector_calls": 0, "classifier_calls": 0,
            "retries": 0, "new_models": 0, "API_calls": 0, "timeout_seconds": 90,
            "control": "after-rotation crops must reproduce saved native recognizer output before intervention",
            "intervention": "same 114 crops before classifier rotation; no shape, order or config changes",
            "stop": "stop after paired calls, no threshold changes or automatic follow-up arms",
            "source_hashes": hashes, "registered_model_hashes": {p: h for p, h in registration["hashes"].items() if p.endswith(".onnx")},
            "script_sha256": sha(Path(__file__))}
        frozen["preflight_amendment"] = "v1 stopped before all inference: compare cfg through the same Path-to-string JSON normalization as the retained capture; no model/config/input changes"
        with (HERE / "registration-v2.json").open("x") as stream:
            json.dump(frozen, stream, indent=2)
        from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
        options = retained.legacy().options()
        model = RapidOcrModel(enabled=True, artifacts_path=options.artifacts_path,
            options=options.ocr_options, accelerator_options=options.accelerator_options)
        from omegaconf import OmegaConf
        config = json.loads(json.dumps(OmegaConf.to_container(model.reader.cfg, resolve=True, enum_to_str=True), default=plain))
        assert config == json.loads((PRIOR / "A/reader-config.json").read_text())
        started = time.monotonic()
        control = model.reader.recognize_txt([v.copy() for v in after])
        assert list(control.txts) == saved["texts"], "control text mismatch; stop"
        np.testing.assert_allclose(control.scores, saved["scores"], rtol=0, atol=1e-7)
        intervention = model.reader.recognize_txt([v.copy() for v in before])
        changed = [i for i, (a, b) in enumerate(zip(control.txts, intervention.txts)) if a != b]
        assert all(sha(Path(p)) == h for p, h in hashes.items())
        result = {"control_reproduced": True, "changed_pixel_indices": changed_pixels,
            "changed_text_indices": changed, "elapsed_seconds": time.monotonic() - started,
            "control": {"texts": list(control.txts), "scores": list(control.scores)},
            "before_rotation": {"texts": list(intervention.txts), "scores": list(intervention.scores)},
            "limitations": ["same exposed page only", "no genuinely inverted-input regression set", "no PDF downstream or full use_cls=False run"]}
        with (HERE / "result.json").open("x") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        print(json.dumps({"control_reproduced": True, "changed_indices": changed,
            "index39_before": control.txts[39], "index39_without_rotation": intervention.txts[39],
            "index39_scores": [float(control.scores[39]), float(intervention.scores[39])]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
