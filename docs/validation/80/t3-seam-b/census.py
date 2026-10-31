"""Census of the fixed corpus for #132 Seam B: pictures, tables and code blocks per paper.

    env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t3-seam-b/census.py CORPUS_MANIFEST

One docling conversion per paper with the paper-pdf parse options; writes counts only to
census.json next to this script.
"""

import json
import sys
from pathlib import Path

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

from kp_processing.methods.docling_parse.pipeline import options

manifest = Path(sys.argv[1])
converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_cls=StandardPdfPipeline,
            pipeline_options=options(),
            backend=PyPdfiumDocumentBackend,
        )
    }
)
rows = []
for paper in json.loads(manifest.read_text())["papers"]:
    result = converter.convert(manifest.parent / paper["file"])
    document = result.document
    rows.append(
        {
            "index": paper["index"],
            "sha256": paper["sha256"],
            "pages": result.input.page_count,
            "pictures": len(document.pictures),
            "tables": len(document.tables),
            "code": sum(text.label == "code" for text in document.texts),
        }
    )
    print(rows[-1], flush=True)
(Path(__file__).parent / "census.json").write_text(json.dumps(rows, indent=1) + "\n")
