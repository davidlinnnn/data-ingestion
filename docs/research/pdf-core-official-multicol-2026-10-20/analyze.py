"""Read-only diagnostics in native body order; manual source review decides acceptance."""
import importlib.util
import json
from pathlib import Path
import sys

from run import BASE, HERE, PROFILES, read, sha, verify, write


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluator = load("frozen_evaluator", BASE / "evaluate.py")
legacy = evaluator.legacy
ROOT = HERE.parent
CONTROLS = {"H-default": BASE / "R0", "H-full": ROOT / "pdf-core-ocr-official-options-2026-10-19/full"}


def order_diagnostic(document, ref):
    # Traverse body references: the texts array is storage, not reading order.
    elements = legacy.document_elements(document)
    selected = {u["id"] for u in ref["items"] if u.get("scored", True)}
    scored = {**ref, "items": [{**u, "role": "section_header" if u["role"] == "heading" else u["role"]}
        for u in ref["items"] if u["id"] in selected], "body_order": [u for u in ref["body_order"] if u in selected]}
    score = legacy.score_stage(elements, scored)
    rows = {u["id"]: u for u in score["paragraphs_and_furniture"]}
    identified = [u for u in scored["body_order"] if rows[u]["median_anchor_position"] is not None]
    observed = sorted(identified, key=lambda u: rows[u]["median_anchor_position"])
    joined = "".join(legacy.normalize(e["text"]) for e in elements)
    reference_stream = "".join(legacy.normalize(u["text"]) for u in scored["items"])
    repeated = []
    for line in ref.get("source_lines", []):
        text = legacy.normalize(line["text"])
        anchor = text[:16]
        if line.get("scored", True) and len(anchor) == 16 and reference_stream.count(anchor) == 1 and joined.count(anchor) > 1:
            repeated.append({"source_line_id": line["id"], "source_text": line["text"],
                             "anchor": anchor, "observed_count": joined.count(anchor)})
    return {"expected": scored["body_order"], "observed_anchor_order": observed,
        "unlocated_units": [u for u in scored["body_order"] if u not in identified],
        "inversion_candidates": score["body_order_inversions_candidates"],
        "partial_line_repeat_candidates": repeated,
        "note": "Source-unique anchors, first-line repeats and inversions are review triggers; no output changes or semantic pass."}


def selfcheck():
    ref = read(BASE / "known-reference.json")
    c10 = read(ROOT / "pdf-core-ocr-region-policy-2026-10-20/C10/known/document.json")
    full = read(CONTROLS["H-full"] / "known/document.json")
    positive, negative = order_diagnostic(c10, ref), order_diagnostic(full, ref)
    assert positive["observed_anchor_order"] == ref["body_order"] and not positive["inversion_candidates"]
    assert len(negative["inversion_candidates"]) == 5 and not negative["unlocated_units"]
    repeat_doc = {"schema_name": "DoclingDocument", "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/texts/1"}]},
                  "texts": [{"self_ref": "#/texts/0", "text": "A sufficiently unique source line."},
                            {"self_ref": "#/texts/1", "text": "A sufficiently unique source line."}]}
    repeat_ref = {"items": [{"id": "U1", "role": "paragraph", "column": "single", "text": "A sufficiently unique source line."}],
                  "body_order": ["U1"], "source_lines": [{"id": "L1", "text": "A sufficiently unique source line."}]}
    assert order_diagnostic(repeat_doc, repeat_ref)["partial_line_repeat_candidates"][0]["observed_count"] == 2
    assert not order_diagnostic({**repeat_doc, "body": {"children": [{"$ref": "#/texts/0"}]}}, repeat_ref)["partial_line_repeat_candidates"]
    frozen = read(HERE / "validation/freeze.json")
    assert all(sha(HERE / "validation" / p) == digest for p, digest in frozen["files"].items())
    validation = read(HERE / "validation/reference.json")
    assert len(validation["pages"]) == 6 and len({p["source_id"] for p in validation["pages"]}) == 3
    for ref in validation["pages"]:
        evaluator.validate_reference(ref)
    return {"C10_correct_12_unit_order": True, "FULL_PAGE_five_inversions_detected": True,
        "partial_repeat_positive_and_negative_controls": True, "six_source_references_valid_and_unchanged": True,
        "new_inference_calls": 0}


def analyze():
    registration = verify()
    refs = {p["id"]: p for p in read(BASE / "corpus/reference.json")["pages"]}
    refs["known"] = read(BASE / "known-reference.json")
    result = {}
    for profile, folder in {**CONTROLS, **{p: HERE / p for p in PROFILES}}.items():
        if not (folder / "execution.json").exists():
            continue
        rows = []
        for job in registration["jobs"]:
            page = folder / job["id"]
            if not (page / "execution.json").exists():
                continue
            execution = read(page / "execution.json")
            row = {"id": job["id"], "status": execution["status"], "seconds": execution["seconds"]}
            if execution["status"] == "success":
                cells, doc, ref = read(page / "cells.json"), read(page / "document.json"), refs[job["id"]]
                score = evaluator.evaluate(cells, doc, ref)
                order = order_diagnostic(doc, ref)
                row.update(raw_mix_flags=len(score["raw_cells"]["cross_column_mixed_elements"]),
                    doc_mix_flags=len(score["document"]["cross_column_mixed_elements"]),
                    omission_flags=score["document"]["whole_unit_omission_candidates"],
                    critical_difference_flags=score["document"]["critical_text_difference_candidates"],
                    order=order, cells_sha256=sha(page / "cells.json"), document_sha256=sha(page / "document.json"))
                if profile in PROFILES:
                    write(page / "score.json", score)
                    write(page / "order.json", order)
                if profile == "E-full":
                    row["FULL_PAGE_OCR_control_equal"] = cells == read(CONTROLS["H-full"] / job["id"] / "cells.json")
            rows.append(row)
        execution = read(folder / "execution.json")
        result[profile] = {"execution_status": execution["status"], "pages": rows,
            "page_seconds_total": sum(p["seconds"] for p in rows),
            "initialization_seconds": read(folder / "initialization.json")["seconds"] if (folder / "initialization.json").exists() else None,
            "peak_sampled_tree_rss_bytes": execution["peak_sampled_tree_rss_bytes"], "qualification": "REVIEW_REQUIRED"}
    write(HERE / "diagnostics.json", result)
    print(json.dumps({p: {"status": r["execution_status"], "seconds": r["page_seconds_total"],
        "known_order": r["pages"][0].get("order", {})} for p, r in result.items()}, indent=2))


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        value = selfcheck()
        write(HERE / "evaluator-selfcheck.json", value)
        print(json.dumps(value))
    elif not sys.argv[1:]:
        analyze()
    else:
        raise SystemExit("use --selfcheck or no arguments")
