"""Compare frozen evidence only; never refresh manifests or execute models."""
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    seal = HERE / "artifacts.json"
    assert seal.exists(), "Seal must already exist; checker does not create it"
    seal_before = seal.read_bytes()
    old_counts = []
    for name in ["docs/research/pdf-core-g2-dots-mlx-2026-10-16/artifacts.json",
                 "docs/research/pdf-core-g2-official-method-2026-10-15/artifacts.json",
                 "docs/reviews/pdf-core-experiment-audit-2026-10-16/artifacts.json"]:
        entries = read(REPO / name)["files"]
        for item in entries:
            path = REPO / item["path"]
            assert not ("holdout" in str(path) and path.suffix == ".pdf")
            assert sha(path) == item["sha256"], str(path)
        old_counts.append(len(entries))
    assert sum(old_counts[:2]) == 326 and old_counts[2] == 119
    for name, backup in [("render-execution-freeze.json", "render-pre-review.py"),
                         ("render-execution-freeze-v2.json", "render-reviewed-v1.py"),
                         ("render-approval-freeze.json", "render-reviewed-v1.py"),
                         ("render-execution-freeze-v3.json", None),
                         ("render-approval-freeze-v2.json", None)]:
        for item in read(HERE / name)["files"]:
            path = REPO / item["path"]
            if backup and path.name == "render_preflight.py":
                path = HERE / backup
            assert sha(path) == item["sha256"], str(path)

    original = read(HERE / "render-inputs/results.json")
    inputs = read(HERE / "render-inputs-v2/results.json")
    gate = read(HERE / "render-gate-v2/results.json")
    failed_gate = read(HERE / "render-gate/results.json")
    approvals = read(HERE / "render-approvals-v2.json")["records"]
    assert original["status"] == inputs["status"] == gate["status"] == "completed"
    assert failed_gate["status"] != "completed" and len(failed_gate["records"]) == 8
    assert all(x["decision"] == "blocked" and x["stub_transport_calls"] == 0 for x in failed_gate["records"])
    assert inputs["options"] == gate["options"]
    assert inputs["runner_sha256"] == gate["runner_sha256"] == sha(HERE / "render_preflight.py")
    assert len({x["id"] for x in inputs["records"]}) == len(approvals) == len(gate["records"]) == 8
    for before, capture, approval, replay in zip(original["records"], inputs["records"], approvals, gate["records"], strict=True):
        assert before["id"] == capture["id"] == approval["id"] == replay["id"]
        fp = capture["fingerprint"]
        assert fp == approval["fingerprint"] == replay["fingerprint"]
        assert {k: v for k, v in before["fingerprint"].items() if k != "options_sha256"} == {k: v for k, v in fp.items() if k != "options_sha256"}
        assert fp["options_sha256"] == json_sha(inputs["options"])
        assert fp["engine_input_sha256"] == json_sha(capture["engine_input"])
        assert capture["engine_input"] == before["engine_input"]
        image = HERE / "render-inputs-v2" / (capture["id"] + ".png")
        assert sha(image) == capture["image_file_sha256"] == before["image_file_sha256"]
        with Image.open(image) as im:
            assert list(im.size) == fp["image_size"]
            assert hashlib.sha256(im.convert("RGB").tobytes()).hexdigest() == fp["pixel_sha256"]
        source = REPO / fp["source_path"]
        assert "holdout" not in str(source) and sha(source) == fp["source_sha256"]
        assert replay["engine_entries"] == 1
        if approval["decision"] == "approved":
            assert replay["decision"] == "allowed" and replay["stub_transport_calls"] == 1
            assert replay["native_stub_conversion_status"] == "success"
        else:
            assert approval["decision"] == "rejected" and replay["decision"] == "blocked"
            assert replay["stub_transport_calls"] == 0
    assert sum(x["decision"] == "allowed" for x in gate["records"]) == 6
    assert sum(x["decision"] == "blocked" for x in gate["records"]) == 2
    guard = read(HERE / "guard-final-verification-v2.json")
    assert guard["gate_results_sha256"] == sha(HERE / "render-gate-v2/results.json")
    assert guard["guard_control_count"] == len(guard["guard_controls"]) == 106
    assert all(x["passed"] for x in guard["integrity_checks"] + guard["guard_controls"])
    schema = read(HERE / "guard-schema-controls-v2.json")
    checks = [x for process in schema["processes"] for x in process["checks"]]
    assert len(checks) == 66 and all(x["passed"] for x in checks)
    for run in [original, inputs, failed_gate, gate]:
        assert run["model_calls"] == run["network_calls"] == run["holdout_reads"] == 0
        assert run["model_loaded"] is False

    parser = read(HERE / "parser/registration.json")
    assert sha(HERE / "parser/inputs.json") == parser["inputs_sha256"]
    assert sha(HERE / "parser/preflight.py") == parser["runner_sha256"]
    for item in parser["installed_sources"] + parser["original_raw"]:
        assert sha(Path(item["path"])) == item["sha256"]
    result = read(HERE / "parser/run/results.json")
    assert len(result["controls"]) == 16 and len(result["saved_raw_replays"]) == 4
    assert result["typed_code_controls_pass"] and result["original_raw_and_installed_source_hashes_unchanged"]
    assert result["model_calls"] == result["network_calls"] == result["output_repairs"] == 0
    assert result["model_libraries_imported"] == []
    for item in read(HERE / "candidate/retrieval.json"):
        path = HERE / "candidate" / item["file"]
        if "error" in item:
            assert "sha256" not in item and not path.exists()
        else:
            assert sha(path) == item["sha256"]
    for item in read(HERE / "candidate/runtime-identity.json")["records"]:
        assert item["RECORD_matches"] and sha(Path(item["path"])) == item["sha256"]
    candidate = read(HERE / "candidate/candidate-plan.json")
    assert candidate["observed_model_calls"] == candidate["package_installs"] == candidate["holdout_reads"] == 0
    assert candidate["status"] == "awaiting_native_result_export_and_input_preflight"
    native = read(HERE / "candidate/native-synthetic-results.json")
    assert native["component_only"] and native["complete_unchanged_official_modules"]
    assert not native["whole_result_and_save_to_markdown_tested"]
    entries = read(seal)["files"]
    for item in entries:
        assert sha(REPO / item["path"]) == item["sha256"], item["path"]
    assert seal.read_bytes() == seal_before
    print(json.dumps({"status": "integrity_passed_not_quality_acceptance", "new_seal_entries_compared": len(entries),
        "old_model_entries_unchanged": sum(old_counts[:2]), "old_audit_entries_unchanged": old_counts[2],
        "actual_rendered_inputs": 8, "allowed_stub_conversions": 6, "blocked_before_stub": 2,
        "failed_first_gate_preserved": True, "parser_source_controls": 16, "saved_raw_replays": 4,
        "model_calls_by_checker": 0, "manifest_refreshed": False, "g2_passed": False}))


if __name__ == "__main__":
    assert not sys.argv[1:]
    main()
