"""No-inference checks for observer transparency and the actual red/green seam."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np
from run import Trace, OLD
from check import inspect


class CaptureTests(unittest.TestCase):
    def test_reader_preserves_native_empty_results(self):
        from rapidocr.utils.output import RapidOCROutput
        with tempfile.TemporaryDirectory() as tmp:
            trace = Trace(Path(tmp) / "trace")
            for value in (None, RapidOCROutput()):
                self.assertIs(trace.reader(lambda image, **kwargs: value)(np.zeros((2, 2, 3), dtype=np.uint8)), value)
            self.assertIsNone(json.loads((trace.directory / "ocr-engine-002.json").read_text())["texts"])

    def test_reader_preserves_input_kwargs_result_and_call_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Trace(Path(tmp) / "trace")
            image = np.arange(36, dtype=np.uint8).reshape(3, 4, 3)
            result = SimpleNamespace(boxes=np.array([[[0, 0], [1, 0], [1, 1], [0, 1]]]), txts=["source"], scores=[.9])
            calls = []
            def reader(actual, **kwargs):
                self.assertIs(actual, image)
                calls.append(kwargs)
                return result
            observed = trace.reader(reader)(image, use_det=True, use_cls=True, use_rec=True)
            self.assertIs(observed, result)
            self.assertEqual(calls, [{"use_det": True, "use_cls": True, "use_rec": True}])
            np.testing.assert_array_equal(np.load(trace.directory / "ocr-engine-001.npy"), image)
            record = json.loads((trace.directory / "ocr-engine-001.json").read_text())
            self.assertEqual(record["texts"], ["source"])
            result.txts[0] = "later mutation"
            self.assertEqual(json.loads((trace.directory / "ocr-engine-001.json").read_text())["texts"], ["source"])

    def test_class_patch_returns_same_object_and_restores(self):
        class Base:
            def call(self, values):
                return values
        class Child(Base):
            pass
        with tempfile.TemporaryDirectory() as tmp:
            trace = Trace(Path(tmp) / "trace")
            counts = []
            def wrapper(original):
                def observed(obj, values):
                    counts.append(1)
                    return original(obj, values)
                return observed
            trace.patch(Child, "call", wrapper)
            value = ["source"]
            self.assertIs(Child().call(value), value)
            self.assertEqual(counts, [1])
            trace.restore()
            self.assertNotIn("call", Child.__dict__)

    def test_frozen_actual_assembly_red_and_positive_control(self):
        s0 = inspect(json.loads((OLD / "S0/scan/result.json").read_text()))
        s1 = inspect(json.loads((OLD / "S1/scan/result.json").read_text()))
        self.assertFalse(s0["paragraph_integrity_pass"])
        self.assertTrue(s0["foror_present"])
        self.assertTrue(s1["paragraph_integrity_pass"])
        self.assertFalse(s1["foror_present"])

    def test_actual_dedup_generator_observer_is_transparent(self):
        from docling.models.base_ocr_model import BaseOcrModel
        from docling_core.types.doc import BoundingBox, CoordOrigin, Size
        boxes = [BoundingBox(l=x, t=10, r=x+60, b=70, coord_origin=CoordOrigin.TOPLEFT) for x in (10, 80)]
        size = Size(width=200, height=100)
        model = SimpleNamespace()
        baseline = BaseOcrModel._deduplicate_rects(model, size, boxes, dilation_size=20)
        with tempfile.TemporaryDirectory() as tmp:
            trace = Trace(Path(tmp) / "trace")
            visited = []
            def generate():
                for i, box in enumerate(boxes):
                    visited.append(i)
                    yield box
            try:
                trace.install()
                observed = BaseOcrModel._deduplicate_rects(model, size, generate(), dilation_size=20)
                self.assertEqual(observed, baseline)
                self.assertEqual(visited, [0, 1])
                self.assertEqual(len(observed[1]), 1)
                self.assertEqual(trace.counts["ocr-dedup"], 1)
            finally:
                trace.restore()


if __name__ == "__main__":
    unittest.main()
