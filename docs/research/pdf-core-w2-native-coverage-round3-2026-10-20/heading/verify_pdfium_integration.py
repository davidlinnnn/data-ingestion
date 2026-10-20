"""Integrate bookmark-only heading with S0's exact PDFium outline extractor."""
import collections
import inspect
import json
import time
from pathlib import Path

import pypdfium2 as pdfium
from docling_core.types.doc import DoclingDocument
from docling_core.types.doc.document import SectionHeaderItem
from docling.datamodel.pipeline_options import HeadingHierarchyOptions
from docling.models.stages.heading_hierarchy.heading_hierarchy_model import HeadingHierarchyModel
from docling.utils.pdf_outline import extract_outline_from_pdfium
from run_ablation import ROOT, OUT, OLD, HELPERS, EVALUATOR, clear_images, write, changed

TARGET = OUT / "pdfium-integration"

def main():
    TARGET.mkdir(exist_ok=True)
    mapping = json.loads((ROOT / "baseline-inputs.json").read_text())
    index = json.loads((OLD / "oracle/job-index.json").read_text())
    options = HeadingHierarchyOptions(enabled=True, use_bookmarks=True, use_numbering=False, use_style=False)
    jobs = json.loads((OLD / "jobs.json").read_text())["jobs"]
    rows = []
    counts = collections.Counter()
    fixed = new_bad = 0
    for job in jobs:
        HELPERS.guard()
        folder = TARGET / job["id"]
        folder.mkdir(exist_ok=False)
        source_path = Path(mapping[job["id"]]) / "document.json"
        source = json.loads(source_path.read_text())
        removed = clear_images(source)
        baseline = DoclingDocument.model_validate(source)
        baseline_dump = baseline.model_dump(mode="json")
        expected_baseline = json.loads((OUT / "jobs" / job["id"] / "baseline-imagefree.json").read_text())
        assert baseline_dump == expected_baseline
        assert HELPERS.sha(Path(job["pdf"])) == job["pdf_sha256"]
        pdoc = pdfium.PdfDocument(job["pdf"])
        try:
            outline = extract_outline_from_pdfium(pdoc)
        finally:
            pdoc.close()
        write(folder / "outline-pdfium.json", [x.model_dump(mode="json") for x in outline])
        started = time.monotonic()
        result = HeadingHierarchyModel(options).assign_heading_levels(
            baseline.model_copy(deep=True), parsed_pages=None, outline=outline)
        seconds = time.monotonic() - started
        after = result.model_dump(mode="json")
        write(folder / "document.json", after)
        (folder / "document.md").write_text(result.export_to_markdown())
        old_path = OUT / "jobs" / job["id"] / "b1-n0-s0" / "document.json"
        previous = json.loads(old_path.read_text())
        delta = HELPERS.differences(previous, after)
        write(folder / "versus-doclingparse-outline-diff.json", delta)
        level_old = {v["self_ref"]: {"text": v["text"], "level": v["level"]} for v in previous["texts"] if v["label"] == "section_header"}
        level_new = {v["self_ref"]: {"text": v["text"], "level": v["level"]} for v in after["texts"] if v["label"] == "section_header"}
        stage_diff = HELPERS.differences(baseline_dump, after)
        allowed = {f"/texts/{i}/level" for i, v in enumerate(baseline.texts) if isinstance(v, SectionHeaderItem)}
        write(folder / "versus-baseline-diff.json", stage_diff)
        oracle = json.loads(Path(index[job["id"]]).read_text())
        scoped = [h for h in oracle["headings"] if h.get("scope") == "IN_SCOPE"]
        assessment = EVALUATOR.assess(after, scoped)
        baseline_assessment = EVALUATOR.assess(baseline_dump, scoped)
        comparison = changed(baseline_assessment["headings"], assessment["headings"])
        write(folder / "assessment.json", assessment)
        structural = collections.Counter(v["status"] for v in assessment["headings"] if v["reference"]["command"] not in ("paragraph", "subparagraph"))
        counts.update(structural)
        fixed += comparison["fixed"]
        new_bad += comparison["new_bad"]
        row = {"id": job["id"], "family": oracle.get("template", {}).get("family") or job["family"],
            "heading_levels_identical_to_doclingparse_outline": level_old == level_new,
            "entire_document_identical_to_doclingparse_outline": not delta,
            "markdown_identical_to_doclingparse_outline": (folder / "document.md").read_bytes() == old_path.with_name("document.md").read_bytes(),
            "outline_pdfium_count": len(outline), "parsed_pages": None,
            "stage_seconds": seconds, "stage_level_only": all(v["path"] in allowed for v in stage_diff),
            "actual_parents_unchanged": [v.parent for v in baseline.texts] == [v.parent for v in result.texts],
            "text_orig_provenance_unchanged": [(v.text, v.orig, v.prov) for v in baseline.texts] == [(v.text, v.orig, v.prov) for v in result.texts],
            "image_fields_cleared": len(removed), "structural_counts": dict(structural),
            "versus_baseline": comparison, "outline_document_sha256": job["pdf_sha256"]}
        write(folder / "summary.json", row)
        rows.append(row)
    summary = {"documents": len(rows), "official_options": options.model_dump(mode="json"),
        "extractor": "docling.utils.pdf_outline.extract_outline_from_pdfium",
        "extractor_source_file": inspect.getfile(extract_outline_from_pdfium),
        "extractor_source_sha256": HELPERS.sha(Path(inspect.getfile(extract_outline_from_pdfium))),
        "scope": "Exact extractor called by S0 PyPdfiumDocumentBackend.get_document_outline; fresh original baseline deepcopy, image fields cleared before Core load, parsed_pages=None. No conversion, native font parse, or model inference.",
        "all_levels_identical_to_doclingparse_outline": all(v["heading_levels_identical_to_doclingparse_outline"] for v in rows),
        "all_documents_identical_to_doclingparse_outline": all(v["entire_document_identical_to_doclingparse_outline"] for v in rows),
        "all_markdown_identical_to_doclingparse_outline": all(v["markdown_identical_to_doclingparse_outline"] for v in rows),
        "versus_baseline": {"fixed": fixed, "new_bad": new_bad},
        "structural_counts": dict(counts), "jobs": rows}
    write(TARGET / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k.startswith("all_") or k in ("documents", "versus_baseline", "structural_counts")}))

if __name__ == "__main__":
    main()

