"""Capture completed pages and assemble registered evidence with the stock document assembler,
then relabel as text each formula whose text layer is one identifier (#212), and as code the
lines of a listing the layout labels as body text (#210)."""

import ctypes
import io
import re
import threading
from collections import Counter
from collections.abc import Callable
from contextlib import closing
from itertools import pairwise
from pathlib import PurePath
from statistics import median
from typing import Any, NamedTuple

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import (
    ConversionStatus,
    DocumentStream,
    InputFormat,
    Page,
    PageConfidenceScores,
)
from docling.datamodel.document import ConversionResult, InputDocument
from docling.datamodel.pipeline_options import (
    TableFormerMode,
    TableStructureOptions,
    ThreadedPdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.models.stages.heading_hierarchy.heading_hierarchy_model import HeadingHierarchyModel
from docling.models.stages.reading_order.readingorder_model import (
    ReadingOrderModel,
    ReadingOrderOptions,
)
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline, ThreadedItem
from docling.utils.locks import pypdfium2_lock
from docling_core.types.doc.document import DoclingDocument

from kp_canonicalization import weights
from kp_canonicalization.methods.docling_parse import IMAGES_SCALE
from kp_canonicalization.methods.docling_parse.serialization import (
    Group,
    SavedPage,
    capture_page,
    png_bytes,
)

# One identifier such as "· django__django-12754" (#212): math joins no word with _ . / or -
IDENTIFIER = re.compile(
    r"(?:[·•]\s+)?(?=[\w./-]*[A-Za-z]{3})(?=[\w./-]*[A-Za-z0-9][_./-]+[A-Za-z0-9])[\w./-]+",
    re.ASCII,
)
# Labels the layout gives to the lines of a listing it does not see as code (#210)
LISTING_LABELS = ("text", "list_item", "section_header")

_lock = threading.Lock()
_converter: DocumentConverter | None = None


def options() -> ThreadedPdfPipelineOptions:
    return ThreadedPdfPipelineOptions(
        artifacts_path=weights.root(),
        do_ocr=False,
        do_table_structure=True,
        use_reading_order_separators=True,
        table_structure_options=TableStructureOptions(
            mode=TableFormerMode.ACCURATE, do_cell_matching=True
        ),
        generate_page_images=True,
        generate_picture_images=True,
        images_scale=IMAGES_SCALE,
        accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU),
    )


class CapturePipeline(StandardPdfPipeline):
    def __init__(self, pipeline_options: ThreadedPdfPipelineOptions) -> None:
        super().__init__(pipeline_options)
        self.captured: dict[int, tuple[SavedPage, bytes]] = {}

    def _build_document(self, conv_res: ConversionResult) -> ConversionResult:
        self.captured = {}
        return super()._build_document(conv_res)

    def _release_page_resources(self, item: ThreadedItem) -> None:
        try:
            page = item.payload
            if page is not None and not item.is_failed:
                if page.image is None:
                    raise ValueError("Completed page has no image")
                self.captured[page.page_no] = (
                    capture_page(page, item.conv_res.confidence.pages[page.page_no]),
                    png_bytes(page.image),
                )
        finally:
            super()._release_page_resources(item)

    def _assemble_document(self, conv_res: ConversionResult) -> ConversionResult:
        return conv_res


class AssemblyPipeline(StandardPdfPipeline):
    def _init_models(self) -> None:
        self.reading_order_model = ReadingOrderModel(
            options=ReadingOrderOptions(
                use_page_separators=self.pipeline_options.use_reading_order_separators
            )
        )
        self.heading_hierarchy_model = HeadingHierarchyModel(
            options=self.pipeline_options.heading_hierarchy_options
        )
        self.keep_images = True
        self.keep_backend = False


def parse_group(data: bytes, pages: list[int]) -> tuple[int, list[tuple[SavedPage, bytes]]]:
    global _converter
    with _lock:
        if _converter is None:
            _converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_cls=CapturePipeline,
                        pipeline_options=options(),
                        backend=PyPdfiumDocumentBackend,
                    )
                }
            )
        pipeline = _converter._get_pipeline(InputFormat.PDF)
        assert isinstance(pipeline, CapturePipeline)
        try:
            result = _converter.convert(
                DocumentStream(name="paper.pdf", stream=io.BytesIO(data)),
                page_range=(pages[0], pages[1]),
            )
            expected = list(range(pages[0], pages[1] + 1))
            if (
                result.status != ConversionStatus.SUCCESS
                or result.errors
                or sorted(pipeline.captured) != expected
            ):
                raise ValueError("Group conversion did not complete every page")
            return result.input.page_count, [pipeline.captured[number] for number in expected]
        finally:
            pipeline.captured = {}


