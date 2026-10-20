"""Raster-only OCR crop-policy probe; native recognition and downstream unchanged."""
import json
import os
from pathlib import Path
from typing import ClassVar

from docling.datamodel.pipeline_options import OcrMode, RapidOcrOptions
from docling.models.base_ocr_model import BaseOcrModel
from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
from docling_core.types.doc import BoundingBox


class SeparateOptions(RapidOcrOptions):
    kind: ClassVar[str] = "separate_rapidocr_probe"
    preserve_context: bool = False


class SeparateRapidOcr(RapidOcrModel):
    @classmethod
    def get_options_type(cls):
        return SeparateOptions

    def get_ocr_rects(self, page):
        assert self.options.mode == OcrMode.LAYOUT_REGIONS
        cells = page._backend.get_text_cells()
        assert cells is not None and len(cells) == 0, "Probe only supports raster PDFs"
        assert page.size is not None and page.predictions.layout is not None
        raw = [cluster.bbox for cluster in page.predictions.layout.clusters]
        _, grouped = BaseOcrModel._deduplicate_rects(self, page.size, raw, dilation_size=0)
        margin = BaseOcrModel.DEFAULT_DILATION_SIZE / 2 if self.options.preserve_context else 0
        # Keep context separate from connectivity; expanding must not union the crops again.
        regions = [BoundingBox(l=max(0, box.l - margin), t=max(0, box.t - margin),
            r=min(page.size.width, box.r + margin), b=min(page.size.height, box.b + margin),
            coord_origin=box.coord_origin) for box in grouped]
        if root := os.environ.get("PDF_REGION_TRACE_ROOT"):
            root = Path(root)
            job = json.loads((root / "stage.json").read_text())["job"]
            with (root / job / "regions.json").open("x") as stream:
                json.dump({"raw_layout_boxes": [box.model_dump(mode="json") for box in raw],
                    "zero_dilation_groups": [box.model_dump(mode="json") for box in grouped],
                    "context_points": margin,
                    "OCR_input_regions": [box.model_dump(mode="json") for box in regions]}, stream, indent=2)
        return regions


def ocr_engines():
    return {"ocr_engines": [SeparateRapidOcr]}
