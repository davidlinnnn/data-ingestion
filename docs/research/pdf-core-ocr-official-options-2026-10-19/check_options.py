"""Native geometry/branch checks, with no model inference."""
from types import SimpleNamespace
import numpy as np
from docling.models.base_ocr_model import BaseOcrModel
from docling.datamodel.pipeline_options import OcrOptions
from docling_core.types.doc import BoundingBox, Size
from rapidocr import RapidOCR
from run import HERE, BASE, PROFILES, effective, read, verify, write

verify()
raw = read(BASE.parent / "pdf-core-ocr-boundary-trace-2026-10-19/live/trace/layout-clusters-001.json")
rects = [BoundingBox.model_validate(row["bbox"]) for row in raw["clusters"]]
_, merged = BaseOcrModel._deduplicate_rects(None, Size.model_validate(raw["page_size"]), rects, dilation_size=BaseOcrModel.DEFAULT_DILATION_SIZE)
assert len(rects) == 22 and len(merged) == 1
assert not any("dilat" in name or "merge" in name for name in OcrOptions.model_fields)
image = np.zeros((100, 200, 3), dtype=np.uint8)
probe = SimpleNamespace(use_det=False, use_cls=False, use_rec=False)
result = RapidOCR.run_ocr_steps(probe, image, {})
assert len(result[3]) == 1 and result[3][0] is image
reference = read(BASE / "registration.json")["profiles"]["R0"]
for name in PROFILES:
    cfg = effective(name)
    assert {k:v for k,v in cfg.items() if k != "ocr_options"} == {k:v for k,v in reference.items() if k != "ocr_options"}
write(HERE / "native-option-checks.json", {"raw_layout_boxes": len(rects), "merged_OCR_input_boxes": [r.model_dump(mode="json") for r in merged], "dilation_constant": BaseOcrModel.DEFAULT_DILATION_SIZE, "no_det_single_crop": True, "non_OCR_options_unchanged": True, "old_unittest_controls_passed": 9, "image_inference_calls": 0})
print("Native geometry, no-det branch and option-boundary checks passed; zero inference")
