"""Seam A: parse group, assemble and inventory with real docling (#131). Needs the weights from
scripts/fetch-models under $DOCLING_ARTIFACTS_PATH (default ~/models/docling)."""

import hashlib
import io
import json
import os
from pathlib import Path

import pytest
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.datamodel.pipeline_options import (
    TableFormerMode,
    TableStructureOptions,
    ThreadedPdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.models.stages.layout.layout_model import LayoutModel
from docling.models.stages.page_preprocessing.page_preprocessing_model import (
    PagePreprocessingModel,
)
from docling.models.stages.table_structure.table_structure_model import TableStructureModel
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling_core.types.doc.base import BoundingBox, CoordOrigin
from docling_core.types.doc.common.reference import ProvenanceItem
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.items.text import FormulaItem, TextItem
from docling_core.types.doc.labels import DocItemLabel

from kp_canonicalization.identity import reuse_key
from kp_canonicalization.methods.docling_parse import pipeline
from kp_canonicalization.stages import (
    AssembleInput,
    GroupInput,
    GroupRef,
    PrepareInput,
    ProcessingFailure,
    parse,
    prepare,
)
from tests.pdfs import Page, paper, write_pdf
from tests.stages.conftest import start_input

ARTIFACTS = Path(os.environ.get("DOCLING_ARTIFACTS_PATH", Path.home() / "models/docling"))


def seven_pages() -> bytes:
    pages = paper(7, picture_on=(2,))
    pages[5] = Page(picture=True)  # page 6 has no text layer
    return write_pdf(pages)


async def parse_all(ports, runtime, pdf):
    start = await start_input(ports, pdf)
    plan = await prepare.run(PrepareInput(start=start, run_id="run_1"), ports, runtime)
    groups = [
        await parse.run_group(
            GroupInput("doc_1", plan.source_key, plan.source_sha256, pages), ports, runtime
        )
        for pages in plan.groups
    ]
    return start, plan, groups


def forbid_page_inference(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("page inference ran")

    for model in (PagePreprocessingModel, LayoutModel, TableStructureModel):
        monkeypatch.setattr(model, "__call__", refuse)


def method(runtime):
    return runtime.profile.methods["docling-parse"]


async def test_a_group_is_registered_once_under_its_reuse_key_with_page_images(ports, runtime):
    pdf = seven_pages()
    sha = hashlib.sha256(pdf).hexdigest()

    _, _, groups = await parse_all(ports, runtime, pdf)

    m = method(runtime)
    key = reuse_key("doc_1", m.ref, m.components, m.module_digest, [sha, "pages:1-5"])
    first = groups[0]
    assert first.ref == f"documents/doc_1/items/{key}/group.json"
    assert first.pages == [1, 5]
    assert first.reused is False
    stored = await ports.store.get(first.ref)
    assert first.digest == hashlib.sha256(stored).hexdigest()
    group = json.loads(stored)
    assert group["schema"] == "docling-parse-group/v1"
    assert group["pages"] == [1, 5]
    assert [image["page"] for image in group["page_images"]] == [1, 2, 3, 4, 5]
    for image in group["page_images"]:
        assert image["ref"].startswith(f"documents/doc_1/items/{key}/")
        png = await ports.store.get(image["ref"])
        assert png.startswith(b"\x89PNG") and hashlib.sha256(png).hexdigest() == image["sha256"]
    assert [g.pages for g in groups] == [[1, 5], [6, 7]]


async def test_a_registered_group_is_reused_without_inference(ports, runtime, monkeypatch):
    pdf = seven_pages()
    _, plan, groups = await parse_all(ports, runtime, pdf)
    before = dict(ports.store.objects)  # type: ignore[attr-defined]
    forbid_page_inference(monkeypatch)

    again = await parse.run_group(
        GroupInput("doc_1", plan.source_key, plan.source_sha256, [1, 5]), ports, runtime
    )

    assert again == GroupRef(pages=[1, 5], ref=groups[0].ref, digest=groups[0].digest, reused=True)
    assert ports.store.objects == before  # type: ignore[attr-defined]


async def test_assemble_rebuilds_the_document_from_groups_without_page_inference(
    ports, runtime, monkeypatch
):
    pdf = seven_pages()
    _, plan, groups = await parse_all(ports, runtime, pdf)
    forbid_page_inference(monkeypatch)

    assembly = await parse.run_assemble(
        AssembleInput("doc_1", plan.source_key, plan.source_sha256, groups), ports, runtime
    )

    m = method(runtime)
    key = reuse_key("doc_1", m.ref, m.components, m.module_digest, [g.digest for g in groups])
    assert assembly.ref == f"documents/doc_1/items/{key}/assembly.json"
    assert assembly.reused is False
    stored = await ports.store.get(assembly.ref)
    assert assembly.digest == hashlib.sha256(stored).hexdigest()
    body = json.loads(stored)
    assert body["schema"] == "docling-parse-assembly/v1"
    assert body["groups"] == [{"pages": g.pages, "ref": g.ref, "digest": g.digest} for g in groups]
    document = DoclingDocument.model_validate(body["document"])
    assert sorted(document.pages) == [1, 2, 3, 4, 5, 6, 7]
    assert "Line 3 of page 7" in document.export_to_markdown()
    pictures = body["picture_images"]
    assert [(p["picture_id"], p["page"]) for p in pictures][:1] == [("#/pictures/0", 2)]
    for picture in pictures:
        assert set(picture["bbox"]) >= {"l", "t", "r", "b", "coord_origin"}
        png = await ports.store.get(picture["ref"])
        assert hashlib.sha256(png).hexdigest() == picture["sha256"]

    again = await parse.run_assemble(
        AssembleInput("doc_1", plan.source_key, plan.source_sha256, groups), ports, runtime
    )
    assert (again.ref, again.digest, again.reused) == (assembly.ref, assembly.digest, True)


async def test_the_assembled_text_equals_a_single_pass_conversion(ports, runtime):
    """The #84 configuration (#131): StandardPdfPipeline with PyPdfiumDocumentBackend, Heron
    with reading-order separators, TableFormer accurate with cell matching, no body OCR."""
    pdf = seven_pages()
    _, plan, groups = await parse_all(ports, runtime, pdf)
    assembly = await parse.run_assemble(
        AssembleInput("doc_1", plan.source_key, plan.source_sha256, groups), ports, runtime
    )
    options = ThreadedPdfPipelineOptions(
        artifacts_path=ARTIFACTS,
        do_ocr=False,
        do_table_structure=True,
        use_reading_order_separators=True,
        table_structure_options=TableStructureOptions(
            mode=TableFormerMode.ACCURATE, do_cell_matching=True
        ),
        accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU),
    )
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=StandardPdfPipeline,
                pipeline_options=options,
                backend=PyPdfiumDocumentBackend,
            )
        }
    )
    single = converter.convert(DocumentStream(name="paper.pdf", stream=io.BytesIO(pdf))).document

    body = json.loads(await ports.store.get(assembly.ref))
    assembled = DoclingDocument.model_validate(body["document"])
    assert assembled.export_to_markdown() == single.export_to_markdown()


