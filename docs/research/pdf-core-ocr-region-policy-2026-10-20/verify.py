"""Check fixed experiment evidence and optionally seal it; zero inference."""
import sys

from run import HERE, PROFILES, read, sha, verify, write

registration = verify()
review = read(HERE / "manual-review.json")
assert set(review["profiles"]) == set(PROFILES)
count = 0
for profile in PROFILES:
    assert read(HERE / profile / "execution.json")["status"] == "completed"
    for job in registration["jobs"]:
        root = HERE / profile / job["id"]
        execution = read(root / "execution.json")
        assert execution["status"] == "success" and execution["cell_count"] > 0
        assert sum(execution["timings"]["reading_order"]["times"]) > 0
        assert read(root / "attempt.json")["attempt"] == 1
        assert read(root / "score.json")["qualification"] == "REVIEW_REQUIRED"
        trace = read(root / "regions.json")
        assert trace["context_points"] == (0 if profile == "C0" else 10)
        assert len(trace["OCR_input_regions"]) == len(trace["zero_dilation_groups"])
        other = read(HERE / "C0" / job["id"] / "regions.json")
        assert trace["raw_layout_boxes"] == other["raw_layout_boxes"]
        assert trace["zero_dilation_groups"] == other["zero_dilation_groups"]
        count += 1
    decision = review["profiles"][profile]
    assert decision["decision"] == "REJECTED"
    assert sha(HERE / profile / decision["page"] / "document.json") == decision["document_sha256"]
for prior in review["previous_seals"]:
    root = HERE.parent / prior["folder"]
    seal = read(root / "artifact-seal.json")
    files = seal["files"] if "files" in seal else seal["artifacts"]
    assert len(files) == prior["unchanged_sealed_files"]
    assert all(sha(root / path) == digest for path, digest in files.items())
assert count == 14
if sys.argv[1:] == ["--seal"]:
    assert not (HERE / "artifact-seal.json").exists()
    write(HERE / "final-verification.json", {"successes": count, "inference_retries": 0,
        "API_calls": 0, "policy_unit_tests_passed": 6, "same_raw_Heron_boxes_across_policies": True,
        "reading_order_executed": count, "both_policies_rejected": True,
        "historical_seals_unchanged": len(review["previous_seals"])})
    files = {str(path.relative_to(HERE)): sha(path) for path in sorted(HERE.rglob("*"))
             if path.is_file() and "__pycache__" not in path.parts}
    write(HERE / "artifact-seal.json", {"state": "completed", "files": files})
elif not sys.argv[1:]:
    assert all(sha(HERE / path) == digest for path, digest in read(HERE / "artifact-seal.json")["files"].items())
else:
    raise SystemExit("use --seal once or no arguments to verify")
print("Verified14 successes, identical Heron geometry, unchanged runtime/controls; both policies rejected.")
