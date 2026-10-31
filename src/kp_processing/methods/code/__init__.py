"""code: a code block reconstructed from the native text layer, with indentation recovered
from character x coordinates."""

from contextlib import closing
from statistics import median
from typing import Any

import pypdfium2 as pdfium
from docling.utils.locks import pypdfium2_lock

from kp_processing.methods import InventoryItem, MethodOutput

ID = "code"
VERSION = 1
ORIGIN = "reconstruction"
TARGET = ("texts", "code")
INPUTS = ("source",)


def run(item: InventoryItem, inputs: list[bytes]) -> MethodOutput:
    """Reads the characters of page item["page"] with PDFium whose tight box centre lies
    inside item["bbox"] (PDF points), groups them into lines and recovers indentation. Every
    x position, width and gap below uses the loose (advance) character box.

    - a character joins a line when the vertical centres differ by at most 0.3 x the smaller
      line height; lines run top to bottom, characters left to right;
    - unit = median width of positioned space characters; without any, for a monospaced font
      (MAD of letter and digit widths <= 3% of their median), the median gap between
      neighbouring character x positions within 0.7x..1.5x the median width;
    - indent columns = round((line x_left - min x_left of the block) / unit); a rounding error
      above 0.3 on any line makes signals["indent_quantized"] False (otherwise True);
      without a unit, 4 spaces per distinct x level and indent_quantized False;
    - positioned PDF spaces are kept; a gap wider than 0.65 x unit between two non-space
      characters inserts max(1, round(gap / unit)) spaces.

    success  content = lines joined with "\\n", each indented with spaces, trailing whitespace
             stripped per line, no trailing newline
    failed   reason NO_TEXT_LAYER when no character lies inside the box
    No files, no evidence."""
    box = item["bbox"]
    characters = []
    with pypdfium2_lock, pdfium.PdfDocument(inputs[0]) as document:
        with closing(document[item["page"] - 1]) as page, closing(page.get_textpage()) as text:
            if box["coord_origin"] == "TOPLEFT":
                height = page.get_height()
                box = {**box, "t": height - box["t"], "b": height - box["b"]}
            for index in range(text.count_chars()):
                glyph = text.get_text_range(index, 1)
                if glyph in ("", "\r", "\n", "\r\n"):
                    continue
                left, bottom, right, top = text.get_charbox(index)
                if right <= left:
                    continue
                x, y = (left + right) / 2, (bottom + top) / 2
                if box["l"] <= x <= box["r"] and box["b"] <= y <= box["t"]:
                    characters.append(
                        {
                            "text": glyph,
                            # Tight ink boxes would put spurious spaces between glyphs like "):".
                            "bbox": text.get_charbox(index, loose=True),
                            "index": index,
                        }
                    )
    if not characters:
        return MethodOutput(outcome="failed", reason="NO_TEXT_LAYER")

    lines: list[dict[str, Any]] = []
    for char in sorted(
        characters,
        key=lambda c: (-(c["bbox"][1] + c["bbox"][3]) / 2, c["bbox"][0], c["index"]),
    ):
        _, bottom, _, top = char["bbox"]
        center, height = (bottom + top) / 2, max(top - bottom, 0.1)
        candidates = [
            line
            for line in lines
            if abs(line["center"] - center) <= 0.3 * min(line["height"], height)
        ]
        if candidates:
            line = min(candidates, key=lambda line: abs(line["center"] - center))
        else:
            line = {"center": center, "height": height, "chars": []}
            lines.append(line)
        line["chars"].append(char)
    lines.sort(key=lambda line: -line["center"])
    for line in lines:
        line["chars"].sort(key=lambda c: (c["bbox"][0], c["index"]))
        line["x_left"] = line["chars"][0]["bbox"][0]

    spaces = [c["bbox"][2] - c["bbox"][0] for c in characters if c["text"] == " "]
    unit = median(spaces) if spaces else None
    if unit is None:
        widths = [
            c["bbox"][2] - c["bbox"][0]
            for c in characters
            if c["text"].isalnum() and c["bbox"][2] > c["bbox"][0]
        ]
        if widths:
            width = median(widths)
            if median(abs(w - width) for w in widths) <= 0.03 * width:
                advances = [
                    b["bbox"][0] - a["bbox"][0]
                    for line in lines
                    for a, b in zip(line["chars"], line["chars"][1:], strict=False)
                    if 0.7 * width <= b["bbox"][0] - a["bbox"][0] <= 1.5 * width
                ]
                if advances:
                    unit = median(advances)
    origin = min(line["x_left"] for line in lines)
    levels = sorted({line["x_left"] for line in lines})
    quantized = unit is not None
    content = []
    for line in lines:
        if unit is not None:
            relative = (line["x_left"] - origin) / unit
            columns = round(relative)
            if abs(relative - columns) > 0.3:
                quantized = False
        else:
            columns = 4 * levels.index(line["x_left"])
        parts = []
        previous = None
        for char in line["chars"]:
            if previous is not None and unit is not None:
                gap = char["bbox"][0] - previous["bbox"][2]
                if (
                    not char["text"].isspace()
                    and not previous["text"].isspace()
                    and gap > 0.65 * unit
                ):
                    parts.append(" " * max(1, round(gap / unit)))
            parts.append(char["text"])
            previous = char
        content.append((" " * columns + "".join(parts)).rstrip())
    return MethodOutput(
        outcome="success", content="\n".join(content), signals={"indent_quantized": quantized}
    )