def test_a_formula_whose_text_layer_is_one_identifier_becomes_a_text_line():
    """#212: the layout labels a list of SWE-bench ids as formulas; real formulas stay."""
    document = DoclingDocument(name="paper")
    identifiers = ["· django__django-12754", "sphinx-doc__sphinx-10449", "config.yaml"]
    formulas = ["L = 2x + 3y", "x-1", "xij", "softmax", "a t i", "αi", "softmax(x)", ""]
    for orig in identifiers + formulas:
        document.add_text(label=DocItemLabel.FORMULA, text="", orig=orig)

    texts = DoclingDocument.model_validate(
        pipeline.document_json(document, write_pdf([Page()]))
    ).texts

    assert [(type(t), t.text) for t in texts] == [
        *[(TextItem, orig) for orig in identifiers],
        *[(FormulaItem, "") for _ in formulas],
    ]


def line(page: int, index: int, text: str) -> ProvenanceItem:
    """The box of line `index` as tests.pdfs.write_pdf draws it on a 612 x 792 pt page."""
    y = 720 if index == 0 else 696 - 16 * (index - 1)
    box = BoundingBox(l=70, t=y + 12, r=560, b=y - 4, coord_origin=CoordOrigin.BOTTOMLEFT)
    return ProvenanceItem(page_no=page, bbox=box, charspan=(0, len(text)))


def labels(document: DoclingDocument, pdf: bytes) -> list[tuple[str, str]]:
    texts = DoclingDocument.model_validate(pipeline.document_json(document, pdf)).texts
    return [(t.label.value, t.orig) for t in texts]


