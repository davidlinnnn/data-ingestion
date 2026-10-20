"""Pass-through RapidOCR probes; snapshots precede native in-place box mapping."""
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image


def plain(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=plain)
        stream.write("\n")


def output(result):
    return {key: getattr(result, key, None) if result is not None else None
            for key in ("boxes", "txts", "scores", "elapse_list")}


class Capture:
    def __init__(self, directory, budget):
        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=False)
        (self.directory / "images").mkdir()
        self.budget, self.calls, self.current, self.originals = budget, 0, None, []

    def image(self, array):
        digest = hashlib.sha256(str(array.dtype).encode() + str(array.shape).encode() + array.tobytes()).hexdigest()
        stem = self.directory / "images" / digest
        if not stem.with_suffix(".npy").exists():
            np.save(stem.with_suffix(".npy"), array, allow_pickle=False)
            Image.fromarray(array).save(stem.with_suffix(".png"))
        return {"shape": list(array.shape), "dtype": str(array.dtype), "pixel_sha256": hashlib.sha256(array.tobytes()).hexdigest(),
                "npy": str(stem.with_suffix(".npy").relative_to(self.directory)),
                "preview": str(stem.with_suffix(".png").relative_to(self.directory)),
                "channels": "native ndarray channel order, unchanged; PNG is only a preview"}

    def record(self, name, data):
        assert self.current is not None
        write(self.current / (name + ".json"), data)

    def patch(self, cls, name, wrapper):
        owned, original = name in cls.__dict__, getattr(cls, name)
        self.originals.append((cls, name, original, owned))
        setattr(cls, name, wrapper(original))

    def restore(self):
        for cls, name, original, owned in reversed(self.originals):
            if owned:
                setattr(cls, name, original)
            else:
                delattr(cls, name)
        self.originals.clear()

    def install(self, cls):
        trace = self

        def preprocess(original):
            def observed(reader, image):
                result = original(reader, image)
                trace.record("preprocess", {"input": trace.image(image), "output": trace.image(result[0]), "operations": result[1]})
                return result
            return observed

        def crops(original):
            def observed(reader, image, boxes):
                # Native build_final_output later mutates these quads in place.
                snapshot = boxes.copy()
                result = original(reader, image, boxes)
                trace.record("detector-crops", {"input": trace.image(image), "boxes": snapshot,
                    "crops": [trace.image(a) for a in result], "scope": "postprocessed/sorted detector quads, not raw neural logits"})
                return result
            return observed

        def detect(original):
            def observed(reader, image, operations):
                result = original(reader, image, operations)
                trace.record("detect", {"operations": operations, "boxes": result[1].boxes})
                return result
            return observed

        def classify(original):
            def observed(reader, images):
                before = [trace.image(a) for a in images]
                result = original(reader, images)
                trace.record("classify", {"before": before, "after": [trace.image(a) for a in result[0]],
                    "labels": result[1].cls_res})
                return result
            return observed

        def recognize(original):
            def observed(reader, images):
                inputs = [trace.image(a) for a in images]
                result = original(reader, images)
                trace.record("recognize", {"inputs": inputs, "texts": result.txts, "scores": result.scores})
                return result
            return observed

        for name, wrapper in (("preprocess_img", preprocess), ("crop_text_regions", crops),
                              ("detect_and_crop", detect), ("cls_and_rotate", classify), ("recognize_txt", recognize)):
            self.patch(cls, name, wrapper)

    def reader(self, original):
        def observed(image, **kwargs):
            if self.calls >= self.budget:
                raise RuntimeError("registered reader call budget exhausted; no retry")
            self.calls += 1
            self.current = self.directory / f"reader-{self.calls:03}"
            self.current.mkdir(exist_ok=False)
            self.record("start", {"call": self.calls, "input": self.image(image), "kwargs": kwargs})
            started = time.monotonic()
            try:
                result = original(image, **kwargs)
            except Exception as error:
                self.record("exception", {"type": type(error).__name__, "message": str(error), "seconds": time.monotonic()-started})
                raise
            elapsed = time.monotonic()-started
            self.record("result", {**output(result), "instrumented_reader_seconds": elapsed})
            return result
        return observed
