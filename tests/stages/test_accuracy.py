"""Accuracy of the local enrichment methods on synthetic pages whose ground truth is exact
(#132): every word in a picture, every character and indent of a listing, every table cell.
The corpus accuracy against the #84 gold runs outside CI (docs/validation/80/t3-accuracy/)."""

import io
import json
import re
import unicodedata
from typing import cast

import pypdfium2 as pdfium
from PIL import Image

from kp_processing.methods import InventoryItem, code
from tests.stages.test_enrich_local import (
    CODE,
    PICTURE_WORDS,
    TABLE,
    enriched,
    enriched_paper,
    items_of,
    native,
    records,
)


def normalized(text: str) -> str:
    """#84 score_ocr_v2: NFKC, whitespace removed; nothing else."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


async def outcome(ports, runtime, method: str) -> list[dict]:
    input = await enriched(ports, runtime, enriched_paper())
    return [r for item_id, r in (await records(ports, input.outcomes)).items()
            if item_id.startswith(f"{method}:")]  # fmt: skip


async def test_picture_ocr_reads_every_word_and_nothing_else(ports, runtime):
    words, empty = await outcome(ports, runtime, "picture-ocr")

    assert sorted(map(normalized, words["content"].split("\n"))) == sorted(
        map(normalized, PICTURE_WORDS)
    )
    lines = json.loads(await ports.store.get(words["provider_artifact_ref"]))["lines"]
    assert [line["text"] for line in lines] == words["content"].split("\n")
    assert all(0 < line["score"] <= 1 and len(line["box"]) == 4 for line in lines)
    assert (empty["outcome"], empty["content"]) == ("no_text", "")


async def test_code_keeps_every_character_line_and_indent(ports, runtime):
    (listing,) = await outcome(ports, runtime, "code")

    assert listing["content"] == "\n".join(CODE)  # character error rate 0
    assert listing["signals"] == {"indent_quantized": True}


async def test_code_reads_a_top_left_box_like_its_bottom_left_twin(ports, runtime):
    pdf = enriched_paper()
    input = await native(ports, runtime, pdf)
    (item,) = [i for i in await items_of(ports, input.inventory) if i["method"] == "code"]
    assert item["bbox"]["coord_origin"] == "BOTTOMLEFT"
    with pdfium.PdfDocument(pdf) as document:
        height = document[item["page"] - 1].get_height()
    box = item["bbox"]
    flipped = {**box, "t": height - box["t"], "b": height - box["b"], "coord_origin": "TOPLEFT"}

    output = code.run(cast(InventoryItem, {**item, "bbox": flipped}), [pdf])

    assert output.content == "\n".join(CODE)


async def test_table_status_delivers_every_cell_with_html_and_a_crop(ports, runtime):
    (table,) = await outcome(ports, runtime, "table-status")

    grid = table["content"]["grid"]
    assert (grid["num_rows"], grid["num_cols"]) == (4, 3)
    cells = sorted(grid["cells"], key=lambda c: (c["row"], c["col"]))
    assert [[c["text"].strip() for c in cells[r * 3 : r * 3 + 3]] for r in range(4)] == TABLE
    assert all((c["row_span"], c["col_span"]) == (1, 1) for c in cells)
    html = table["content"]["html"]
    assert [cell.strip() for cell in re.findall(r"<t[hd][^>]*>([^<]*)</t[hd]>", html)] == [
        cell for row in TABLE for cell in row
    ]
    (crop_ref,) = table["evidence_refs"]
    with Image.open(io.BytesIO(await ports.store.get(crop_ref))) as crop:
        width, height = crop.size
    # The ruled table spans 270 x 72 PDF points; the crop is page pixels at 2.0 per point.
    assert 0.8 * 540 <= width <= 1.2 * 540 and 0.8 * 144 <= height <= 1.2 * 144