def test_the_lines_around_a_monospaced_code_node_in_its_font_become_code():
    """#210: the layout labels part of a prompt listing as code and the rest as body text."""
    mono = [
        "You are an assistant for questions.",
        "## Task",
        "1. Answer the question briefly.",
        "Respond with JSON only: {answer}",
        "Return nothing else, please.",
    ]
    pdf = write_pdf([Page(lines=[
        "Prompts", "The agent receives this prompt.", *[[("Courier", m)] for m in mono],
        "Figure 1: the prompt template.", [("Courier", "Courier after the caption stays.")],
    ])])  # fmt: skip
    document = DoclingDocument(name="paper")
    document.add_heading("Prompts", prov=line(1, 0, "Prompts"))
    document.add_text(DocItemLabel.TEXT, "The agent receives this prompt.",
                      prov=line(1, 1, "The agent receives this prompt."))  # fmt: skip
    document.add_text(DocItemLabel.TEXT, mono[0], prov=line(1, 2, mono[0]))
    document.add_heading(mono[1], prov=line(1, 3, mono[1]))
    group = document.add_list_group()
    document.add_list_item(mono[2], enumerated=True, parent=group, prov=line(1, 4, mono[2]))
    document.add_code(mono[3], prov=line(1, 5, mono[3]))
    document.add_text(DocItemLabel.TEXT, mono[4], prov=line(1, 6, mono[4]))
    caption = "Figure 1: the prompt template."
    document.add_text(DocItemLabel.CAPTION, caption, prov=line(1, 7, caption))
    after = "Courier after the caption stays."
    document.add_text(DocItemLabel.TEXT, after, prov=line(1, 8, after))

    assert labels(document, pdf) == [
        ("section_header", "Prompts"),
        ("text", "The agent receives this prompt."),
        *[("code", m) for m in mono],
        ("caption", caption),
        ("text", after),
    ]


def test_a_code_node_across_pages_becomes_one_code_node_per_page():
    """#210: the inventory reads a node's first provenance only, which missed the second page."""
    first, second = "for item in items:", "    print(item)"
    pages = [Page(lines=["Listing", [("Courier", first)]]),
             Page(lines=[[("Courier", second)], "Body text after the listing."])]  # fmt: skip
    pdf = write_pdf(pages)
    document = DoclingDocument(name="paper")
    document.add_heading("Listing", prov=line(1, 0, "Listing"))
    code = document.add_code(f"{first} {second}", prov=line(1, 1, first))
    start = len(first) + 1
    code.prov.append(
        line(2, 0, second).model_copy(update={"charspan": (start, start + len(second))})
    )
    document.add_text(DocItemLabel.TEXT, "Body text after the listing.",
                      prov=line(2, 1, "Body text after the listing."))  # fmt: skip

    data = pipeline.document_json(document, pdf)
    order = pipeline.reading_order(data)

    assert [(n["label"], n["orig"], [p["page_no"] for p in n["prov"]]) for n in order] == [
        ("section_header", "Listing", [1]),
        ("code", first, [1]),
        ("code", second, [2]),
        ("text", "Body text after the listing.", [2]),
    ]
    assert DoclingDocument.model_validate(data).texts[-1].prov[0].charspan == (0, len(second))


def test_a_code_node_in_a_proportional_font_takes_no_neighbour():
    """Pseudocode set in the body font: its neighbours are body text in that font."""
    body = [
        f"Then the model {word} converges quickly on benchmark number {n}."
        for n, word in enumerate(("always", "usually", "rarely", "sometimes", "never"))
    ]
    pdf = write_pdf([Page(lines=["Method", "for each step do update the weights", *body])])
    document = DoclingDocument(name="paper")
    document.add_heading("Method", prov=line(1, 0, "Method"))
    document.add_code("for each step do update the weights",
                      prov=line(1, 1, "for each step do update the weights"))  # fmt: skip
    for n, text in enumerate(body, start=2):
        document.add_text(DocItemLabel.TEXT, text, prov=line(1, n, text))

    assert labels(document, pdf) == [
        ("section_header", "Method"),
        ("code", "for each step do update the weights"),
        *[("text", text) for text in body],
    ]


async def test_groups_that_do_not_cover_every_page_fail_integrity(ports, runtime):
    _, plan, groups = await parse_all(ports, runtime, seven_pages())

    with pytest.raises(ProcessingFailure) as caught:
        await parse.run_assemble(
            AssembleInput("doc_1", plan.source_key, plan.source_sha256, groups[:1]), ports, runtime
        )

    assert (caught.value.cause, caught.value.category, caught.value.reason) == (
        "platform", "integrity", "NATIVE_COVERAGE_INCOMPLETE",
    )  # fmt: skip


async def test_a_group_whose_bytes_differ_from_its_digest_fails_integrity(ports, runtime):
    _, plan, groups = await parse_all(ports, runtime, seven_pages())
    stale = GroupRef(groups[1].pages, groups[1].ref, "0" * 64, False)

    with pytest.raises(ProcessingFailure) as caught:
        await parse.run_assemble(
            AssembleInput("doc_1", plan.source_key, plan.source_sha256, [groups[0], stale]),
            ports,
            runtime,
        )

    assert caught.value.reason == "NATIVE_COVERAGE_INCOMPLETE"
