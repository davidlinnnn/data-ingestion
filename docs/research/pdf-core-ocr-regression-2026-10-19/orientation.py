"""One fixed 12-line x two-direction paired probe; no threshold search."""
import hashlib
import time

import numpy as np
from PIL import Image

from run import HERE, options, read, stage, verify, write


def worker():
    verify()
    from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
    out = HERE / "orientation"
    stage(out, "direction-probe", 180)
    reference = read(HERE / "corpus/orientation.json")["lines"]
    assert len(reference) == 12 and len({x["source_page_id"] for x in reference}) >= 3
    config = options("R0")
    model = RapidOcrModel(enabled=True, artifacts_path=config.artifacts_path,
        options=config.ocr_options, accelerator_options=config.accelerator_options)
    normal = [model.reader.load_img(Image.open(x["png"]).convert("RGB")) for x in reference]
    inputs = normal + [np.rot90(x, 2).copy() for x in normal]
    write(out / "inputs.json", [{"line_id": reference[i % 12]["id"], "rotation": 0 if i < 12 else 180,
        "shape": list(x.shape), "pixel_sha256": hashlib.sha256(x.tobytes()).hexdigest()} for i, x in enumerate(inputs)])
    started = time.monotonic()
    rotated, classified = model.reader.cls_and_rotate([x.copy() for x in inputs])
    with_classifier = model.reader.recognize_txt(rotated)
    without_classifier = model.reader.recognize_txt([x.copy() for x in inputs])
    rows = []
    for i, (original, actual) in enumerate(zip(inputs, rotated)):
        assert actual.shape == original.shape
        flipped = not np.array_equal(original, actual)
        if flipped:
            assert np.array_equal(np.rot90(original, 2), actual)
        rows.append({"id": reference[i % 12]["id"], "input_rotation": 0 if i < 12 else 180,
            "reference": reference[i % 12]["text"], "classifier": {"label": str(classified.cls_res[i][0]), "score": float(classified.cls_res[i][1])}, "actually_flipped": flipped,
            "with_classifier": {"text": with_classifier.txts[i], "score": float(with_classifier.scores[i])},
            "without_classifier": {"text": without_classifier.txts[i], "score": float(without_classifier.scores[i])}})
    write(out / "result.json", {"rows": rows, "seconds": time.monotonic() - started,
        "classifier_calls": 1, "recognizer_calls": 2, "line_inputs_per_recognizer_call": 24,
        "detector_calls": 0, "API_calls": 0, "retries": 0,
        "scope": "fixed line crops; synthetic 180-degree controls are paired derivatives, not independent documents"})
    verify()
    print("Completed fixed paired direction probe; no additional variants.", flush=True)
