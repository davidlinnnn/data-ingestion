"""table-status: delivers a table's native grid and HTML with a crop for review; status only,
no model call (v2 §4; the dual cell-matching signal stays with #82)."""

from typing import Any

from kp_processing.methods import MethodOutput

ID = "table-status"
VERSION = 1
ORIGIN = None  # neither reconstruction nor interpretation: the content is the native grid


def run(item: dict[str, Any], inputs: list[bytes]) -> MethodOutput:
    """inputs = [assembly.json, page image PNG of item["page"]]. The table is the assembly
    document's node at item["target_ref"].

    success  content = {"html": the table's docling HTML export,
                        "grid": {"num_rows", "num_cols", "cells": [{"row", "col", "row_span",
                                 "col_span", "text", "column_header", "row_header"}]}}
             in docling's cell order; evidence "crop.png" = the page image cut to item["bbox"]
             (page image pixels = PDF points x 2.0, top-left origin)
    failed   reason NO_TABLE_CELLS when the table has no cells; RENDER_FAILED when the page
             image cannot be decoded or the box falls outside it
    No signals."""
    raise NotImplementedError
