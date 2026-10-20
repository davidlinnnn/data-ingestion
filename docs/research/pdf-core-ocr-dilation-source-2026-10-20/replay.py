"""Check retained Heron geometry through native dedup; no model initialization."""
import hashlib
import importlib.metadata
import json
from pathlib import Path

from docling.models.base_ocr_model import BaseOcrModel
from docling_core.types.doc import BoundingBox, Size

here = Path(__file__).resolve().parent
record = json.loads((here / "geometry.json").read_text())
source = Path(record["source"])
assert hashlib.sha256(source.read_bytes()).hexdigest() == record["source_sha256"]
assert importlib.metadata.version("docling-slim") == "2.132.0"
raw = json.loads(source.read_text())
boxes = [BoundingBox.model_validate(item["bbox"]) for item in raw["clusters"]]
size = Size.model_validate(raw["page_size"])
assert len(boxes) == 22 and not any(box.l < 306 < box.r for box in boxes)
for expected in record["dilation_sweep"]:
    _, regions = BaseOcrModel._deduplicate_rects(
        None, size, boxes, dilation_size=expected["kernel"]
    )
    assert [box.model_dump(mode="json") for box in regions] == expected["regions"]
    assert len(regions) == expected["region_count"]
    assert sum(box.l < 306 < box.r for box in regions) == expected["crosses_page_midline"]
print("Six native geometry contrasts reproduced; zero model inference.")
