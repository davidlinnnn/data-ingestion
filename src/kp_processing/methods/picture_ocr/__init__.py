"""picture-ocr: text inside a picture, read by local RapidOCR from the registered picture
image (the assemble output at images_scale 2.0, 144 dpi)."""

import io
import json
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from kp_processing import weights
from kp_processing.methods import InventoryItem, MethodOutput, MethodUnavailable

ID = "picture-ocr"
VERSION = 1
ORIGIN = "reconstruction"
TARGET = ("pictures", None)
INPUTS = ("picture_image",)

# Component rapidocr-ppocrv6-small, relative to weights.root(), verified at worker start.
DET_MODEL = "RapidOcr/PP-OCRv6_det_small.onnx"
REC_MODEL = "RapidOcr/PP-OCRv6_rec_small.onnx"
CLS_MODEL = "RapidOcr/ch_ppocr_mobile_v2.0_cls_mobile.onnx"


@cache
def _engine(root: Path) -> Any:
    try:
        from rapidocr import RapidOCR

        if any(not (root / name).is_file() for name in (DET_MODEL, REC_MODEL, CLS_MODEL)):
            raise MethodUnavailable("RapidOCR weight files are missing")
        return RapidOCR(
            params={
                "Det.model_path": str(root / DET_MODEL),
                "Rec.model_path": str(root / REC_MODEL),
                "Cls.model_path": str(root / CLS_MODEL),
                "EngineConfig.onnxruntime.intra_op_num_threads": 4,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
                "Global.log_level": "error",
            }
        )
    except Exception as exc:
        raise MethodUnavailable("RapidOCR engine cannot load its weights") from exc


def ocr(png: bytes) -> list[dict[str, Any]]:
    """RapidOCR lines of one image, in RapidOCR's order: [{"text", "score", "box"}], where box
    is the four [x, y] corners in image pixels. [] when it finds no text. Loads the engine
    once per weights root (RapidOCR 3.9.2 defaults, text_score 0.5, onnxruntime 4 intra-op and
    1 inter-op threads); raises MethodUnavailable when a weight file is
    missing or the engine cannot load. Raises ValueError when png is not a decodable image."""
    try:
        with Image.open(io.BytesIO(png)) as image:
            pixels = np.asarray(image.convert("RGB"))
    except (OSError, ValueError) as exc:
        raise ValueError("Picture image cannot be decoded") from exc
    result = _engine(weights.root())(pixels)
    if result.txts is None:
        return []
    return [
        {"text": text, "score": float(score), "box": box.tolist()}
        for text, score, box in zip(result.txts, result.scores, result.boxes, strict=True)
    ]


def run(item: InventoryItem, inputs: list[bytes]) -> MethodOutput:
    """Lines from ocr() on the picture image joined with "\\n" are the content.

    success  content = the joined text; provider artifact "ocr.json" = {"lines": ocr(...)}
    no_text  ocr() found no line; content ""; provider artifact "ocr.json" = {"lines": []}
    failed   reason RENDER_FAILED when the image cannot be decoded
    No evidence files (the picture image is native evidence already) and no signals."""
    try:
        lines = ocr(inputs[0])
    except ValueError:
        return MethodOutput(outcome="failed", reason="RENDER_FAILED")
    return MethodOutput(
        outcome="success" if lines else "no_text",
        content="\n".join(line["text"] for line in lines),
        files={"ocr.json": json.dumps({"lines": lines}, separators=(",", ":")).encode()},
        provider_artifact="ocr.json",
    )
