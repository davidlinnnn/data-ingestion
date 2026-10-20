"""Source-anchored OCR diagnostics; flags require page review, never automatic qualification."""
import argparse
from difflib import SequenceMatcher
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEGACY = HERE.parent / "pdf-core-ocr-crop-ablation-2026-10-19/score.py"
spec = importlib.util.spec_from_file_location("frozen_crop_score", LEGACY)
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
normalize = legacy.normalize


def validate_reference(ref):
    assert isinstance(ref, dict) and isinstance(ref.get("items"), list) and ref["items"], "Empty reference"
    ids = [item["id"] for item in ref["items"]]
    assert len(set(ids)) == len(ids), "Duplicate source IDs"
    for item in ref["items"]:
        assert isinstance(item["text"], str) and (normalize(item["text"]) or not item.get("scored", True)), "Empty source text"
        assert isinstance(item["role"], str) and isinstance(item["column"], str)
        assert len(item["bbox"]) == 4 and item["bbox"][0] < item["bbox"][2] and item["bbox"][1] < item["bbox"][3]
    order = ref["body_order"]
    assert order and len(set(order)) == len(order) and set(order) <= set(ids), "Invalid body denominator"
    assert set(ref.get("legitimate_cross_column_items", [])) <= set(ids)
    for line in ref.get("source_lines", []):
        assert isinstance(line["text"], str) and (normalize(line["text"]) or not line.get("scored", True)), "Empty source line"
    return ref


def document_elements(document):
    assert document.get("schema_name") == "DoclingDocument", "Expected native DoclingDocument"
    texts = document.get("texts")
    assert isinstance(texts, list) and texts, "Empty document text array"
    assert all(isinstance(item.get("text"), str) for item in texts), "Invalid document text"
    assert any(normalize(item["text"]) for item in texts), "No document text"
    return [{"id": item.get("self_ref"), "text": item["text"],
             "label": item.get("label"), "content_layer": item.get("content_layer"),
             "prov": item.get("prov", [])} for item in texts]


def coverage(text, observed):
    target = normalize(text)
    blocks = SequenceMatcher(None, target, observed, autojunk=False).get_matching_blocks()
    # Unrelated words can supply every character of a missing short heading.
    matched = sum(block.size for block in blocks) if max(block.size for block in blocks) >= min(8, len(target)) else 0
    return {"reference_characters": len(target), "matched_characters": matched,
            "character_coverage": round(matched / len(target), 6), "exact_normalized_text_present": target in observed}


def score_stage(elements, ref):
    assert isinstance(elements, list) and all(isinstance(item.get("text"), str) for item in elements)
    joined = "".join(normalize(item["text"]) for item in elements)
    diagnostic = legacy.score_stage(elements, {**ref, "items": [
        {**item, "role": "section_header" if item["role"] == "heading" else item["role"]}
        for item in ref["items"]]})
    rows = [{**row, **coverage(item["text"], joined), "critical": bool(item.get("critical", False))}
            for row, item in zip(diagnostic["paragraphs_and_furniture"], ref["items"])]
    lines = [{"id": line.get("id", f"line-{i}"), "text": line["text"], **coverage(line["text"], joined)}
             for i, line in enumerate(ref.get("source_lines", []))]
    return {
        "source_units": rows,
        "source_lines": lines,
        "cross_column_mixed_elements": diagnostic["cross_column_mixed_elements"],
        "whole_unit_omission_candidates": [row["id"] for row in rows
                                            if row["id"] in ref["body_order"] and row["character_coverage"] < .2],
        "critical_text_difference_candidates": [row["id"] for row in rows
                                                 if row["critical"] and not row["exact_normalized_text_present"]],
        "incomplete_source_unit_candidates": [row["id"] for row in rows if row["character_coverage"] < .8],
        "incomplete_source_line_candidates": [row["id"] for row in lines if row["character_coverage"] < .8],
        "whole_unit_duplicate_candidates": diagnostic["whole_paragraph_duplicates_candidates"],
        "review_required": True,
    }


def evaluate(cells, document, page_reference):
    original = validate_reference(page_reference)
    included = [item for item in original["items"] if item.get("scored", True)]
    included_ids = {item["id"] for item in included}
    ref = {**original, "items": included,
           "body_order": [key for key in original["body_order"] if key in included_ids],
           "legitimate_cross_column_items": [key for key in original.get("legitimate_cross_column_items", []) if key in included_ids],
           "source_lines": [line for line in original.get("source_lines", []) if line.get("scored", True)]}
    validate_reference(ref)
    assert isinstance(cells, list) and cells and any(normalize(item.get("text", "")) for item in cells), "Empty OCR cells"
    result = {
        "page_id": ref.get("id"), "qualification": "REVIEW_REQUIRED",
        "normalization": "Scoring copies only: Unicode casefold and alphanumeric characters; no OCR substitutions",
        "raw_cells": score_stage(cells, ref),
        "document": score_stage(document_elements(document), ref),
        "scope": {"body_order": ref["body_order"], "excluded_figure_regions": ref.get("excluded_figure_regions", []),
                  "unscored_source_units": [item for item in original["items"] if not item.get("scored", True)]},
        "notes": [
            "Raw RapidOCR line cells and Tesseract word cells differ in granularity; raw mixed-element counts are not an engine ranking.",
            "Cross-column flags require unique source-text evidence from both left and right paragraphs; spanning source headings are legal.",
            "Coverage searches the whole output stream, so word/line fragmentation alone does not create omissions.",
            "Character coverage requires an 8-character contiguous seed (or the whole shorter source); unrelated scattered characters are not evidence.",
            "20% omission and 80% incompleteness are review triggers, not acceptance thresholds; manual source-page adjudication is required.",
            "Text storage order is not reading order; this scoped OCR comparison does not qualify downstream ordering or other components.",
        ],
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cells", type=Path, required=True)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    refs = json.loads(args.reference.read_text())
    selected = [page for page in refs["pages"] if page["id"] == args.page_id]
    assert len(selected) == 1, "Page ID must identify exactly one reference"
    document = json.loads(args.document.read_text())
    result = evaluate(json.loads(args.cells.read_text()), document.get("document", document), selected[0])
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
