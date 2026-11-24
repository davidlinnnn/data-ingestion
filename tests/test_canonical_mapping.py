"""The canonical-mapping seam (#81; docs/design/knowledge-platform-canonical-content-spec.md):
build() over a docling document made with docling-core's own API, and validate() over the
content it builds, changed one way per check."""

import copy
import hashlib
import json

import pytest
from docling_core.types.doc.base import BoundingBox, CoordOrigin, Size
from docling_core.types.doc.common.content_layer import ContentLayer
from docling_core.types.doc.common.reference import ProvenanceItem
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.items.table.table_data import TableCell, TableData
from docling_core.types.doc.labels import DocItemLabel, GroupLabel

from kp_canonicalization.methods import canonical_mapping as mapping
from kp_canonicalization.ports.object_store import DictObjectStore
from kp_canonicalization.stages import ProcessingFailure

UID = "doc_7"
ITEMS = f"documents/{UID}/items/"
PAGE_KEY, PICTURE_KEY, CROP_KEY = "a" * 64, "b" * 64, "c" * 64
PAGE_PNG, PICTURE_PNG, CROP_PNG = b"page-png", b"picture-png", b"crop-png"
DESCRIPTION = "A generated description of the bar chart"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prov(top: float) -> ProvenanceItem:
    box = BoundingBox(l=72, t=top, r=300, b=top - 10, coord_origin=CoordOrigin.BOTTOMLEFT)
    return ProvenanceItem(page_no=1, bbox=box, charspan=(0, 1))


def cell(text: str, row: int, col: int, cols: int = 1, header: bool = False) -> TableCell:
    return TableCell(text=text, start_row_offset_idx=row, end_row_offset_idx=row + 1,
                     start_col_offset_idx=col, end_col_offset_idx=col + cols, col_span=cols,
                     column_header=header)  # fmt: skip


def document() -> dict:
    doc = DoclingDocument(name="paper")
    doc.add_page(page_no=1, size=Size(width=612, height=792))
    doc.add_text(DocItemLabel.PAGE_HEADER, "Running head", prov=prov(780),
                 content_layer=ContentLayer.FURNITURE)  # fmt: skip  # texts/0
    doc.add_title("A paper", prov=prov(760))  # texts/1
    doc.add_heading("Method", level=1, prov=prov(740))  # texts/2
    doc.add_text(DocItemLabel.TEXT, "", orig="native words of a node", prov=prov(720))  # texts/3
    picture = doc.add_picture(prov=prov(600))  # pictures/0
    doc.add_text(DocItemLabel.TEXT, "axis label", parent=picture, prov=prov(590))  # texts/4
    caption = doc.add_text(DocItemLabel.CAPTION, "Figure 1: bars", parent=picture,
                           prov=prov(500))  # fmt: skip  # texts/5
    picture.captions.append(caption.get_ref())
    spanning = TableData(num_rows=2, num_cols=2, table_cells=[
        cell("Group", 0, 0, cols=2, header=True), cell("a", 1, 0), cell("b", 1, 1)])  # fmt: skip
    table = doc.add_table(data=spanning, prov=prov(400))  # tables/0
    table_caption = doc.add_text(DocItemLabel.CAPTION, "Table 1: spans", parent=table,
                                 prov=prov(300))  # fmt: skip  # texts/6
    table.captions.append(table_caption.get_ref())
    simple = TableData(num_rows=2, num_cols=2, table_cells=[
        cell("k", 0, 0, header=True), cell("v", 0, 1, header=True),
        cell("1", 1, 0), cell("2", 1, 1)])  # fmt: skip
    doc.add_table(data=simple, prov=prov(250))  # tables/1
    doc.add_text(DocItemLabel.FORMULA, "x = y + 1", prov=prov(200))  # texts/7
    doc.add_code("for i in x:\n    f(i)", prov=prov(150))  # texts/8
    items = doc.add_group(label=GroupLabel.LIST, name="list")  # groups/0: a container, no prov
    doc.add_list_item("first point", parent=items, prov=prov(100))  # texts/9
    doc.add_code("You are a judge.", parent=picture, prov=prov(560))  # texts/10: a boxed prompt
    return doc.export_to_dict()