def assemble(
    groups: list[Group], pages: list[Page], source: bytes
) -> tuple[dict[str, Any], list[tuple[dict[str, Any], bytes]]]:
    with _lock:
        first = groups[0]
        # The validated group metadata supplies assembly identity without reopening the source.
        input = InputDocument.model_construct(
            file=PurePath(first.source_name),
            document_hash=first.source_sha256,
            format=InputFormat.PDF,
            page_count=first.page_count,
        )
        result = ConversionResult(input=input, pages=pages, status=ConversionStatus.SUCCESS)
        result.confidence.pages = {
            saved.page_no: PageConfidenceScores.model_validate(saved.confidence)
            for group in groups
            for saved in group.page_results
        }
        pipeline = AssemblyPipeline(options())
        pipeline._page_sizes_by_no = {
            page.page_no: page.size for page in pages if page.size is not None
        }
        document = pipeline._assemble_document(result).document
        return document_json(document, source), picture_images(document)


def picture_images(document: DoclingDocument) -> list[tuple[dict[str, Any], bytes]]:
    images = []
    for picture in document.pictures:
        if picture.image is None or not picture.prov:
            raise ValueError("Assembled picture has no image or provenance")
        image = picture.image.pil_image
        if image is None:
            raise ValueError("Assembled picture image cannot be loaded")
        provenance = picture.prov[0]
        images.append(
            (
                {
                    "picture_id": picture.self_ref,
                    "page": provenance.page_no,
                    "bbox": provenance.bbox.model_dump(mode="json"),
                },
                png_bytes(image),
            )
        )
    return images


def document_json(document: DoclingDocument, source: bytes) -> dict[str, Any]:
    copy = document.model_copy(deep=True)
    for page in copy.pages.values():
        page.image = None
    for picture in copy.pictures:
        picture.image = None
    data = copy.export_to_dict()
    for node in data["texts"]:
        if node["label"] == "formula" and IDENTIFIER.fullmatch(node["orig"]):
            node.update(label="text", text=node["orig"])
    whole_listings(data, source)
    return data


class Character(NamedTuple):
    glyph: str
    font: str
    x: float  # tight box centre
    y: float
    origin_x: float
    origin_y: float


def page_characters(document: pdfium.PdfDocument, number: int) -> list[Character]:
    font = ctypes.create_string_buffer(256)
    flags = ctypes.c_int()
    x, y = ctypes.c_double(), ctypes.c_double()
    characters = []
    with closing(document[number - 1]) as page, closing(page.get_textpage()) as text:
        for index in range(text.count_chars()):
            pdfium_c.FPDFText_GetFontInfo(text, index, font, len(font), flags)
            pdfium_c.FPDFText_GetCharOrigin(text, index, x, y)
            left, bottom, right, top = text.get_charbox(index)
            characters.append(
                Character(
                    text.get_text_range(index, 1),
                    font.value.decode(errors="replace"),
                    (left + right) / 2,
                    (bottom + top) / 2,
                    x.value,
                    y.value,
                )
            )
    return characters


def monospaced(characters: list[Character], font: str) -> bool:
    """At least half of the runs of `font` advance evenly, a run being the characters between
    spaces on one baseline with at least 5 steps and 4 distinct glyphs, and even meaning every
    step within 4 % of the run's median. Origins, not font sizes: a scaled font reports size 1."""
    runs: list[list[Character]] = []
    run: list[Character] = []
    for character in characters:
        if run and (
            not character.glyph.strip()
            or character.font != run[-1].font
            or abs(character.origin_y - run[-1].origin_y) > 0.1
        ):
            runs.append(run)
            run = []
        if character.glyph.strip():
            run.append(character)
    runs.append(run)
    even = []
    for run in runs:
        steps = [b.origin_x - a.origin_x for a, b in pairwise(run)]
        if run and run[0].font == font and len(steps) >= 5 and len({c.glyph for c in run}) >= 4:
            middle = median(steps)
            even.append(middle > 0 and all(abs(s - middle) <= 0.04 * middle for s in steps))
    return len(even) >= 5 and sum(even) * 2 >= len(even)


