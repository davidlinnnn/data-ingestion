"""Exact packaged Docling heading-stage replay; never invokes a conversion pipeline."""

import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
from pathlib import Path

from docling_core.types.doc import DoclingDocument
from docling_core.types.doc.document import SectionHeaderItem, TitleItem
from docling_core.types.doc.page import PdfTextCell, SegmentedPdfPage

from docling.backend.docling_parse_backend import ThreadedDoclingParseDocumentBackend
from docling.datamodel.backend_options import ThreadedDoclingParseBackendOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import InputDocument
from docling.datamodel.pipeline_options import HeadingHierarchyOptions
from docling.datamodel.settings import DocumentLimits
from docling.models.stages.heading_hierarchy.heading_hierarchy_model import (
    HeadingHierarchyModel,
)
from docling.utils.pdf_outline import _PdfOutlineItem


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def differences(before, after, path=""):
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        result = []
        for key in sorted(before.keys() | after.keys()):
            if key not in before or key not in after:
                result.append({"path": f"{path}/{key}", "before": before.get(key), "after": after.get(key)})
            else:
                result.extend(differences(before[key], after[key], f"{path}/{key}"))
        return result
    if isinstance(before, list):
        if len(before) != len(after):
            return [{"path": path, "before": before, "after": after}]
        return [change for i, (a, b) in enumerate(zip(before, after)) for change in differences(a, b, f"{path}/{i}")]
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def heading_tree(document):
    rows, stack = [], []
    title = None
    for item, _ in document.iterate_items():
        if isinstance(item, TitleItem):
            title, stack = item.self_ref, []
            level, inferred_parent = 0, "#/body"
        elif isinstance(item, SectionHeaderItem):
            level = item.level
            while stack and stack[-1][0] >= level:
                stack.pop()
            inferred_parent = stack[-1][1] if stack else title or "#/body"
            stack.append((level, item.self_ref))
        else:
            continue
        rows.append({"self_ref": item.self_ref, "label": item.label, "text": item.text,
                     "level": level, "inferred_parent": inferred_parent,
                     "actual_parent": item.parent.model_dump(mode="json") if item.parent else None,
                     "prov": [p.model_dump(mode="json") for p in item.prov]})
    return {"convention": "Reading-order headings use nearest preceding lower level; each TitleItem is a level-0 display root and resets the stack. These inferred edges do not change Docling parent fields.", "headings": rows}


def capture(args, output):
    source = json.loads(Path(args.document).read_text())
    document = DoclingDocument.model_validate(source)
    before = document.model_dump(mode="json")
    write(output / "source-to-runtime-normalization-diff.json", differences(source, before))
    write(output / "document-before.json", before)
    (output / "document-before.md").write_text(document.export_to_markdown())
    write(output / "headings-before.json", heading_tree(document))
    backend_options = ThreadedDoclingParseBackendOptions(parser_threads=1, render_pages=False)
    in_doc = InputDocument(path_or_stream=Path(args.pdf), format=InputFormat.PDF,
                           backend=ThreadedDoclingParseDocumentBackend,
                           backend_options=backend_options,
                           limits=DocumentLimits(page_range=(1, args.pages)))
    assert in_doc.valid, "PDF backend rejected source"
    backend = in_doc._backend
    parsed_pages = {}
    try:
        outline = backend.get_document_outline()
        write(output / "outline.json", [item.model_dump(mode="json") for item in outline])
        for page in backend.iter_pages():
            assert page.is_valid(), page.get_error_message()
            parsed = page.get_segmented_page()
            assert parsed is not None
            physical = page.page_no
            parsed_pages[physical] = parsed
            write(output / f"parsed-page-{physical:04d}.json", parsed.model_dump(mode="json"))
        assert sorted(parsed_pages) == list(range(1, args.pages + 1)), sorted(parsed_pages)
    finally:
        backend.unload()
    manifest = {
        "method": "Old assembled whole DoclingDocument + fresh exact packaged native PDF backend inputs; assembly replay only, not a v2.132 conversion pipeline.",
        "pdf": str(Path(args.pdf).resolve()), "pdf_sha256": sha(Path(args.pdf)),
        "old_document": str(Path(args.document).resolve()), "old_document_sha256": sha(Path(args.document)),
        "physical_pages": sorted(parsed_pages), "outline_count": len(outline),
        "backend": "docling.backend.docling_parse_backend.ThreadedDoclingParseDocumentBackend",
        "backend_options": backend_options.model_dump(mode="json"),
        "options": HeadingHierarchyOptions(enabled=True).model_dump(mode="json"),
        "packages": {name: importlib.metadata.version(name) for name in ("docling-slim", "docling-core", "docling-parse", "pypdfium2", "pydantic")},
        "textline_cells": {n: {"total": len(p.textline_cells), "pdf_font_cells": sum(isinstance(c, PdfTextCell) for c in p.textline_cells)} for n, p in parsed_pages.items()},
        "input_hashes": {p.name: sha(p) for p in sorted(output.glob("parsed-page-*.json"))},
        "outline_sha256": sha(output / "outline.json"),
    }
    write(output / "input-manifest.json", manifest)
    return document, parsed_pages, outline


