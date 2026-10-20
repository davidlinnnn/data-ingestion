"""Recompute the fixed comparison from retained outputs; no models initialized."""
import hashlib
import json
from pathlib import Path
import statistics
import sys

from run import HERE, PROFILES, read, sha, verify, write


def analyze():
    registered = verify()
    amendment = read(HERE / "environment-amendment.json")
    assert sha(HERE / "registration.json") == amendment["old_registration_sha256"]
    assert sha(amendment["added_vendor_file"]["path"]) == amendment["added_vendor_file"]["sha256"]
    for path, digest in amendment["failed_artifact_hashes"].items():
        assert sha(HERE / "T1-environment-invalid" / path) == digest
    assert all(read(HERE / "R0/known/control.json").values())
    normal = lambda text: "".join(c for c in text.casefold() if c.isalnum())
    orientation = read(HERE / "orientation/result.json")
    direction = {}
    for rotation in (0, 180):
        rows = [r for r in orientation["rows"] if r["input_rotation"] == rotation]
        assert len(rows) == 12
        direction[str(rotation)] = {name: sum(normal(r[name]["text"]) == normal(r["reference"]) for r in rows)
            for name in ("with_classifier", "without_classifier")}
    assert direction == {"0": {"with_classifier": 12, "without_classifier": 12},
        "180": {"with_classifier": 9, "without_classifier": 0}}
    profiles = {}
    for name in PROFILES:
        execution = read(HERE / name / "execution.json")
        assert execution["status"] == "completed"
        rows = []
        for job in registered["jobs"]:
            out = HERE / name / job["id"]
            metric = read(out / "execution.json")
            assert metric["status"] == "success" and metric["cell_count"] > 0
            score = read(out / "score.json")
            assert score["qualification"] == "REVIEW_REQUIRED"
            rows.append({"id": job["id"], "seconds": metric["seconds"],
                "ocr_seconds": sum(metric["timings"].get("ocr", {}).get("times", [])),
                "cell_count": metric["cell_count"],
                "automatic_document_mix_flags": len(score["document"]["cross_column_mixed_elements"])})
        profiles[name] = {"pages": rows, "page_seconds_total": sum(r["seconds"] for r in rows),
            "page_seconds_median": statistics.median(r["seconds"] for r in rows),
            "ocr_seconds_total": sum(r["ocr_seconds"] for r in rows),
            "initialization_seconds": read(HERE / name / "initialization.json")["seconds"],
            "peak_sampled_tree_rss_bytes": execution["peak_sampled_tree_rss_bytes"],
            "whole_worker_seconds": execution["seconds"], "decision": "NOT_ADOPTED_AS_GLOBAL_PROFILE"}
    return {"state": "COMPLETED_NO_GLOBAL_METHOD_ACCEPTED", "profiles": profiles, "direction": direction,
        "valid_profile_page_attempts": 21, "invalid_environment_page_attempts": 7,
        "documented_environment_corrected_profile_reruns": 1,
        "inference_tuning_retries": 0, "API_calls": 0,
        "evidence": {name: sha(HERE / name) for name in ("known-review.json", "manual-english-review.json",
            "manual-chinese-review.json", "report.md", "registration.json", "environment-amendment.json")},
        "limits": "Exposed clean-raster regression; diagnostic flags manually adjudicated; no full Profile, noisy scan, whole-page rotation, p95, GPU, VLM, or downstream reading-order qualification."}


if __name__ == "__main__":
    result = analyze()
    if sys.argv[1:] == ["--check"]:
        assert result == read(HERE / "analysis.json")
    elif not sys.argv[1:]:
        assert not (HERE / "analysis.json").exists()
        write(HERE / "analysis.json", result)
    else:
        raise SystemExit("use no args once, or --check for read-only verification")
    print(json.dumps({k: result[k] for k in ("state", "valid_profile_page_attempts", "invalid_environment_page_attempts", "direction")}, ensure_ascii=False))
