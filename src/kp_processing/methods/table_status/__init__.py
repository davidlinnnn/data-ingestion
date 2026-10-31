"""table-status: delivers a table's native grid and HTML with a crop for review; status only,
no model call (v2 §4; the dual cell-matching signal stays with #82)."""

import io
import json
from functools import lru_cache
from typing import Any

from docling_core.types.doc.document import DoclingDocument
from PIL import Image

from kp_processing.methods import MethodOutput

ID = "table-status"
VERSION = 1
ORIGIN = None  # neither reconstruction nor interpretation: the content is the native grid


@lru_cache(maxsize=1)
def _document(assembly: bytes) -> DoclingDocument:
    return DoclingDocument.model_validate(json.loads(assembly)["document"])


def run(item: dict[str, Any], inputs: list[bytes]) -> MethodOutput:
    """inputs = [assembly.json, page image PNG of item["page"]]. The table is the assembly
    document's node at item["target_ref"].

    success  content = {"html": the table's docling HTML export,
                        "grid": {"num_rows", "num_cols", "cells": [{"row", "col", "row_span",
                                 "col_span", "text", "column_header", "row_header"}]}}
             in docling's cell order; evidence "crop.png" = the page image cut to item["bbox"]
             (page image pixels = PDF points x 2.0, top-left origin)
    failed   reason NO_TABLE_CELLS when the table has no cells; RENDER_FAILED when the page
             image cannot be decoded or the box clamped to the page is empty
    No signals."""
    document = _document(inputs[0])
    table = document.tables[int(item["target_ref"].rsplit("/", 1)[1])]
    if not table.data.table_cells:
        return MethodOutput(outcome="failed", reason="NO_TABLE_CELLS")
    try:
        with Image.open(io.BytesIO(inputs[1])) as image:
            image.load()
            box = item["bbox"]
            left, right = 2 * box["l"], 2 * box["r"]
            top, bottom = 2 * box["t"], 2 * box["b"]
            if box["coord_origin"] == "BOTTOMLEFT":
                top, bottom = image.height - top, image.height - bottom
            crop_box = (
                round(max(0, min(image.width, left))),
                round(max(0, min(image.height, top))),
                round(max(0, min(image.width, right))),
                round(max(0, min(image.height, bottom))),
            )
            if crop_box[0] >= crop_box[2] or crop_box[1] >= crop_box[3]:
                return MethodOutput(outcome="failed", reason="RENDER_FAILED")
            with image.crop(crop_box) as crop:
                png = io.BytesIO()
                crop.save(png, format="PNG")
    except (OSError, ValueError):
        return MethodOutput(outcome="failed", reason="RENDER_FAILED")
    return MethodOutput(
        outcome="success",
        content={
            "html": table.export_to_html(document),
            "grid": {
                "num_rows": table.data.num_rows,
                "num_cols": table.data.num_cols,
                "cells": [
                    {
                        "row": cell.start_row_offset_idx,
                        "col": cell.start_col_offset_idx,
                        "row_span": cell.row_span,
                        "col_span": cell.col_span,
                        "text": cell.text,
                        "column_header": cell.column_header,
                        "row_header": cell.row_header,
                    }
                    for cell in table.data.table_cells
                ],
            },
        },
        files={"crop.png": png.getvalue()},
        evidence=["crop.png"],
    )
