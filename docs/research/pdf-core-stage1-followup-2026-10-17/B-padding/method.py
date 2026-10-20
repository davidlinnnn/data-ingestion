"""Offline candidate: explicit spans own exact-empty covered padding."""
from copy import deepcopy
from pathlib import Path
import importlib.util

from pydantic import create_model

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("padding_strict_protocol", HERE.parent / "B/protocol.py")
strict = importlib.util.module_from_spec(spec)
spec.loader.exec_module(strict)
# Reuse field validation; the original Grid still validates all structural rules.
GridFields = create_model("GridFields", __base__=strict.Shape, **{
    name: (field.annotation, deepcopy(field)) for name, field in strict.Grid.model_fields.items()})


def parse(payload, keys):
    normalized = deepcopy(payload)
    padding = []
    try:
        for target in normalized["targets"]:
            for index, panel in enumerate(target["panels"]):
                fields = GridFields.model_validate(panel["data"])
                grid = fields.grid
                rows, cols = len(grid), len(grid[0])
                if not 1 <= cols <= 64 or any(len(row) != cols for row in grid):
                    raise ValueError("grid must be rectangular, 1..64 columns")
                for span in fields.spans:
                    if span.row + span.rows > rows or span.col + span.cols > cols:
                        raise ValueError("span outside grid")
                    for row in range(span.row, span.row + span.rows):
                        for col in range(span.col, span.col + span.cols):
                            if (row, col) != (span.row, span.col) and grid[row][col] == "":
                                grid[row][col] = None
                                padding.append(dict(target_key=target["target_key"], panel=index, row=row, col=col))
                panel["data"] = fields.model_dump(mode="json")
    except (KeyError, TypeError) as error:
        raise ValueError("malformed response container") from error
    return strict.parse(normalized, keys), padding


def map_response(baseline, payload, page_no, keys):
    parsed, padding = parse(payload, keys)
    doc, bindings = strict.map_response(baseline, parsed.model_dump(mode="json"), page_no, keys)
    original = {target["target_key"]: target for target in payload["targets"]}
    for binding in bindings:
        key = binding["target_key"]
        binding["protocol"] = "grid-spans-v2-padding"
        binding["transport_provider"] = deepcopy(original[key])
        binding["covered_padding"] = [slot for slot in padding if slot["target_key"] == key]
    return doc, bindings
