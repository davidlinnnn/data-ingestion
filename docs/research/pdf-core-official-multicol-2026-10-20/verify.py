"""Verify or seal the completed finite experiment; never run model inference."""
from pathlib import Path
import re
import sys

from run import HERE, PROFILES, read, sha, verify, write
from analyze import CONTROLS, order_diagnostic, selfcheck


def main():
    registration = verify()
    checks = selfcheck()
    assert checks.pop("new_inference_calls") == 0 and all(checks.values())
    review = read(HERE / "manual-review.json")
    assert review["decision"] == "STOP_NO_QUALIFIED_CANDIDATE" and review["validation_inferences"] == 0
    diagnostics = read(HERE / "diagnostics.json")
    count, equal = 0, 0
    ref = read(HERE.parent / "pdf-core-ocr-regression-2026-10-19/known-reference.json")
    for profile in PROFILES:
        execution = read(HERE / profile / "execution.json")
        assert execution["status"] == "completed" and execution["exit_code"] == 0
        assert execution["API_calls"] == execution["automatic_retries"] == 0
        assert execution["peak_sampled_tree_rss_bytes"] < 12 * 2**30
        assert execution["seconds"] < 900
        assert review["profiles"][profile]["decision"] == "REJECTED"
        rows = {r["id"]: r for r in review["profiles"][profile]["pages"]}
        assert set(rows) == {j["id"] for j in registration["jobs"]}
        for job in registration["jobs"]:
            folder = HERE / profile / job["id"]
            run = read(folder / "execution.json")
            assert run["status"] == "success" and run["cell_count"] > 0
            assert run["seconds"] < 180
            assert sum(run["timings"]["reading_order"]["times"]) > 0
            assert read(folder / "attempt.json")["attempt"] == 1
            assert read(folder / "score.json")["qualification"] == "REVIEW_REQUIRED"
            assert sha(folder / "document.json") == rows[job["id"]]["document_sha256"]
            if profile == "E-full":
                assert read(folder / "cells.json") == read(CONTROLS["H-full"] / job["id"] / "cells.json")
                equal += 1
            count += 1
        document = read(HERE / profile / "known/document.json")
        order = order_diagnostic(document, ref)
        assert order == read(HERE / profile / "known/order.json")
        assert len(order["inversion_candidates"]) == (25 if profile == "E-default" else 5)
        assert not order["unlocated_units"]
        assert order == diagnostics[profile]["pages"][0]["order"]
        text = " ".join(t["text"] for t in document["texts"])
        assert "Background." in text and "2 OVERVIEW" in text
    assert count == 14 and equal == 7
    assert not (HERE / "validation-run").exists()
    previous = []
    for name in ("pdf-core-ocr-regression-2026-10-19", "pdf-core-ocr-official-options-2026-10-19",
                 "pdf-core-ocr-crop-ablation-2026-10-19", "pdf-core-ocr-region-policy-2026-10-20"):
        folder = HERE.parent / name
        seal = read(folder / "artifact-seal.json")
        files = seal["files"] if "files" in seal else seal["artifacts"]
        assert all(sha(folder / path) == digest for path, digest in files.items()), name
        previous.append({"folder": name, "unchanged_files": len(files)})
    out = HERE.parent / "pdf-core-native-visualization-2026-10-19/output/official-multicol"
    manifest = read(out / "manifest.json")
    assert len(manifest["entries"]) == 28 and manifest["new_model_inferences"] == 0
    assert not manifest["source_text_and_geometry_changed"]
    assert all(sha(Path(path)) == digest for path, digest in manifest["inputs"].items())
    assert all(sha(out / path) == digest for path, digest in manifest["outputs"].items())
    secret = re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}")
    for path in HERE.rglob("*"):
        if path.is_file() and path.suffix in (".py", ".json", ".md", ".txt", ".html", ".log", ".patch"):
            assert not secret.search(path.read_text()), f"credential pattern: {path}"
    summary = {"state": "completed_no_qualified_candidate", "new_successes": count,
        "inference_retries": 0, "API_calls": 0, "conditional_validation_calls": 0,
        "FULL_PAGE_OCR_controls_equal": equal, "native_reading_order_executed": count,
        "evaluator_controls_passed": checks, "historical_seals_unchanged": previous,
        "native_presentations": 28, "known_order_pair_inversions": {"E-default": 25, "E-full": 5}}
    if sys.argv[1:] == ["--seal"]:
        assert not (HERE / "artifact-seal.json").exists()
        write(HERE / "final-verification.json", summary)
        files = {str(p.relative_to(HERE)): sha(p) for p in sorted(HERE.rglob("*"))
                 if p.is_file() and "__pycache__" not in p.parts}
        write(HERE / "artifact-seal.json", {"state": "completed", "files": files})
    elif not sys.argv[1:]:
        assert read(HERE / "final-verification.json") == summary
        assert all(sha(HERE / p) == digest for p, digest in read(HERE / "artifact-seal.json")["files"].items())
    else:
        raise SystemExit("use --seal once, then no arguments")
    print("Verified 14 successes, 7 exact OCR controls, 28 native views, four unchanged historical seals; both candidates rejected.")


if __name__ == "__main__":
    main()
