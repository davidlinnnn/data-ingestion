"""Verify and seal the bounded experiment; no inference or output repair."""
from pathlib import Path
import re
import sys

from run import BASE, HERE, effective, read, sha, verify, write


def main():
    registration = verify()
    original = read(BASE / "registration.json")["profiles"]["T1"]
    candidate = effective("TB")
    assert {k: v for k, v in original.items() if k != "ocr_options"} == {k: v for k, v in candidate.items() if k != "ocr_options"}
    assert {k: v for k, v in original["ocr_options"].items() if k != "path"} == {k: v for k, v in candidate["ocr_options"].items() if k != "path"}
    execution = read(HERE / "TB/execution.json")
    assert execution["status"] == "completed" and execution["exit_code"] == 0
    assert execution["API_calls"] == execution["automatic_retries"] == 0
    assert execution["seconds"] < 900 and execution["peak_sampled_tree_rss_bytes"] < 12 * 2**30
    review = read(HERE / "manual-review.json")
    assert review["decision"] == "REJECTED" and review["new_inference_successes"] == 7
    rows = {r["id"]: r for r in review["pages"]}
    assert set(rows) == {j["id"] for j in registration["jobs"]} and len(rows) == 7
    for job in registration["jobs"]:
        folder = HERE / "TB" / job["id"]
        result = read(folder / "execution.json")
        assert result["status"] == "success" and result["seconds"] < 180
        assert sum(result["timings"]["reading_order"]["times"]) > 0
        assert read(folder / "attempt.json")["attempt"] == 1
        assert read(folder / "score.json")["qualification"] == "REVIEW_REQUIRED"
        assert sha(folder / "document.json") == rows[job["id"]]["document_sha256"]
    for example in review["primary_counterexamples"]:
        document = read(HERE / "TB" / example["page"] / "document.json")
        assert sha(HERE / "TB" / example["page"] / "document.json") == example["document_sha256"]
        text = next(t["text"] for t in document["texts"] if t["self_ref"] == example["ref"])
        assert text == example["observed"]
    trace_count = 0
    for name, expected in (("order-traces", 12), ("best-order-traces", 2)):
        summary = read(HERE / name / "summary.json")
        assert len(summary) == expected
        for row in summary:
            trace = read(HERE / name / f'{row["profile"]}-{row["page"]}.json')
            assert trace["new_model_inferences"] == 0 and trace["markdown_equal"]
            assert all(trace["native_replay_equal"].values())
            assert sha(Path(trace["input_result"])) == trace["input_sha256"]
            trace_count += 1
    traces = read(HERE / "order-traces/summary.json")
    for profile, count in (("Heron-full", 5), ("Egret-default", 25), ("Egret-full", 5), ("C10", 0), ("Tesseract-fast", 0)):
        row = next(r for r in traces if r["profile"] == profile and r["page"] == "known")
        assert row["stage_flags"]["predictor_output"]["inversions"] == count
        assert row["stage_flags"]["final_body"]["inversions"] == count and not row["merge_mapping"]
    easy = read(HERE / "order-traces/EasyOCR-known.json")
    assert easy["native_relation_mappings"]["predict_merges"] == {"10": [3, 4, 8, 9, 11]}
    assert not easy["scores"]["assembled"]["mixed_elements"] and easy["scores"]["final_body"]["mixed_elements"]
    for row in read(HERE / "best-order-traces/summary.json"):
        assert row["stage_flags"]["predictor_output"]["inversions"] == 0
        assert row["stage_flags"]["final_body"]["inversions"] == 0
        assert not row["stage_flags"]["final_body"]["unlocated"]
    assert read(HERE / "OSD-control.json")["same_eight_warning_regions"]
    assert len(read(HERE / "OSD-control.json")["best"]) == 8
    previous = []
    for name in ("pdf-core-ocr-regression-2026-10-19", "pdf-core-ocr-official-options-2026-10-19",
                 "pdf-core-ocr-crop-ablation-2026-10-19", "pdf-core-ocr-region-policy-2026-10-20",
                 "pdf-core-official-multicol-2026-10-20"):
        folder = HERE.parent / name
        seal = read(folder / "artifact-seal.json")
        files = seal["files"] if "files" in seal else seal["artifacts"]
        assert all(sha(folder / p) == digest for p, digest in files.items()), name
        previous.append({"folder": name, "unchanged_files": len(files)})
    out = HERE.parent / "pdf-core-native-visualization-2026-10-19/output/order-tessbest"
    manifest = read(out / "manifest.json")
    assert len(manifest["entries"]) == 21 and manifest["new_model_inferences"] == 0
    assert not manifest["source_text_and_geometry_changed"]
    assert all(sha(Path(p)) == digest for p, digest in manifest["inputs"].items())
    assert all(sha(out / p) == digest for p, digest in manifest["outputs"].items())
    token = re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}")
    for path in HERE.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".md", ".py", ".html", ".log", ".patch"):
            assert not token.search(path.read_text()), path
    summary = {"state": "completed_candidate_rejected", "new_successes": 7, "inference_retries": 0,
        "API_calls": 0, "native_postprocessing_replays": trace_count, "replay_text_structure_and_markdown_equal": True,
        "known_and_acl_p2_best_order_correct": True, "official_best_eng_and_chi_tra_hashes_locked": True,
        "same_eight_OSD_warning_regions": True, "native_presentations": 21, "historical_seals_unchanged": previous,
        "extra_page_inferences": 0, "stop_applied": True}
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
    print("Verified seven successes, fourteen exact native-stage replays, twenty-one native views, five unchanged historical seals; candidate rejected and round closed.")


if __name__ == "__main__":
    main()
