"""Freeze the single model-family comparison before candidate inference."""
import difflib
import importlib.metadata
from pathlib import Path

from run import BASE, HERE, PROFILES, effective, read, sha, write
from trace_order import audit, PROFILES as TRACE_PROFILES


def main():
    assert not (HERE / "registration.json").exists() and not (HERE / "TB").exists()
    reference = read(BASE / "known-reference.json")
    positive = audit.order_diagnostic(read(TRACE_PROFILES["C10"] / "known/document.json"), reference)
    negative = audit.order_diagnostic(read(TRACE_PROFILES["Heron-full"] / "known/document.json"), reference)
    assert positive["observed_anchor_order"] == reference["body_order"] and not positive["inversion_candidates"]
    assert len(negative["inversion_candidates"]) == 5 and not negative["unlocated_units"]
    assert Path(audit.evaluator.__file__).parent == BASE
    checks = {"C10_correct_12_unit_order": True, "FULL_PAGE_five_inversions_detected": True,
              "frozen_source_evaluator_reused": True}
    old = read(BASE / "registration.json")
    options, control = effective("TB"), old["profiles"]["T1"]
    assert PROFILES == ("TB",)
    assert {k: v for k, v in options.items() if k != "ocr_options"} == {k: v for k, v in control.items() if k != "ocr_options"}
    assert {k: v for k, v in options["ocr_options"].items() if k != "path"} == {k: v for k, v in control["ocr_options"].items() if k != "path"}
    assert not options["enable_remote_services"] and not options["allow_external_plugins"]
    receipt = read(HERE / "model-receipt.json")
    for row in receipt["recognition_models"]:
        path = HERE / "tessdata-best" / row["name"]
        assert sha(path) == row["sha256"] and path.stat().st_size == row["bytes"]
    for name in ("osd.traineddata", "configs/tsv"):
        assert sha(HERE / "tessdata-best" / name) == sha(BASE / "tessdata" / name)
    hashes = dict(old["hashes"])
    for path, digest in hashes.items():
        assert sha(path) == digest, path
    for name, version in old["runtime"].items():
        assert importlib.metadata.version(name) == version, name
    original = HERE.parent / "pdf-core-official-multicol-2026-10-20/run.py"
    (HERE / "runner-diff.patch").write_text("".join(difflib.unified_diff(original.read_text().splitlines(True),
        (HERE / "run.py").read_text().splitlines(True), fromfile=str(original), tofile=str(HERE / "run.py"))))
    paths = [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    paths += [p for p in (BASE / "T1").rglob("*") if p.is_file()]
    paths += [Path("/opt/homebrew/bin/tesseract"), BASE / "R0/known/control.json"]
    paths += [Path(audit.__file__), Path(audit.evaluator.__file__), Path(audit.legacy.__file__)]
    for folder in TRACE_PROFILES.values():
        for page in ("known", "acl-p2"):
            paths += [folder / page / "result.json", folder / page / "document.md"]
    from docling.models.stages.reading_order import readingorder_model
    from docling.models.postprocessing import reading_order_rb
    paths += [Path(readingorder_model.__file__), Path(reading_order_rb.__file__)]
    hashes.update({str(p.resolve()): sha(p) for p in paths})
    traces = read(HERE / "order-traces/summary.json")
    assert len(traces) == 12 and all(t["native_text_structure_replay_exact"] for t in traces)
    assert next(t for t in traces if t["profile"] == "Heron-full" and t["page"] == "known")["stage_flags"]["predictor_output"]["inversions"] == 5
    assert next(t for t in traces if t["profile"] == "C10" and t["page"] == "known")["stage_flags"]["predictor_output"]["inversions"] == 0
    write(HERE / "registration.json", {"state": "frozen_before_candidate_inference", "profiles": {"TB": options},
        "runtime": old["runtime"], "hashes": hashes, "jobs": old["jobs"], "model_receipt": receipt,
        "evaluator_controls": checks, "scope": "One official model-family change, fast to best; same eng/chi_tra, Heron, PSM3 and seven raster pages.",
        "budgets": {"new_page_attempts": 7, "automatic_retries": 0, "profile_seconds": 900, "page_and_init_seconds": 180,
            "max_tree_rss_bytes": 12 * 2**30, "prelaunch_available_bytes": 10 * 2**30, "available_floor_bytes": 8 * 2**30},
        "stop": "Any major content/order regression rejects this candidate; no new variants or automatic extra-page inference."})
    print("Frozen best/fast model-family comparison, seven inputs, native-stage replay controls and all options/runtime hashes.")


if __name__ == "__main__":
    main()
