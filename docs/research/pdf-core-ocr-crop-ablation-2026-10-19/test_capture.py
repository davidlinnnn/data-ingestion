"""No-model tests for transparent probes, native mapping and source pixel crops."""
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from omegaconf import OmegaConf

from capture import Capture, write
from run import crop, rects


class FakeReader:
    def preprocess_img(self, image):
        return image, {"preprocess": {"ratio_h": 1, "ratio_w": 1}}

    def crop_text_regions(self, image, boxes):
        return [image]

    def detect_and_crop(self, image, operations):
        operations["padding_1"] = {"top": 0, "left": 0}
        boxes = np.array([[[0., 0.], [3., 0.], [3., 2.], [0., 2.]]])
        return self.crop_text_regions(image, boxes), SimpleNamespace(boxes=boxes)

    def cls_and_rotate(self, images):
        return images, SimpleNamespace(cls_res=[("0", .99)])

    def recognize_txt(self, images):
        return SimpleNamespace(txts=("source",), scores=(.99,))

    def __call__(self, image, **kwargs):
        self.actual_image, self.kwargs = image, kwargs
        processed, operations = self.preprocess_img(image)
        images, detected = self.detect_and_crop(processed, operations)
        images, _ = self.cls_and_rotate(images)
        recognized = self.recognize_txt(images)
        detected.boxes += 100
        self.result = SimpleNamespace(boxes=detected.boxes, txts=recognized.txts, scores=recognized.scores)
        return self.result


class CaptureTests(unittest.TestCase):
    def test_native_flow_identity_snapshots_and_restore(self):
        original = FakeReader.crop_text_regions
        array = np.arange(36, dtype=np.uint8).reshape((3, 4, 3))
        before = array.copy()
        with tempfile.TemporaryDirectory() as tmp:
            trace = Capture(Path(tmp) / "trace", 1)
            try:
                trace.install(FakeReader)
                reader = FakeReader()
                result = trace.reader(reader)(array, use_det=True, use_cls=True, use_rec=True)
                self.assertIs(result, reader.result)
                self.assertIs(reader.actual_image, array)
                self.assertEqual(reader.kwargs, {"use_det": True, "use_cls": True, "use_rec": True})
                np.testing.assert_array_equal(array, before)
                raw = json.loads((trace.current / "detector-crops.json").read_text())
                self.assertEqual(raw["boxes"][0][0], [0., 0.])
                self.assertEqual(result.boxes[0][0].tolist(), [100., 100.])
                recognized = json.loads((trace.current / "recognize.json").read_text())
                self.assertEqual(recognized["inputs"], raw["crops"])
                self.assertEqual(trace.calls, 1)
                with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
                    trace.reader(reader)(array)
                self.assertEqual(trace.calls, 1)
            finally:
                trace.restore()
            self.assertIs(FakeReader.crop_text_regions, original)

    def test_empty_result_and_exception_are_not_retried(self):
        from rapidocr.utils.output import RapidOCROutput
        array = np.zeros((3, 4, 3), dtype=np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            trace = Capture(Path(tmp) / "trace", 3)
            self.assertIsNone(trace.reader(lambda image: None)(array))
            result = RapidOCROutput()
            self.assertIs(trace.reader(lambda image: result)(array), result)
            failure = ValueError("native failure")
            def fail(image):
                raise failure
            with self.assertRaises(ValueError) as caught:
                trace.reader(fail)(array)
            self.assertIs(caught.exception, failure)
            self.assertEqual(trace.calls, 3)

    def test_config_path_is_serializable_without_models(self):
        config = OmegaConf.create({"Global": {"model_root_dir": Path("/private/tmp/models")}}, flags={"allow_objects": True})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            write(path, OmegaConf.to_container(config, resolve=True, enum_to_str=True))
            self.assertEqual(json.loads(path.read_text())["Global"]["model_root_dir"], "/private/tmp/models")

    def test_native_startup_config_with_fake_inference_engine(self):
        import rapidocr
        from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
        from run import legacy
        native_class, opts = rapidocr.RapidOCR, legacy().options()
        created = []
        def factory(*, params):
            reader = FakeReader()
            reader.cfg = native_class.__new__(native_class)._load_config(None, params)
            created.append(reader)
            return reader
        with patch("rapidocr.RapidOCR", factory):
            model = RapidOcrModel(enabled=True, artifacts_path=opts.artifacts_path,
                options=opts.ocr_options, accelerator_options=opts.accelerator_options)
        self.assertIs(model.reader, created[0])
        self.assertEqual(len(created), 1)
        self.assertEqual(str(model.reader.cfg.Det.model_path), opts.ocr_options.det_model_path)
        with tempfile.TemporaryDirectory() as tmp:
            write(Path(tmp) / "config.json", OmegaConf.to_container(model.reader.cfg, resolve=True, enum_to_str=True))

    def test_saved_pixel_crop_identity_and_bounds(self):
        array = np.arange(2211*1608*3, dtype=np.uint8).reshape((2211, 1608, 3))
        np.testing.assert_array_equal(crop(array, rects("A")[0], 3), array)
        self.assertEqual(len(rects("B")), 15)
        for box in rects("B"):
            small = crop(array, box, 3)
            self.assertGreater(small.size, 0)
            self.assertFalse(np.shares_memory(small, array))
        from docling_core.types.doc import BoundingBox, CoordOrigin
        with self.assertRaises(AssertionError):
            crop(array, BoundingBox(l=0, t=0, r=1, b=1, coord_origin=CoordOrigin.TOPLEFT), 3)

    def test_sdk_quad_mapping_not_a_custom_mapper(self):
        from docling.datamodel.base_models import Page
        from docling.datamodel.document import ConversionResult, InputDocument
        from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
        from docling_core.types.doc import BoundingBox, CoordOrigin, Size
        from PIL import Image
        model = RapidOcrModel.__new__(RapidOcrModel)
        model.enabled, model.scale = True, 3
        model.options = SimpleNamespace(use_det=True, use_cls=True, use_rec=True)
        box = BoundingBox(l=10, t=20, r=14, b=23, coord_origin=CoordOrigin.TOPLEFT)
        model.get_ocr_rects = lambda page: [box]
        model.reader = lambda image, **kwargs: SimpleNamespace(boxes=np.array([[[3., 3.], [6., 3.], [6., 6.], [3., 6.]]]),
            txts=("source",), scores=(.9,))
        cells = []
        model.post_process_cells = lambda actual, page, conv: cells.extend(actual)
        page = Page(page_no=1, size=Size(width=612, height=792))
        page._backend = SimpleNamespace(is_valid=lambda: True, get_page_image=lambda **kwargs: Image.new("RGB", (12, 9)))
        conv = ConversionResult(input=InputDocument.model_construct())
        self.assertEqual(list(model(conv, [page])), [page])
        self.assertEqual(cells[0].rect.to_bounding_box().as_tuple(), (11, 21, 12, 22))
        self.assertEqual(cells[0].text, "source")


if __name__ == "__main__":
    unittest.main()
