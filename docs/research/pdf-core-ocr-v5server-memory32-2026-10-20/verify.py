"""Read-only completion checks and an immutable artifact seal; no inference."""
from pathlib import Path
import re
import sys

from run import BASE, HERE, read, sha, verify, write


def main():
    registration = verify()
    execution = read(HERE / "V5/execution.json")
    assert execution["status"] == "completed" and execution["exit_code"] == 0
    assert execution["API_calls"] == execution["automatic_retries"] == 0
    assert execution["seconds"] < 900 and execution["peak_sampled_tree_rss_bytes"] < 32 * 2**30
    actual = read(HERE / "V5/actual-models.json")
    for key in ("Det", "Rec"):
        assert actual["models"][key]["sha256"] == registration["model_receipt"]["models"][key.lower()]["sha256"]
        assert actual["resolved_config"][key]["ocr_version"] == "PP-OCRv5"
        assert actual["resolved_config"][key]["model_type"] == "server"
    assert all(v == ["CPUExecutionProvider"] for v in actual["providers"].values())
    assert sha(HERE / "V5/recognizer-dictionary.txt") == actual["recognizer_dictionary"]["sha256"]
    review = read(HERE / "manual-review.json")
    assert review["decision"] in ("REJECTED", "DEVELOPMENT_ACCEPTED")
    assert review["new_inference_successes"] == 7
    rows = {r["id"]: r for r in review["pages"]}
    assert set(rows) == {j["id"] for j in registration["jobs"]} and len(rows) == 7
    for job in registration["jobs"]:
        folder = HERE / "V5" / job["id"]
        result = read(folder / "execution.json")
        assert result["status"] == "success" and result["seconds"] < 180
        assert sum(result["timings"]["reading_order"]["times"]) > 0
        assert read(folder / "attempt.json")["attempt"] == 1
        assert read(folder / "score.json")["qualification"] == "REVIEW_REQUIRED"
        assert sha(folder / "document.json") == rows[job["id"]]["document_sha256"]
    for example in review["primary_counterexamples"]:
        document = read(HERE / "V5" / example["page"] / "document.json")
        assert sha(HERE / "V5" / example["page"] / "document.json") == example["document_sha256"]
        text = next(t["text"] for t in document["texts"] if t["self_ref"] == example["ref"])
        assert text == example["observed"]
        assert sha(example["source_image"]) == example["source_image_sha256"]
    if review["decision"] == "REJECTED":
        assert review["primary_counterexamples"] and review["additional_page_inferences"] == 0
        assert not (HERE / "validation-run").exists()
    historical = []
    for name in ("pdf-core-ocr-regression-2026-10-19", "pdf-core-ocr-official-options-2026-10-19",
                 "pdf-core-ocr-crop-ablation-2026-10-19", "pdf-core-ocr-region-policy-2026-10-20",
                 "pdf-core-official-multicol-2026-10-20", "pdf-core-order-tessbest-2026-10-20"):
        folder = HERE.parent / name
        seal = read(folder / "artifact-seal.json")
        files = seal["files"] if "files" in seal else seal["artifacts"]
        assert all(sha(folder / p) == digest for p, digest in files.items()), name
        historical.append({"folder": name, "unchanged_files": len(files)})
    out = HERE.parent / "pdf-core-native-visualization-2026-10-19/output/ocr-v5server-memory32"
    manifest = read(out / "manifest.json")
    assert len(manifest["entries"]) == 21 and manifest["new_model_inferences"] == 0
    assert not manifest["source_text_and_geometry_changed"]
    assert all(sha(Path(p)) == digest for p, digest in manifest["inputs"].items())
    assert all(sha(out / p) == digest for p, digest in manifest["outputs"].items())
    token = re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}")
    for path in HERE.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".md", ".py", ".html", ".log", ".patch"):
            assert not token.search(path.read_text()), path
    summary = {"state": "completed", "decision": review["decision"], "new_successes": 7,
        "API_calls": 0, "inference_retries": 0, "native_presentations": 21,
        "official_model_hashes_and_actual_provider_verified": True,
        "additional_page_inferences": review["additional_page_inferences"],
        "historical_seals_unchanged": historical}
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
    print("Verified seven successful conversions, actual model identities, native presentations and six unchanged historical seals.")


if __name__ == "__main__":
    main()
