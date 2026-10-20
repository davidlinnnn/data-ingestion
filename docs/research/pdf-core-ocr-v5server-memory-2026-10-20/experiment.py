"""Freeze and score one configuration using the retained source evaluator."""
import difflib
import importlib.util
from pathlib import Path
import sys

from run import BASE, HERE, PROFILES, effective, read, sha, verify, write

CONTROL = HERE.parent / "pdf-core-ocr-region-policy-2026-10-20/C10"
FULL = HERE.parent / "pdf-core-ocr-official-options-2026-10-19/full"
VALIDATION = HERE.parent / "pdf-core-official-multicol-2026-10-20/validation"
AUDIT_PATH = HERE.parent / "pdf-core-official-multicol-2026-10-20/analyze.py"
spec = importlib.util.spec_from_file_location("retained_order_audit", AUDIT_PATH)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def freeze():
    assert not (HERE / "registration.json").exists() and not (HERE / "V5").exists()
    control = read(BASE / "registration.json")
    candidate = effective("V5")
    prior = read(HERE.parent / "pdf-core-ocr-v5server-2026-10-20/registration.json")
    assert candidate == prior["profiles"]["V5"], "candidate changed during resource-only rerun"
    original = control["profiles"]["R0"]
    assert {k: v for k, v in candidate.items() if k != "ocr_options"} == {
        k: v for k, v in original.items() if k != "ocr_options"}
    changed = {k for k in candidate["ocr_options"] if candidate["ocr_options"][k] != original["ocr_options"][k]}
    assert changed == {"det_model_path", "rec_model_path", "rapidocr_params"}
    extras = {"Det.ocr_version": "PP-OCRv5", "Rec.ocr_version": "PP-OCRv5",
              "Det.model_type": "server", "Rec.model_type": "server"}
    assert candidate["ocr_options"]["rapidocr_params"] == {**original["ocr_options"]["rapidocr_params"], **extras}
    assert not candidate["enable_remote_services"] and not candidate["allow_external_plugins"]
    assert PROFILES == ("V5",)
    reference = read(BASE / "known-reference.json")
    positive = audit.order_diagnostic(read(CONTROL / "known/document.json"), reference)
    negative = audit.order_diagnostic(read(FULL / "known/document.json"), reference)
    assert positive["observed_anchor_order"] == reference["body_order"] and not positive["inversion_candidates"]
    assert len(negative["inversion_candidates"]) == 5 and not negative["unlocated_units"]
    assert Path(audit.evaluator.__file__).parent == BASE
    repeat_doc = {"schema_name": "DoclingDocument", "body": {"children": [{"$ref": "#/texts/0"}, {"$ref": "#/texts/1"}]},
        "texts": [{"self_ref": "#/texts/0", "text": "A sufficiently unique source line."},
                  {"self_ref": "#/texts/1", "text": "A sufficiently unique source line."}]}
    repeat_ref = {"items": [{"id": "U1", "role": "paragraph", "column": "single", "text": "A sufficiently unique source line."}],
        "body_order": ["U1"], "source_lines": [{"id": "L1", "text": "A sufficiently unique source line."}]}
    assert audit.order_diagnostic(repeat_doc, repeat_ref)["partial_line_repeat_candidates"][0]["observed_count"] == 2
    assert not audit.order_diagnostic({**repeat_doc, "body": {"children": [{"$ref": "#/texts/0"}]}}, repeat_ref)["partial_line_repeat_candidates"]
    hashes = dict(control["hashes"])
    for path, digest in hashes.items():
        assert sha(path) == digest, path
    receipt = read(HERE / "model-receipt.json")
    assert sha(receipt["registry"]) == receipt["registry_sha256"]
    for row in receipt["models"].values():
        assert sha(row["path"]) == row["sha256"] == row["expected_sha256"]
        hashes[row["path"]] = row["sha256"]
    paths = [Path(receipt["registry"]), AUDIT_PATH, Path(audit.evaluator.__file__), Path(audit.legacy.__file__)]
    for folder in (CONTROL, FULL, BASE / "R0"):
        paths += [p for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    frozen = read(VALIDATION / "freeze.json")
    for path, digest in frozen["files"].items():
        assert sha(VALIDATION / path) == digest
        paths.append(VALIDATION / path)
    paths.append(VALIDATION / "freeze.json")
    original_runner = HERE.parent / "pdf-core-order-tessbest-2026-10-20/run.py"
    (HERE / "runner-diff.patch").write_text("".join(difflib.unified_diff(
        original_runner.read_text().splitlines(True), (HERE / "run.py").read_text().splitlines(True),
        fromfile=str(original_runner), tofile=str(HERE / "run.py"))))
    paths += [p for p in HERE.iterdir() if p.is_file()]
    hashes.update({str(p.resolve()): sha(p) for p in paths})
    write(HERE / "registration.json", {"state": "frozen_before_candidate_inference", "profiles": {"V5": candidate},
        "runtime": control["runtime"], "hashes": hashes, "jobs": control["jobs"], "model_receipt": receipt,
        "evaluator_controls": {"C10_positive_order": True, "FULL_PAGE_negative_order": True,
            "repeat_positive_and_negative": True, "six_additional_pages_frozen": True},
        "budgets": {"development_page_attempts": 7, "conditional_extra_page_attempts": 6, "maximum_new_page_attempts": 13,
            "automatic_retries": 0, "profile_seconds": 900, "page_and_init_seconds": 180,
            "max_tree_rss_bytes": 16 * 2**30, "prelaunch_available_bytes": 10 * 2**30, "available_floor_bytes": 4 * 2**30},
        "resource_amendment": read(HERE / "resource-amendment.json"),
        "extra_page_gate": "All seven source-reviewed results must meet the unchanged acceptance criteria; otherwise no extra inference."})
    verify()
    print("Frozen one V5 server configuration and seven jobs; order/repeat controls passed; no inference.")


def analyze():
    registration = verify()
    refs = {p["id"]: p for p in read(BASE / "corpus/reference.json")["pages"]}
    refs["known"] = read(BASE / "known-reference.json")
    results = {}
    for name, folder in {"R0": BASE / "R0", "FULL_PAGE": FULL, "C10": CONTROL, "V5": HERE / "V5"}.items():
        execution = read(folder / "execution.json")
        rows = []
        for job in registration["jobs"]:
            page = folder / job["id"]
            run = read(page / "execution.json")
            row = {"id": job["id"], "status": run["status"], "seconds": run["seconds"]}
            if run["status"] == "success":
                cells, doc, ref = read(page / "cells.json"), read(page / "document.json"), refs[job["id"]]
                score = audit.evaluator.evaluate(cells, doc, ref)
                order = audit.order_diagnostic(doc, ref)
                row.update(raw_mix_flags=len(score["raw_cells"]["cross_column_mixed_elements"]),
                    document_mix_flags=len(score["document"]["cross_column_mixed_elements"]),
                    omission_flags=score["document"]["whole_unit_omission_candidates"],
                    critical_difference_flags=score["document"]["critical_text_difference_candidates"],
                    order=order, document_sha256=sha(page / "document.json"), cells_sha256=sha(page / "cells.json"))
                if name == "V5":
                    write(page / "score.json", score)
                    write(page / "order.json", order)
            rows.append(row)
        results[name] = {"execution_status": execution["status"], "pages": rows,
            "page_seconds_total": sum(r["seconds"] for r in rows),
            "initialization_seconds": read(folder / "initialization.json")["seconds"],
            "peak_sampled_tree_rss_bytes": execution["peak_sampled_tree_rss_bytes"], "qualification": "REVIEW_REQUIRED"}
    write(HERE / "diagnostics.json", results)
    for name, result in results.items():
        print(name, "seconds", round(result["page_seconds_total"], 3), "RSS GiB", round(result["peak_sampled_tree_rss_bytes"] / 2**30, 3))
        for row in result["pages"]:
            print(row["id"], "mix", row.get("document_mix_flags"), "missing", row.get("omission_flags"),
                  "order", len(row.get("order", {}).get("inversion_candidates", [])),
                  "repeat", len(row.get("order", {}).get("partial_line_repeat_candidates", [])))


if __name__ == "__main__":
    if sys.argv[1:] == ["freeze"]:
        freeze()
    elif sys.argv[1:] == ["analyze"]:
        analyze()
    else:
        raise SystemExit("use freeze or analyze")