def table(*rows: tuple[str, ...]) -> dict:
    """table-status content (spec §3.3): docling's HTML and the native grid, first row a header."""
    cells = [
        {"row": r, "col": c, "row_span": 1, "col_span": 1, "text": text,
         "column_header": r == 0, "row_header": False}
        for r, row in enumerate(rows) for c, text in enumerate(row)
    ]  # fmt: skip
    grid = {"num_rows": len(rows), "num_cols": len(rows[0]), "cells": cells}
    return {"html": "<table>…</table>", "grid": grid}


# The scores read under the wrong model: d3 judged the table unfaithful to its page (#84 U2).
WRONGLY_ASSOCIATED = table(("Model", "Score"), ("A", "0.9"), ("B", "0.4"))
D3_SIGNALS = {"d3": {"question": "Q2", "score": 0.14, "p": 0.012, "t_d": 0.31,
                     "model": "vllm-sr/d3-mini", "revision": "bd0090dd"}}  # fmt: skip


def enrichment(item_id: str, method: str, target: str, content, **fields) -> dict:
    return {
        "item_id": item_id,
        "result_ref": f"{ITEMS}{'d' * 64}/outcome.json",
        "method_ref": {"id": method, "version": 1, "digest": "e" * 64},
        "scope": "document" if target == "#" else "item",
        "origin": "interpretation" if method in ("picture-interpretation", "document-summary")
        else "reconstruction",
        "target_refs": [target],
        "input_refs": [f"{ITEMS}{PAGE_KEY}/pages/1.png"],
        "content": content,
        "evidence_refs": [],
        "status": "unverified",
        "status_reason": None,
        "signals": {},
        "provider_artifact_ref": f"{ITEMS}{'d' * 64}/response.json",
        "reused": False,
    } | fields  # fmt: skip


def result() -> dict:
    page = f"{ITEMS}{PAGE_KEY}/pages/{hashlib.sha256(PAGE_PNG).hexdigest()}.png"
    picture = f"{ITEMS}{PICTURE_KEY}/pictures/{hashlib.sha256(PICTURE_PNG).hexdigest()}.png"
    summary = {
        "overview": [{"text": "It measures bars.", "evidence": [{"section_id": "#/texts/2"}]}],
        "sections": [{"section_id": "#/texts/2", "heading": "Method",
                      "sentences": [{"text": "Bars."}]}],
    }  # fmt: skip
    return {
        "schema": "pdf-processing-result/v1",
        "request": {
            "request_id": "req_0123456789abcdef0123456789abcdef",
            "document_uid": UID,
            "source_revision_id": "srv_7",
            "adopted_version": "paper-pdf@1",
            "adoption_sequence": 3,
            "files": [
                {
                    "role": "main",
                    "custody_ref": "s3://kp-custody/custody/f",
                    "sha256": "f" * 64,
                    "size": 10,
                    "media_type": "application/pdf",
                }
            ],
        },  # fmt: skip
        "profile": {
            "id": "paper-pdf@1",
            "status_rule": "v1",
            "methods": [
                {
                    "id": "canonical-mapping",
                    "version": 1,
                    "components": [],
                    "module_digest": "9" * 64,
                }
            ],
            "runtime_identity": {"python": "3.12", "docling_slim": "2.132.0", "build_id": "1-r1"},
        },  # fmt: skip
        "outcome": "complete",
        "native": {
            "assembly_ref": f"{ITEMS}{PICTURE_KEY}/assembly.json",
            "page_groups": [],
            "page_images": [
                {"page": 1, "ref": page, "sha256": hashlib.sha256(PAGE_PNG).hexdigest()}
            ],
            "picture_images": [
                {
                    "picture_id": "#/pictures/0",
                    "page": 1,
                    "bbox": {},
                    "ref": picture,
                    "sha256": hashlib.sha256(PICTURE_PNG).hexdigest(),
                }
            ],
        },  # fmt: skip
        "inventory": {"ref": "inv", "counts": {}},
        "enrichments": [
            enrichment("picture-ocr:#/pictures/0", "picture-ocr", "#/pictures/0", "12 34"),
            enrichment(
                "picture-interpretation:#/pictures/0/description",
                "picture-interpretation",
                "#/pictures/0",
                DESCRIPTION,
            ),
            enrichment(
                "table-status:#/tables/0",
                "table-status",
                "#/tables/0",
                WRONGLY_ASSOCIATED,
                status="disputed",
                status_reason="TABLE_D3_UNFAITHFUL",
                signals=D3_SIGNALS,
            ),
            enrichment(
                "table-status:#/tables/1",
                "table-status",
                "#/tables/1",
                table(("k", "v"), ("a", "1")),
            ),
            enrichment(
                "formula:#/texts/7",
                "formula",
                "#/texts/7",
                "x = y + 1 \\quad",
                status="disputed",
                status_reason="FORMULA_NATIVE_MISMATCH",
                evidence_refs=[f"{ITEMS}{CROP_KEY}/crop.png"],
            ),
            enrichment("code:#/texts/8", "code", "#/texts/8", "for i in x:\n    f(i)"),
            enrichment("code:#/texts/10", "code", "#/texts/10", "You are a judge."),
            enrichment("document-summary:#", "document-summary", "#", summary),
        ],  # fmt: skip
        "limitations": [
            {"code": "INLINE_MATH_NOT_RECONSTRUCTED", "scope": "profile", "detail": "d"},
            {"code": "NO_TEXT_LAYER_PAGES", "scope": "document", "detail": "pages 3"},
        ],
    }


