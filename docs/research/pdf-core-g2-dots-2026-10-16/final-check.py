"""Verify recorded evidence, not model quality; never read custody holdout PDFs."""
import datetime
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REPORT = HERE.with_suffix(".md")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    registration = read(HERE / "phase-registration.json")
    for item in registration["prior_refs"]:
        assert sha(REPO / item["path"]) == item["sha256"], item["path"]
    prior = read(REPO / registration["prior_refs"][0]["path"])
    for item in prior["files"]:
        assert "holdout" not in item["path"] or not item["path"].endswith(".pdf")
        path = REPO / item["path"]
        assert path.stat().st_size == item["bytes"] and sha(path) == item["sha256"], path
    inputs = read(HERE / "execution-inputs.json")
    for item in inputs["files"]:
        path = HERE / ("cpu-probe-attempt01/run.py" if item["path"] == "cpu-probe.py" else item["path"])
        assert sha(path) == item["sha256"], path
    repair = read(HERE / "setup-repair.json")
    assert repair["native_snapshot_resolution_and_class_import_passed"]
    assert sha(HERE / "cpu-probe.py") == repair["revised_runner_sha256"]
    execution = read(HERE / "cpu-probe/execution.json")
    assert execution["runner_sha256"] == repair["revised_runner_sha256"]
    assert execution["all_owned_children_reaped"] and not execution["quality_pass"]
    assert execution["holdout_reads"] == execution["automatic_retries"] == 0
    assert read(HERE / "process-cleanup.json")["owned_probe_processes_remaining"] == []
    weights = read(HERE / "weights.json")
    assert weights["complete"] and weights["revision"] == registration["model_revision"]
    metadata = read(HERE / "model-source/metadata.json")
    for item in weights["files"]:
        official = next(x for x in metadata["siblings"] if x["rfilename"] == item["file"])
        assert item["bytes"] == official["size"] and item["sha256"] == official["lfs"]["sha256"]
        assert (Path(weights["model_path"]) / item["file"]).stat().st_ino == (Path(repair["snapshot"]) / item["file"]).stat().st_ino
    validation = read(HERE / "validation/verification.json")
    assert sha(HERE / "validation/source-contract.json") == validation["source_contract_sha256"]
    assert sha(HERE / "validation/manifest.json") == validation["manifest_sha256"]
    assert sha(HERE / "validation/sources.md") == validation["sources_md_sha256"]
    for target in re.findall(r"\]\(([^)]+)\)", REPORT.read_text()):
        if not target.startswith(("https:", "http:", "#")):
            path = REPORT.parent / target.split("#")[0]
            assert path.exists() or path in (HERE / "artifacts.json", HERE / "verification.json"), target
    files = sorted(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                   and p not in (HERE / "artifacts.json", HERE / "verification.json")) + [REPORT]
    for path in files:
        if path.suffix == ".json":
            read(path)
    manifest = {"scope": "dots.ocr source, parser preflight, bounded CPU feasibility and unexecuted validation evidence",
                "files": [{"path": str(p.relative_to(REPO)), "bytes": p.stat().st_size, "sha256": sha(p)} for p in files]}
    (HERE / "artifacts.json").write_text(json.dumps(manifest, indent=2) + "\n")
    result = {"verified_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "status": "evidence_integrity_passed_not_model_quality", "prior_payloads_unchanged": len(prior["files"]),
              "new_payloads": len(files), "cpu_status": execution["status"],
              "original_freeze_and_explicit_setup_repair_reconciled": True,
              "holdout_pdf_content_reads": 0, "g2_passed": False,
              "new_manifest_sha256": sha(HERE / "artifacts.json")}
    (HERE / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