def stage(document, pages, outline, output, name):
    before = document.model_dump(mode="json")
    assert document.validate_tree(document.body, raise_on_error=True)
    start = time.monotonic()
    result = HeadingHierarchyModel(options=HeadingHierarchyOptions(enabled=True)).assign_heading_levels(document.model_copy(deep=True), parsed_pages=pages, outline=outline)
    elapsed = time.monotonic() - start
    after = result.model_dump(mode="json")
    assert result.validate_tree(result.body, raise_on_error=True)
    assert result.validate_tree(result.furniture, raise_on_error=True)
    # A second parse validates every reference and the full output data model.
    assert DoclingDocument.model_validate(after).model_dump(mode="json") == after
    write(output / f"document-{name}.json", after)
    (output / f"document-{name}.md").write_text(result.export_to_markdown())
    write(output / f"headings-{name}.json", heading_tree(result))
    diff = differences(before, after)
    write(output / f"diff-{name}.json", diff)
    locator_fields = ("prov", "orig", "text")
    preserved = len(document.texts) == len(result.texts) and all(
        all(getattr(a, field, None) == getattr(b, field, None) for field in locator_fields)
        for a, b in zip(document.texts, result.texts)
    )
    summary = {"name": name, "seconds": elapsed, "changes": len(diff),
               "level_only": all(c["path"].startswith("/texts/") and c["path"].endswith("/level") for c in diff),
               "text_orig_provenance_preserved_by_index": preserved,
               "actual_parent_fields_unchanged": [item.parent for item in document.texts] == [item.parent for item in result.texts],
               "graph_valid": True, "heading_count": len([i for i in result.texts if isinstance(i, SectionHeaderItem)]),
               "model_modules_loaded": [m for m in ("torch", "transformers", "docling_ibm_models") if m in sys.modules]}
    write(output / f"summary-{name}.json", summary)
    return after


def main():
    assert differences({"a": 1}, {"a": 1, "b": 2}) == [{"path": "/b", "before": None, "after": 2}]
    assert differences([1, 2], [2, 1])[0]["path"] == "/0"
    assert differences([1], [1, 2]) == [{"path": "", "before": [1], "after": [1, 2]}]
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("capture-fresh", "reload"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--pdf")
    parser.add_argument("--document")
    parser.add_argument("--pages", type=int)
    parser.add_argument("--no-outline-ablation", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if args.mode == "capture-fresh":
        document, pages, outline = capture(args, output)
        stage(document, pages, outline, output, "fresh")
        if args.no_outline_ablation:
            stage(document, pages, [], output, "no-outline")
    else:
        document = DoclingDocument.model_validate_json((output / "document-before.json").read_text())
        pages = {int(p.stem.rsplit("-", 1)[1]): SegmentedPdfPage.model_validate_json(p.read_text()) for p in output.glob("parsed-page-*.json")}
        outline = [_PdfOutlineItem.model_validate(item) for item in json.loads((output / "outline.json").read_text())]
        manifest = json.loads((output / "input-manifest.json").read_text())
        assert {str(n): sum(isinstance(c, PdfTextCell) for c in p.textline_cells) for n, p in pages.items()} == {n: value["pdf_font_cells"] for n, value in manifest["textline_cells"].items()}
        after = stage(document, pages, outline, output, "reloaded")
        fresh = json.loads((output / "document-fresh.json").read_text())
        assert after == fresh, "Persisted stage-input reload changed output"
        assert (output / "document-fresh.md").read_bytes() == (output / "document-reloaded.md").read_bytes()
        write(output / "reload-equivalence.json", {"document_json_equal": True, "markdown_equal": True,
              "scope": "Stage-input fresh/reloaded equivalence only; neither full-pipeline nor recovery qualification.",
              "pdf_font_cells_after_reload": {n: sum(isinstance(c, PdfTextCell) for c in p.textline_cells) for n, p in pages.items()}})


if __name__ == "__main__":
    main()