@pytest.fixture
def store() -> DictObjectStore:
    store = DictObjectStore()
    native = result()["native"]
    store.objects[native["page_images"][0]["ref"]] = PAGE_PNG
    store.objects[native["picture_images"][0]["ref"]] = PICTURE_PNG
    store.objects[f"{ITEMS}{CROP_KEY}/crop.png"] = CROP_PNG
    return store


async def built(store) -> dict:
    return json.loads(json.dumps(await mapping.build(result(), document(), store)))


def block(content: dict, ref: str) -> dict:
    return next(b for b in content["blocks"] if b["ref"] == ref)


# --- build: one test per row of #81 scope §2 --------------------------------------------------


async def test_blocks_follow_reading_order_and_render_the_body_markdown(store):
    content = await built(store)

    assert [b["ref"] for b in content["blocks"]] == [
        "#/texts/1", "#/texts/2", "#/texts/3", "#/pictures/0", "#/texts/5",
        "#/tables/0", "#/texts/6", "#/tables/1", "#/texts/7", "#/texts/8", "#/texts/9",
    ]  # fmt: skip
    assert block(content, "#/texts/9")["markdown"] == "- first point"
    assert [b["markdown"] for b in content["blocks"][:2]] == ["# A paper", "## Method"]
    box = {"l": 72.0, "t": 760.0, "r": 300.0, "b": 750.0, "coord_origin": "BOTTOMLEFT"}
    assert block(content, "#/texts/1")["locators"] == [{"page": 1, "bbox": box | {"unit": "pt"}}]
    assert content["pages"] == [{"page": 1, "width": 612.0, "height": 792.0,
                                 "image": content["artifacts"][0]["ref"]}]  # fmt: skip


async def test_an_empty_text_delivers_orig_marked_role_uncertain(store):
    content = await built(store)

    node = block(content, "#/texts/3")
    assert (node["text"], node["role_uncertain"], node["markdown"]) == (
        "native words of a node", True, "native words of a node",
    )  # fmt: skip
    assert block(content, "#/texts/1")["role_uncertain"] is False


async def test_text_inside_a_picture_is_its_native_text_and_its_caption_a_block(store):
    content = await built(store)

    picture = block(content, "#/pictures/0")
    assert [(t["ref"], t["text"]) for t in picture["native_text"]] == [
        ("#/texts/4", "axis label"), ("#/texts/10", "You are a judge."),
    ]  # fmt: skip
    assert picture["markdown"] == f"![]({picture['image']})"
    assert "axis label" not in "\n\n".join(b["markdown"] for b in content["blocks"])
    assert block(content, "#/texts/5")["kind"] == "caption"


async def test_a_spanning_table_is_html_once_and_a_simple_one_markdown_without_captions(store):
    content = await built(store)

    spanning = block(content, "#/tables/0")["markdown"]
    assert spanning.startswith("<table>")
    assert spanning.count("Group") == 1 and 'colspan="2"' in spanning
    simple = block(content, "#/tables/1")["markdown"]
    assert [c.strip() for c in simple.splitlines()[0].split("|")[1:3]] == ["k", "v"]
    assert "Table 1" not in spanning + simple  # the caption is its own block
    assert "text" not in block(content, "#/tables/0")


