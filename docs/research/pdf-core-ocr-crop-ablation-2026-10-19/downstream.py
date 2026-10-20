"""Replay retained S0 downstream methods without initializing any inference model."""
import hashlib
import importlib.util
import json
from pathlib import Path
import time

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import Cluster, InputFormat, LayoutPrediction, Page
from docling.datamodel.document import ConversionResult, InputDocument
from docling.datamodel.pipeline_options import LayoutPostprocessorOptions
from docling.datamodel.settings import DocumentLimits
from docling.models.base_ocr_model import BaseOcrModel
from docling.models.stages.heading_hierarchy.heading_hierarchy_model import HeadingHierarchyModel
from docling.models.stages.layout.layout_postprocessing_model import LayoutPostprocessingModel
from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
from docling.models.stages.page_assemble.page_assemble_model import PageAssembleModel, PageAssembleOptions
from docling.models.stages.page_preprocessing.page_preprocessing_model import PagePreprocessingModel, PagePreprocessingOptions
from docling.models.stages.reading_order.readingorder_model import ReadingOrderModel, ReadingOrderOptions
from docling.models.stages.table_structure.table_structure_model import TableStructureModel
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
from docling_core.types.doc import DocItemLabel
from docling_core.types.doc.page import TextCell

HERE = Path(__file__).resolve().parent
TRACE = HERE.parent / "pdf-core-ocr-boundary-trace-2026-10-19"
RETAINED = HERE.parent / "pdf-core-native-round-2026-10-17"


def read(path):
    return json.loads(Path(path).read_text())


def retained_options():
    spec = importlib.util.spec_from_file_location("retained_s0_downstream", RETAINED / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.options("S0")


def replay(cells: list[TextCell]) -> dict:
    """Use native ordering/merge/assembly; input cells are cloned, never repaired."""
    started = time.monotonic()
    saved = read(TRACE / "live/result.json")
    raw = read(TRACE / "live/trace/layout-clusters-001.json")
    options = retained_options()
    assert options.generate_page_images and not options.heading_hierarchy_options.enabled
    source = Path(saved["input"]["file"])
    assert hashlib.sha256(source.read_bytes()).hexdigest() == saved["input"]["document_hash"]
    in_doc = InputDocument(source, format=InputFormat.PDF, backend=PyPdfiumDocumentBackend,
                           limits=DocumentLimits(page_range=(1, 1)))
    assert in_doc.valid and in_doc.document_hash == saved["input"]["document_hash"]
    conv = ConversionResult(input=in_doc)
    page = Page(page_no=1)
    page._backend = in_doc._backend.load_page(0)
    try:
        page.size = page._backend.get_size()
        conv.pages = [page]
        page = list(PagePreprocessingModel(options=PagePreprocessingOptions(
            images_scale=options.images_scale,
            capture_reading_order_separators=options.use_reading_order_separators,
        ))(conv, [page]))[0]
        assert page.size.model_dump(mode="json") == raw["page_size"]
        assert page.parsed_page is not None
        assert not page.cells and not page.parsed_page.char_cells and not page.parsed_page.word_cells, "fixture unexpectedly has native text"
        page.predictions.layout = LayoutPrediction(clusters=[Cluster.model_validate(c) for c in raw["clusters"]])
        prep_seconds = time.monotonic() - started
        downstream_started = time.monotonic()

        # Constructor-free shells call only SDK methods whose required state is explicit; no weights.
        ocr = RapidOcrModel.__new__(RapidOcrModel)
        ocr.options = options.ocr_options
        BaseOcrModel.post_process_cells(ocr, [c.model_copy(deep=True) for c in cells], page, conv)
        after_ocr = [c.model_dump(mode="json") for c in page.cells]
        lo = options.layout_options
        layout = LayoutPostprocessingModel(options=LayoutPostprocessorOptions(
            skip_cell_assignment=lo.skip_cell_assignment,
            keep_empty_clusters=lo.keep_empty_clusters,
            create_orphan_clusters=lo.create_orphan_clusters,
            run_postprocessor=True,
        ))
        page.predictions.layout = layout.postprocess_layout(conv, [page])[0]
        postlayout = page.predictions.layout.model_dump(mode="json")
        assert not any(c.label in (DocItemLabel.TABLE, DocItemLabel.DOCUMENT_INDEX)
                       for c in page.predictions.layout.clusters), "no-table replay guard failed"
        table = TableStructureModel.__new__(TableStructureModel)
        table.scale = 2.0
        table.enabled = True
        # The SDK's empty-table branch exits before reading a predictor or image.
        page.predictions.tablestructure = table.predict_tables(conv, [page])[0]
        assert page.predictions.tablestructure.model_dump(mode="json") == {"table_map": {}}
        page = list(PageAssembleModel(options=PageAssembleOptions())(conv, [page]))[0]

        pipeline = StandardPdfPipeline.__new__(StandardPdfPipeline)
        pipeline.pipeline_options = options
        pipeline._page_sizes_by_no = {1: page.size}
        pipeline.reading_order_model = ReadingOrderModel(options=ReadingOrderOptions(
            use_page_separators=options.use_reading_order_separators))
        pipeline.heading_hierarchy_model = HeadingHierarchyModel(options=options.heading_hierarchy_options)
        conv = pipeline._assemble_document(conv)
        markdown = conv.document.export_to_markdown()
        return {
            "after_ocr_cells": after_ocr,
            "parsed_cells": [c.model_dump(mode="json") for c in page.cells],
            "postlayout": postlayout,
            "table_structure": page.predictions.tablestructure.model_dump(mode="json"),
            "assembled": page.assembled.model_dump(mode="json"),
            "document": conv.document.model_dump(mode="json"),
            "markdown": markdown,
            "cost": {"prepare_seconds": prep_seconds,
                     "downstream_seconds": time.monotonic() - downstream_started,
                     "total_seconds": time.monotonic() - started,
                     "model_initializations": 0, "inference_calls": 0},
        }
    finally:
        page._backend.unload()
        in_doc._backend.unload()


def preflight() -> dict:
    """Captured OCR must exactly reproduce retained full-page downstream output."""
    cells = [TextCell.model_validate(c) for c in read(TRACE / "live/trace/ocr-cells-before-merge-001.json")]
    before = [c.model_dump(mode="json") for c in cells]
    output = replay(cells)
    expected = read(TRACE / "live/result.json")
    page = expected["pages"][0]
    comparisons = {
        "caller_cells_unchanged": before == [c.model_dump(mode="json") for c in cells],
        "after_ocr_cells": output["after_ocr_cells"] == read(TRACE / "live/trace/ocr-cells-after-merge-001.json"),
        "parsed_cells": output["parsed_cells"] == page["parsed_page"]["textline_cells"],
        "postlayout": output["postlayout"] == page["predictions"]["layout"],
        "table_structure": output["table_structure"] == page["predictions"]["tablestructure"],
        "assembled": output["assembled"] == page["assembled"],
        "document": output["document"] == expected["document"],
        "markdown_bytes": output["markdown"].encode() == (TRACE / "live/document.md").read_bytes(),
    }
    assert all(comparisons.values()), comparisons
    return {"exact_equal": comparisons, "cost": output["cost"],
            "scope": "one retained raster page, no table inference; no output normalization"}


if __name__ == "__main__":
    print(json.dumps(preflight(), ensure_ascii=False))
