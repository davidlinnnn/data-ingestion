"""Compare V2 raw headings and official PDFium bookmark-only composition."""
import collections
import json
from pathlib import Path
import pypdfium2 as pdfium
from docling_core.types.doc import DoclingDocument
from docling_core.types.doc.document import SectionHeaderItem
from docling.datamodel.pipeline_options import HeadingHierarchyOptions
from docling.models.stages.heading_hierarchy.heading_hierarchy_model import HeadingHierarchyModel
from docling.utils.pdf_outline import extract_outline_from_pdfium
from run_ablation import ROOT, OUT, OLD, HELPERS, EVALUATOR, clear_images, write, changed

TARGET = OUT / "V2-bookmarks"

def main():
    TARGET.mkdir(exist_ok=True)
    jobs = json.loads((OLD / "jobs.json").read_text())["jobs"]
    index = json.loads((OLD / "oracle/job-index.json").read_text())
    options = HeadingHierarchyOptions(enabled=True, use_bookmarks=True, use_numbering=False, use_style=False)
    rows = []
    for job in jobs:
        HELPERS.guard()
        output = TARGET / job["id"]
        output.mkdir(exist_ok=False)
        v2path = ROOT / "runs/V2-official/jobs" / job["id"] / "document.json"
        raw = json.loads(v2path.read_text())
        cleared = clear_images(raw)
        doc = DoclingDocument.model_validate(raw)
        before = doc.model_dump(mode="json")
        write(output / "V2-core-load-normalization-diff.json", HELPERS.differences(raw, before))
        write(output / "V2-image-removal.json", cleared)
        heron = json.loads((OUT / "jobs" / job["id"] / "baseline-imagefree.json").read_text())
        pdf = pdfium.PdfDocument(job["pdf"])
        try:
            outline = extract_outline_from_pdfium(pdf)
        finally:
            pdf.close()
        write(output / "outline-pdfium.json", [x.model_dump(mode="json") for x in outline])
        after_doc = HeadingHierarchyModel(options).assign_heading_levels(doc.model_copy(deep=True), parsed_pages=None, outline=outline)
        after = after_doc.model_dump(mode="json")
        write(output / "document.json", after)
        (output / "document.md").write_text(after_doc.export_to_markdown())
        assert doc.model_dump(mode="json") == before
        diff = HELPERS.differences(before, after)
        write(output / "diff.json", diff)
        oracle = json.loads(Path(index[job["id"]]).read_text())
        refs = [h for h in oracle["headings"] if h.get("scope") == "IN_SCOPE"]
        assessments = {"Heron_raw": EVALUATOR.assess(heron, refs),
                       "V2_raw": EVALUATOR.assess(before, refs),
                       "V2_bookmarks": EVALUATOR.assess(after, refs)}
        write(output / "assessment.json", assessments["V2_bookmarks"])
        write(output / "assessment-raw.json", assessments["V2_raw"])
        write(output / "assessment-heron.json", assessments["Heron_raw"])
        allowed = {f"/texts/{i}/level" for i, v in enumerate(doc.texts) if isinstance(v, SectionHeaderItem)}
        comparisons = {
            "V2_raw_vs_Heron_raw": changed(assessments["Heron_raw"]["headings"], assessments["V2_raw"]["headings"]),
            "V2_bookmarks_vs_Heron_raw": changed(assessments["Heron_raw"]["headings"], assessments["V2_bookmarks"]["headings"]),
            "V2_bookmarks_vs_V2_raw": changed(assessments["V2_raw"]["headings"], assessments["V2_bookmarks"]["headings"])}
        structural = {name: dict(collections.Counter(v["status"] for v in assessment["headings"] if v["reference"]["command"] not in ("paragraph", "subparagraph")))
                      for name, assessment in assessments.items()}
        row = {"id": job["id"], "family": oracle.get("template", {}).get("family") or job["family"],
            "in_scope": len(refs), "structural_counts": structural, "comparisons": comparisons,
            "stage_level_only": all(v["path"] in allowed for v in diff),
            "stage_nonlevel_changes": [v for v in diff if v["path"] not in allowed],
            "text_orig_provenance_unchanged_vs_V2_core": [(v.text, v.orig, v.prov) for v in doc.texts] == [(v.text, v.orig, v.prov) for v in after_doc.texts],
            "actual_parents_unchanged": [v.parent for v in doc.texts] == [v.parent for v in after_doc.texts],
            "V2_document_sha256": HELPERS.sha(v2path), "options": options.model_dump(mode="json")}
        write(output / "summary.json", row)
        rows.append(row)
        print(job["id"] + " V2 raw+B-only complete", flush=True)
    def total(members):
        return {"documents": len(members),
            "structural_counts": {mode: dict(sum((collections.Counter(v["structural_counts"][mode]) for v in members), collections.Counter())) for mode in ("Heron_raw", "V2_raw", "V2_bookmarks")},
            "comparisons": {name: {"fixed": sum(v["comparisons"][name]["fixed"] for v in members),
                                  "new_bad": sum(v["comparisons"][name]["new_bad"] for v in members),
                                  "transitions": dict(sum((collections.Counter(v["comparisons"][name]["transitions"]) for v in members), collections.Counter()))}
                            for name in ("V2_raw_vs_Heron_raw", "V2_bookmarks_vs_Heron_raw", "V2_bookmarks_vs_V2_raw")}}
    families = collections.defaultdict(list)
    for row in rows:
        families[row["family"]].append(row)
    summary = {"scope": "Egret V2 raw and V2 plus official bookmark-only via exact S0 PDFium outline; parsed_pages=None. Same frozen oracle/evaluator. No conversion or model inference.",
        "total": total(rows), "by_family": {k: total(v) for k, v in families.items()},
        "all_stage_level_only": all(v["stage_level_only"] for v in rows),
        "all_stage_text_orig_provenance_preserved_vs_V2_core": all(v["text_orig_provenance_unchanged_vs_V2_core"] for v in rows),
        "all_stage_actual_parents_unchanged": all(v["actual_parents_unchanged"] for v in rows),
        "jobs": rows}
    write(TARGET / "summary.json", summary)
    print(json.dumps(summary["total"]))

if __name__ == "__main__":
    main()