async def test_generated_content_is_only_in_the_pictures_supplement(store):
    content = await built(store)

    body = json.dumps(content["blocks"])
    assert DESCRIPTION not in body and "12 34" not in body
    supplement = [e["item_id"] for e in content["enrichments"]
                  if e["target_refs"] == ["#/pictures/0"]]  # fmt: skip
    assert supplement == ["picture-ocr:#/pictures/0",
                          "picture-interpretation:#/pictures/0/description"]  # fmt: skip


async def test_formula_and_code_take_their_enrichment_and_keep_the_native_text(store):
    content = await built(store)

    formula = block(content, "#/texts/7")
    assert formula["markdown"] == "$$\nx = y + 1 \\quad\n$$"
    assert formula["text"] == "x = y + 1"
    assert block(content, "#/texts/8")["markdown"] == "```\nfor i in x:\n    f(i)\n```"


async def test_a_table_known_to_be_wrongly_associated_keeps_its_grid_status_and_signals(store):
    content = await built(store)

    table = next(e for e in content["enrichments"] if e["item_id"] == "table-status:#/tables/0")
    assert table == {
        "item_id": "table-status:#/tables/0",
        "method_ref": {"id": "table-status", "version": 1, "digest": "e" * 64},
        "scope": "item",
        "origin": "reconstruction",
        "target_refs": ["#/tables/0"],
        "content": WRONGLY_ASSOCIATED,  # the grid only: no model, metric or value association
        "evidence_refs": [],
        "status": "disputed",  # delivered all the same (#84 U2)
        "status_reason": "TABLE_D3_UNFAITHFUL",
        "signals": D3_SIGNALS,
    }


async def test_evidence_is_a_reference_and_no_full_key_is_in_the_content(store):
    content = await built(store)

    formula = next(e for e in content["enrichments"] if e["item_id"] == "formula:#/texts/7")
    assert formula["evidence_refs"] == [f"{CROP_KEY}/crop.png"]
    assert "documents/" not in json.dumps(content)


async def test_two_kinds_of_limitation_and_furniture_left_out_by_rule(store):
    content = await built(store)

    assert [(x["code"], x["scope"]) for x in content["limitations"]] == [
        ("INLINE_MATH_NOT_RECONSTRUCTED", "profile"), ("NO_TEXT_LAYER_PAGES", "document"),
    ]  # fmt: skip
    assert content["omitted"] == [{"ref": "#/texts/0", "reason": "FURNITURE"}]
    assert "Running head" not in json.dumps(content["blocks"])


async def test_every_referenced_artifact_is_in_the_manifest_with_its_digest_and_size(store):
    content = await built(store)

    page = result()["native"]["page_images"][0]["ref"].removeprefix(ITEMS)
    picture = result()["native"]["picture_images"][0]["ref"].removeprefix(ITEMS)
    assert content["artifacts"] == [
        {"ref": page, "kind": "page_image", "media_type": "image/png",
         "sha256": hashlib.sha256(PAGE_PNG).hexdigest(), "size": len(PAGE_PNG)},
        {"ref": picture, "kind": "picture_image", "media_type": "image/png",
         "sha256": hashlib.sha256(PICTURE_PNG).hexdigest(), "size": len(PICTURE_PNG)},
        {"ref": f"{CROP_KEY}/crop.png", "kind": "evidence", "media_type": "image/png",
         "sha256": hashlib.sha256(CROP_PNG).hexdigest(), "size": len(CROP_PNG)},
    ]  # fmt: skip
    assert [a["ref"] for a in content["artifacts"]] == sorted(
        a["ref"] for a in content["artifacts"]
    )
    assert content["revision"]["canonical_revision_id"] == "crv_0123456789abcdef0123456789abcdef"


# --- validate: each check has a candidate that fails it (spec §6) ----------------------------


async def test_the_built_content_passes_validation(store):
    await mapping.validate(await built(store), result(), document(), store)


def broken(content: dict, change) -> dict:
    copied = copy.deepcopy(content)
    change(copied)
    return copied