def node_fonts(
    data: dict[str, Any], node: dict[str, Any], characters: Callable[[int], list[Character]]
) -> Counter[str]:
    fonts: Counter[str] = Counter()
    for provenance in node["prov"]:
        number, box = provenance["page_no"], provenance["bbox"]
        top, bottom = box["t"], box["b"]
        if box["coord_origin"] == "TOPLEFT":
            height = data["pages"][str(number)]["size"]["height"]
            top, bottom = height - top, height - bottom
        fonts.update(
            c.font
            for c in characters(number)
            if c.glyph.strip() and box["l"] <= c.x <= box["r"] and bottom <= c.y <= top
        )
    return fonts


def resolve(data: dict[str, Any], ref: str) -> dict[str, Any]:
    _, kind, *index = ref.split("/")  # "#/body" or "#/texts/3"
    return data[kind][int(index[0])] if index else data[kind]


def reading_order(data: dict[str, Any]) -> list[dict[str, Any]]:
    """The body's items depth first; groups are containers, not items, and page headers and
    footers, which docling may attach to the body, are furniture, not items."""
    order = []

    def visit(ref: str) -> None:
        node = resolve(data, ref)
        if not ref.startswith("#/groups/") and node.get("content_layer", "body") == "body":
            order.append(node)
        for child in node.get("children", []):
            visit(child["$ref"])

    for child in data["body"]["children"]:
        visit(child["$ref"])
    return order


def whole_listings(data: dict[str, Any], source: bytes) -> None:
    """Relabel as code the text, list item and heading nodes next to a code node in reading
    order whose most common font is that code node's, when that font is monospaced on the code
    node's pages; then split each code node into one node per provenance (#210)."""
    order = reading_order(data)
    listing = set()
    with pypdfium2_lock, pdfium.PdfDocument(source) as document:
        pages: dict[int, list[Character]] = {}

        def characters(number: int) -> list[Character]:
            if number not in pages:
                pages[number] = page_characters(document, number)
            return pages[number]

        for at, anchor in enumerate(order):
            if anchor["label"] != "code" or not (fonts := node_fonts(data, anchor, characters)):
                continue
            font = fonts.most_common(1)[0][0]
            numbers = sorted({p["page_no"] for p in anchor["prov"]})
            if not monospaced([c for n in numbers for c in characters(n)], font):
                continue
            for step in (-1, 1):
                index = at + step
                while 0 <= index < len(order) and order[index]["label"] in (
                    *LISTING_LABELS,
                    "code",
                ):
                    fonts = node_fonts(data, order[index], characters)
                    if not fonts or fonts.most_common(1)[0][0] != font:
                        break
                    listing.add(order[index]["self_ref"])
                    index += step
    for node in data["texts"]:
        if node["self_ref"] in listing and node["label"] != "code":
            for key in ("enumerated", "marker", "level"):
                node.pop(key, None)
            node.update(label="code", text=node["orig"], captions=[], references=[],
                        footnotes=[], code_language="unknown")  # fmt: skip
    split_pages(data)


def split_pages(data: dict[str, Any]) -> None:
    """Give each provenance but the first of a code node a new code node right after it in
    texts and in its parent's children, with the part of orig its charspan names, then
    renumber every text reference, so that texts stays in document order."""
    texts, renamed = [], {}
    for node in data["texts"]:
        renamed[node["self_ref"]] = f"#/texts/{len(texts)}"
        texts.append(node)
        if node["label"] != "code" or len(node["prov"]) < 2:
            continue
        orig = node["orig"]
        parts = []
        for provenance in node["prov"]:
            start, end = provenance["charspan"]
            parts.append((orig[start:end], {**provenance, "charspan": [0, end - start]}))
        (text, provenance), *rest = parts
        node.update(orig=text, text=text, prov=[provenance])
        siblings = resolve(data, node["parent"]["$ref"])["children"]
        at = next(i for i, c in enumerate(siblings) if c["$ref"] == node["self_ref"])
        for offset, (text, provenance) in enumerate(rest, start=1):
            ref = f"split:{len(texts)}"
            renamed[ref] = f"#/texts/{len(texts)}"
            texts.append({**node, "self_ref": ref, "children": [], "orig": text, "text": text,
                          "prov": [provenance], "captions": [], "references": [],
                          "footnotes": []})  # fmt: skip
            siblings.insert(at + offset, {"$ref": ref})
    data["texts"] = texts

    def renumber(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ("$ref", "self_ref") and item in renamed:
                    value[key] = renamed[item]
                else:
                    renumber(item)
        elif isinstance(value, list):
            for item in value:
                renumber(item)

    renumber(data)
