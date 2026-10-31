"""Capture completed pages and assemble registered evidence with the stock document assembler."""

import io
import threading
from pathlib import PurePath
from typing import Any

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
from docling_core.types.doc.document import DoclingDocument

from kp_processing import weights
from kp_processing.methods.docling_parse import IMAGES_SCALE
from kp_processing.methods.docling_parse.serialization import (
    Group,
    SavedPage,
    capture_page,
    png_bytes,
)

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
    groups: list[Group], pages: list[Page]
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
        return document_json(document), picture_images(document)


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


def document_json(document: DoclingDocument) -> dict[str, Any]:
    copy = document.model_copy(deep=True)
    for page in copy.pages.values():
        page.image = None
    for picture in copy.pictures:
        picture.image = None
    return copy.export_to_dict()
