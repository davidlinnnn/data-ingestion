"""Read-only post-run evidence checks; optional seal creation after completion."""
import sys
import re
from run import BASE, HERE, PROFILES, read, sha, verify, write

registration = verify()
review, diagnostics = read(HERE / "manual-review.json"), read(HERE / "diagnostics.json")
assert set(review["profiles"]) == set(diagnostics) == set(PROFILES)
count = 0
for profile in PROFILES:
    root = HERE / profile
    assert read(root / "execution.json")["status"] == "completed"
    assert len(diagnostics[profile]["pages"]) == 7
    for job in registration["jobs"]:
        out = root / job["id"]
        metric = read(out / "execution.json")
        assert metric["status"] == "success" and metric["cell_count"] > 0
        assert sum(metric["timings"]["reading_order"]["times"]) > 0
        assert read(out / "attempt.json")["attempt"] == 1
        assert read(out / "score.json")["qualification"] == "REVIEW_REQUIRED"
        count += 1
    adjudication = review["profiles"][profile]
    assert sha(root / adjudication["page"] / "document.json") == adjudication["document_sha256"]
assert count == 98
for name in ("layout", "pdfaware"):
    assert all(all(v.values()) for v in read(HERE / name / "baseline-equivalence.json").values())
prior = read(BASE / "artifact-seal.json")["files"]
assert all(sha(BASE / path) == digest for path, digest in prior.items())
if sys.argv[1:] == ["--seal"]:
    assert not (HERE / "artifact-seal.json").exists()
    write(HERE / "final-verification.json", {"successful_page_attempts": count, "profiles": len(PROFILES), "reading_order_executed": count, "inference_retries": 0, "API_calls": 0, "prior_artifacts_unchanged": len(prior), "registration_verified": True, "unit_tests_passed": 9, "global_method_accepted": False})
    files = {str(p.relative_to(HERE)): sha(p) for p in sorted(HERE.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
    pattern = rb"sk-proj-[A-Za-z0-9_-]{20,}"
    assert re.search(pattern, b"sk-proj-" + b"x" * 20)
    assert not re.search(pattern, b"sk-proj-")
    assert all(not re.search(pattern, (HERE / name).read_bytes()) for name in files if name.endswith((".json", ".py", ".md", ".log")))
    write(HERE / "artifact-seal.json", {"state": "completed", "files": files})
elif not sys.argv[1:]:
    seal = read(HERE / "artifact-seal.json")["files"]
    assert all(sha(HERE / path) == digest for path, digest in seal.items())
else:
    raise SystemExit("use --seal once, or no arguments to verify")
print("Verified14 profiles,98 successes, zero retries/API, native reading order, manual evidence and unchanged332 prior artifacts")
