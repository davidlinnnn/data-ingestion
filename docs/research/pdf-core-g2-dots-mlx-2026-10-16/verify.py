"""Verify experiment custody and actual outcomes; not a model-quality pass."""
import datetime
import hashlib
import json
from pathlib import Path
import re

import psutil
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DIAG = HERE.parent / "pdf-core-g2-dots-mlx-renderer-diagnostic-2026-10-16"
REPORT = HERE.with_suffix(".md")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    reg = read(HERE / "registration.json")
    for item in reg["prior_refs"]:
        assert sha(REPO / item["path"]) == item["sha256"], item["path"]
    old_manifests = [HERE.parent / "pdf-core-g2-dots-2026-10-16/artifacts.json",
                     HERE.parent / "pdf-core-g2-official-method-2026-10-15/artifacts.json"]
    prior_count = 0
    for manifest in old_manifests:
        for item in read(manifest)["files"]:
            assert "holdout" not in item["path"] or not item["path"].endswith(".pdf")
            assert sha(REPO / item["path"]) == item["sha256"], item["path"]
            prior_count += 1
    for freeze in [HERE / "execution-inputs.json", HERE / "execution-inputs-v2.json"]:
        for item in read(freeze)["files"]:
            assert sha(HERE / item["path"]) == item["sha256"], item["path"]
    installed = Path("/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages")
    for item in read(HERE / "runtime-source-hashes.json"):
        assert sha(installed / item["path"]) == item["sha256"], item["path"]
    total_calls = 0
    for base, expected in [(HERE, 12), (DIAG, 2)]:
        execution = read(base / "run/execution.json")
        assert execution["status"] == "completed" and execution["all_owned_children_reaped"]
        assert execution["holdout_reads"] == execution["automatic_retries"] == 0
        assert sha(base / "run.py") == execution["runner_sha256"]
        records = read(base / "run/completed-pages.json")
        assert len(records) == expected and len({x["id"] for x in records}) == expected
        assert all(x["status"] == "success" for x in records)
        for record in records:
            path = base / "run" / record["id"]
            assert read(path / "generation.json")["finish_reason"] == "stop"
            assert read(path / "prediction.json")["outputs"][0]["text"] == (path / "raw.txt").read_text()
        total_calls += len(records)
    mapping = read(HERE / "run/weight-mapping.json")
    assert mapping["tensor_count"] == 643 and mapping["parameters"] == 3039179264 and mapping["all_bfloat16"]
    cpu = read(HERE / "cpu-processor-reference.json")
    actual = read(HERE / "run/controls-p1/actual-processor.json")
    for key, value in cpu["arrays"].items():
        assert actual["arrays"][key]["canonical_sha256"] == value["sha256"], key
    for record in read(HERE / "renderer-preflight/results.json")["records"]:
        image = Image.open(DIAG / f"run/validation-02-p{record['page']}/input.png").convert("RGB")
        assert hashlib.sha256(image.tobytes()).hexdigest() == record["official_pypdfium_backend"]["pixel_sha256"]
    review = read(HERE / "review.json")
    assert review["summary"]["g2_passed"] is False and review["summary"]["diagnostics_not_substituted_for_main_validation"]
    assert len(review["exposed_units"]) == 41 and len(review["validation_positive_units"]) == 12 and len(review["validation_negative_units"]) == 10
    live = []
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            if any(x.endswith(str(base.relative_to(REPO) / "run.py")) for x in proc.info["cmdline"] or [] for base in [HERE, DIAG]):
                live.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    assert not live, live
    (HERE / "process-cleanup.json").write_text(json.dumps({"owned_model_processes_remaining": live}, indent=2) + "\n")
    planned = {HERE / "verification.json", HERE / "artifacts.json"}
    for target in re.findall(r"\]\(([^)]+)\)", REPORT.read_text()):
        if not target.startswith(("http:", "https:", "#")):
            path = REPORT.parent / target.split("#")[0]
            assert path.exists() or path in planned, target
    files = [p for base in [HERE, DIAG] for p in base.rglob("*")
             if p.is_file() and p not in planned and "__pycache__" not in p.parts] + [REPORT]
    for path in files:
        if path.suffix == ".json":
            read(path)
    manifest = {"scope": "Pinned dots.ocr MLX main12-page run and separate2-page official-renderer diagnostics; no holdout",
        "files": [{"path": str(p.relative_to(REPO)), "bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(files)]}
    (HERE / "artifacts.json").write_text(json.dumps(manifest, indent=2) + "\n")
    result = {"verified_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status": "evidence_integrity_passed_not_g2", "prior_payloads_unchanged": prior_count,
        "new_payloads": len(files), "completed_model_calls": total_calls, "holdout_pdf_content_reads": 0,
        "owned_processes_remaining": 0, "original_freezes_and_setup_only_addendum_verified": True,
        "main_control_processor_shared_values_equal_cpu": True, "diagnostic_images_equal_render_only_preflight": True,
        "g2_passed": False, "manifest_sha256": sha(HERE / "artifacts.json")}
    (HERE / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
