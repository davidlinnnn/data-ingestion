"""Read-only verification of corpus, methods, effective options and output completeness."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R2 = HERE.parent / "pdf-core-w2-native-coverage-round2-2026-10-20"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_supported_engines(value):
    # Model metadata serializes a set in process-dependent order. Enrichment is off.
    if isinstance(value, dict):
        return {k: sorted(v) if k == "supported_engines" and isinstance(v, list) else normalize_supported_engines(v) for k,v in value.items()}
    if isinstance(value, list):
        return [normalize_supported_engines(v) for v in value]
    return value


def main():
    load = lambda p: json.loads(p.read_text())
    registration = load(HERE / "registration.json")
    checks = {}
    for name, expected in registration["method_sha256"].items():
        checks["method:" + name] = digest(HERE / name) == expected
    checks["backend_source"] = digest(Path(registration["backend_source"])) == registration["backend_source_sha256"]
    checks["analyzer_v3"] = digest(R2 / "analyze_full.py") == registration["analyzer_sha256"]
    freeze_path = R2 / "oracle/freeze.json"
    checks["oracle_seal"] = digest(freeze_path) == "17c02e47c9e11fabdeb996b2d7327d3326b45feff80baa3125218693cd518c4e"
    freeze = load(freeze_path)
    for name, expected in freeze["files"].items():
        checks["oracle:" + name] = digest(freeze_path.parent / name) == expected
    jobs = load(HERE / "jobs.json")["jobs"]
    selected = load(HERE / "selected-effective-options.json")
    pages = 0
    for job in jobs:
        checks["pdf:" + job["id"]] = digest(Path(job["pdf"])) == job["pdf_sha256"]
        dest = HERE / "runs/V4/jobs" / job["id"]
        conv = load(dest / "conversion.json")
        checks["conversion:" + job["id"]] = conv["status"] == "success" and conv["retries"] == 0 and conv["pages_returned"] == job["last"] - job["first"] + 1
        effective = load(dest / "effective-options.json")
        checks["effective_options:" + job["id"]] = normalize_supported_engines(effective) == normalize_supported_engines(selected)
        for filename in ("document.json", "document.md", "stage-events.json", "timings.json"):
            checks["saved:" + job["id"] + ":" + filename] = (dest / filename).is_file() and (dest / filename).stat().st_size > 0
        pages += conv["pages_returned"]
    before = (R2 / "run_full.py").read_text().split("def stop_reason", 1)[0]
    expected = before.replace("PyPdfiumDocumentBackend", "ThreadedDoclingParseDocumentBackend")
    expected = expected.replace("from docling.backend.pypdfium2_backend import", "from docling.backend.docling_parse_backend import")
    checks["worker_only_backend_substitution"] = (HERE / "worker.py").read_text().rstrip() == expected.rstrip()
    execution = load(HERE / "runs/V4/execution.json")
    checks["rss_guard"] = all(r["peak_tree_rss_bytes"] <= 12 * 1024**3 for r in execution["records"])
    checks["single_worker_zero_retry"] = len(execution["records"]) == 36 and all(r["retries"] == 0 and r["status"] == "success" for r in execution["records"])
    checks["scope"] = len(jobs) == 36 and pages == 715
    result = dict(status="PASS" if all(checks.values()) else "FAIL", checks=checks, documents=len(jobs), pages=pages,
                  frozen_oracle_files=len(freeze["files"]), effective_options_normalization="Only supported_engines metadata set order is sorted; all values retained. Chart enrichment remains disabled.", limitations="Checks registered file hashes, saved configuration and sampled process guard. Does not prove semantic completeness or continuous unsampled RSS bounds.")
    (HERE / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(status=result["status"], checks=len(checks), failed=[k for k,v in checks.items() if not v], documents=len(jobs), pages=pages)))


if __name__ == "__main__":
    main()
