"""picture-ocr: text inside a picture, read by local RapidOCR from the registered picture
image (the assemble output at images_scale 2.0, 144 dpi). #84 gold, 358 pilot items: the 2x
image matched 305, a 3x re-render 300."""

from typing import Any

from kp_processing.methods import MethodOutput

ID = "picture-ocr"
VERSION = 1
ORIGIN = "reconstruction"

# Weight files of component rapidocr-ppocrv6-small, relative to weights.root(); the inference
# worker checks them against the manifest at start.
DET_MODEL = "RapidOcr/PP-OCRv6_det_small.onnx"
REC_MODEL = "RapidOcr/PP-OCRv6_rec_small.onnx"
CLS_MODEL = "RapidOcr/ch_ppocr_mobile_v2.0_cls_mobile.onnx"


def ocr(png: bytes) -> list[dict[str, Any]]:
    """RapidOCR lines of one image, in RapidOCR's order: [{"text", "score", "box"}], where box
    is the four [x, y] corners in image pixels. [] when it finds no text. Loads the engine
    once per weights root (RapidOCR 3.9.2 defaults, text_score 0.5, onnxruntime 4 intra-op and
    1 inter-op threads, as #84 round 4 ran it); raises MethodUnavailable when a weight file is
    missing or the engine cannot load. Raises ValueError when png is not a decodable image."""
    raise NotImplementedError


def run(item: dict[str, Any], inputs: list[bytes]) -> MethodOutput:
    """inputs = [picture image PNG]. Lines from ocr() joined with "\\n" are the content.

    success  content = the joined text; provider artifact "ocr.json" = {"lines": ocr(...)}
    no_text  ocr() found no line; content ""; provider artifact "ocr.json" = {"lines": []}
    failed   reason RENDER_FAILED when the image cannot be decoded
    No evidence files (the picture image is native evidence already) and no signals."""
    raise NotImplementedError
