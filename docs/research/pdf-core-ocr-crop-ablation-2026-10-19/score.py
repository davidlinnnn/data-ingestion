"""Read-only, source-anchored scoring for the single frozen page; no output repair."""
import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REFERENCE_SHA256 = "415216bada09152e082db98411fabae978c6f1e234b88dfd7dc6945e44218a8f"
ANCHOR_WIDTH = 16
MIN_ANCHORS = 8


def normalize(text):
    # Scoring only: ignore typography/spacing; never substitute OCR characters.
    return "".join(c for c in text.casefold() if c.isalnum())


def reference():
    raw = (HERE / "reference.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REFERENCE_SHA256, "Frozen reference changed"
    return json.loads(raw)


def document_elements(document):
    assert document.get("schema_name") == "DoclingDocument"
    result = []
    seen = set()

    def visit(node):
        if "$ref" in node or "cref" in node:
            pointer = node.get("$ref", node.get("cref"))
            assert "$ref" not in node or "cref" not in node or node["$ref"] == node["cref"], "Conflicting reference aliases"
            assert pointer not in seen, "Repeated/cyclic document reference"
            seen.add(pointer)
            target = document
            for key in pointer.removeprefix("#/").split("/"):
                target = target[int(key)] if isinstance(target, list) else target[key]
            visit(target)
            return
        if "text" in node:
            result.append({"text": node["text"], "id": node.get("self_ref"),
                           "label": node.get("label"), "content_layer": node.get("content_layer"),
                           "prov": node.get("prov", [])})
        for child in node.get("children", []):
            visit(child)

    visit(document["body"])
    return result


def score_stage(elements, ref):
    items = ref["items"]
    source = {x["id"]: normalize(x["text"]) for x in items}
    # Only source-unique character anchors count as evidence for a paragraph.
    owners = {}
    for key, text in source.items():
        for j in range(max(0, len(text) - ANCHOR_WIDTH + 1)):
            owners.setdefault(text[j:j + ANCHOR_WIDTH], set()).add(key)
    anchors = {key: {gram for gram, keys in owners.items() if keys == {key}}
               for key in source}
    for key, text in source.items():
        if len(text) < ANCHOR_WIDTH and all(text not in other for k, other in source.items() if k != key):
            anchors[key] = {text}
    normalized = [normalize(x["text"]) for x in elements]
    joined = "".join(normalized)
    source_by_id = {x["id"]: x for x in items}
    element_hits = []
    mixed = []
    for idx, (raw, text) in enumerate(zip(elements, normalized)):
        hits = {key: sorted(gram for gram in grams if gram in text)
                for key, grams in anchors.items()}
        strong = [key for key, grams in hits.items()
                  if len(grams) >= MIN_ANCHORS or
                  (len(source[key]) < ANCHOR_WIDTH and text == source[key])]
        for key in strong:
            if not hits[key]:
                hits[key] = [source[key]]
        columns = {source_by_id[key]["column"] for key in strong
                   if source_by_id[key]["role"] in ("paragraph", "section_header")}
        record = {"index": idx, "text": raw["text"], "source_hits":
                  {key: {"unique_anchor_count": len(hits[key]), "example": hits[key][0]}
                   for key in strong}, "source_ids": strong}
        element_hits.append(record)
        if columns == {"left", "right"}:
            mixed.append(record)
    rows = []
    for item in items:
        key = item["id"]
        selected = [i for i, hit in enumerate(element_hits) if key in hit["source_ids"]]
        observed = "".join(normalized[i] for i in selected)
        matcher = SequenceMatcher(None, source[key], observed, autojunk=False)
        matched = sum(block.size for block in matcher.get_matching_blocks())
        available = anchors[key]
        present = [g for g in available if g in joined]
        repeated = [g for g in available if joined.count(g) >= 2]
        positions = sorted(joined.find(g) for g in present)
        edits = [{"operation": tag, "reference": source[key][i:j],
                  "observed": observed[a:b]}
                 for tag, i, j, a, b in matcher.get_opcodes() if tag != "equal"]
        rows.append({"id": key, "role": item["role"], "column": item["column"],
                     "reference_characters": len(source[key]), "matched_characters": matched,
                     "character_coverage": round(matched / max(1, len(source[key])), 6),
                     "unique_anchor_coverage": round(len(present) / max(1, len(available)), 6),
                     "repeated_anchor_fraction": round(len(repeated) / max(1, len(available)), 6),
                     "median_anchor_position": positions[len(positions)//2] if positions else None,
                     "element_indexes": selected, "text_differences": edits})
    row_by_id = {x["id"]: x for x in rows}
    body = [row_by_id[key] for key in ref["body_order"]]
    omissions = [x["id"] for x in body if x["character_coverage"] < 0.2]
    duplicates = [x["id"] for x in body if x["repeated_anchor_fraction"] >= 0.6]
    inversions = []
    for i, left in enumerate(body):
        for right in body[i + 1:]:
            if min(left["character_coverage"], right["character_coverage"]) < 0.6:
                continue
            a, b = left["median_anchor_position"], right["median_anchor_position"]
            if a is not None and b is not None and a > b:
                inversions.append([left["id"], right["id"]])
    return {"elements": element_hits, "paragraphs_and_furniture": rows,
            "cross_column_mixed_elements": mixed,
            "whole_paragraph_omissions_candidates": omissions,
            "whole_paragraph_duplicates_candidates": duplicates,
            "body_order_inversions_candidates": inversions,
            "review_required": True,
            "notes": ["Cells retain caller order; document follows body references without sorting.",
                      "Anchor thresholds are diagnostic flags, not automatic semantic acceptance.",
                      "Missing/duplicate/order candidates and character diffs require source-page review.",
                      "No geometry-only midpoint rule and no OCR text substitution are used."]}


def score(cells, document):
    assert isinstance(cells, list) and all(isinstance(x.get("text"), str) for x in cells)
    ref = reference()
    return {"reference_sha256": REFERENCE_SHA256,
            "scoring_normalization": "Unicode casefold, alphanumeric characters only; scoring copies only",
            "raw_cells": score_stage(cells, ref),
            "document": score_stage(document_elements(document), ref)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cells", type=Path, required=True)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    doc = json.loads(args.document.read_text())
    result = score(json.loads(args.cells.read_text()), doc.get("document", doc))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        assert not args.output.exists(), "Do not overwrite existing evaluation"
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