CHANGES = {
    "SCHEMA": [
        lambda c: c.update(extra=1),
        lambda c: c["enrichments"][0].update(status="failed"),
        lambda c: c["enrichments"][0].update(status="verified"),
        lambda c: block(c, "#/tables/0").update(text="cells"),
        lambda c: block(c, "#/pictures/0").update(image=None),  # a picture without its image
        lambda c: c["enrichments"][2]["content"].update(association={"A": "0.9"}),
        lambda c: c["enrichments"][2]["content"]["grid"]["cells"][0].pop("row_span"),
        lambda c: c["enrichments"][-1]["content"]["sections"][0]["sentences"][0].pop("text"),
    ],
    "REFERENCE_FORM": [
        lambda c: [a.update(ref=ITEMS + a["ref"]) for a in c["artifacts"]]
        and c["pages"][0].update(image=ITEMS + c["pages"][0]["image"]),
        lambda c: c["enrichments"][4].update(evidence_refs=[f"{CROP_KEY}/../x.png"]),
    ],
    "REFERENCE_UNLISTED": [
        lambda c: c["artifacts"].pop(),
        lambda c: c["artifacts"].append({**c["artifacts"][0], "ref": f"{CROP_KEY}/other.png"}),
    ],
    "REFERENCE_UNRESOLVED": [
        lambda c: c["enrichments"][0].update(target_refs=["#/pictures/9"]),
        lambda c: c["enrichments"][-1]["content"]["sections"][0].update(section_id="#/texts/99"),
        lambda c: c["enrichments"].pop(3),  # tables/1 would have no status
        lambda c: c["blocks"].append(copy.deepcopy(c["blocks"][0])),
    ],
    "COVERAGE": [
        lambda c: c["blocks"].pop(2),  # a paragraph dropped
        lambda c: block(c, "#/texts/2").update(text="Methods"),  # a native text changed
        lambda c: block(c, "#/pictures/0")["native_text"].append(
            {**block(c, "#/pictures/0")["native_text"][0], "ref": "#/texts/1"}),  # delivered twice
        lambda c: c["omitted"].clear(),  # furniture neither delivered nor left out
        lambda c: c["omitted"].append({"ref": "#/texts/2", "reason": "FURNITURE"}),
    ],
}  # fmt: skip


@pytest.mark.parametrize(
    "check,change",
    [(check, change) for check, changes in CHANGES.items() for change in changes],
    ids=[f"{check}-{n}" for check, changes in CHANGES.items() for n in range(len(changes))],
)
async def test_a_candidate_that_breaks_a_check_fails_it_not_retryable(store, check, change):
    content = broken(await built(store), change)

    with pytest.raises(ProcessingFailure) as caught:
        await mapping.validate(content, result(), document(), store)

    failure = caught.value
    assert (failure.cause, failure.category, failure.reason, failure.retryable) == (
        "platform", "method", "CANONICAL_INVALID", False,
    )  # fmt: skip
    assert failure.metadata["check"] == check


@pytest.mark.parametrize(
    "damage",
    [
        lambda s, key: s.objects.pop(key),
        lambda s, key: s.objects.update({key: b"changed"}),
    ],
    ids=["missing", "changed"],
)
async def test_an_artifact_missing_or_changed_fails_retryable(store, damage):
    content = await built(store)
    damage(store, f"{ITEMS}{CROP_KEY}/crop.png")

    with pytest.raises(ProcessingFailure) as caught:
        await mapping.validate(content, result(), document(), store)

    failure = caught.value
    assert (failure.category, failure.reason, failure.retryable) == (
        "integrity", "ARTIFACT_MISMATCH", True,
    )  # fmt: skip
    assert failure.metadata == {"check": "ARTIFACT", "detail": f"{CROP_KEY}/crop.png"}


async def test_a_page_image_that_differs_from_its_declared_digest_fails(store):
    content = await built(store)
    page = result()["native"]["page_images"][0]["ref"]
    store.objects[page] = b"other"
    entry = next(a for a in content["artifacts"] if a["kind"] == "page_image")
    entry.update(sha256=hashlib.sha256(b"other").hexdigest(), size=5)  # manifest agrees, group not

    with pytest.raises(ProcessingFailure) as caught:
        await mapping.validate(content, result(), document(), store)

    assert caught.value.reason == "ARTIFACT_MISMATCH"
