"""Lock options, inputs, control artifacts and model bytes before inference."""
import difflib
import importlib.metadata
from pathlib import Path

from run import BASE, HERE, PROFILES, effective, read, sha, write
from analyze import CONTROLS, selfcheck


def main():
    assert not (HERE / "registration.json").exists()
    assert not any((HERE / p).exists() for p in PROFILES)
    checks = selfcheck()
    assert checks.pop("new_inference_calls") == 0 and all(checks.values())
    previous = read(BASE / "registration.json")
    hashes = dict(previous["hashes"])
    for path, digest in hashes.items():
        assert sha(path) == digest, path
    baseline = previous["profiles"]["R0"]
    profiles = {p: effective(p) for p in PROFILES}
    expected_full = read(HERE.parent / "pdf-core-ocr-official-options-2026-10-19/registration.json")["profiles"]["full"]
    diffs = {}
    for name, options in profiles.items():
        control = baseline if name == "E-default" else expected_full
        assert {k: v for k, v in options.items() if k != "layout_options"} == {k: v for k, v in control.items() if k != "layout_options"}
        assert {k: v for k, v in options["layout_options"].items() if k != "model_spec"} == {k: v for k, v in control["layout_options"].items() if k != "model_spec"}
        assert not options["allow_external_plugins"] and not options["enable_remote_services"]
        diffs[name] = {"layout_model": options["layout_options"]["model_spec"], "ocr_mode": options["ocr_options"]["mode"],
                       "other_pipeline_and_engine_options_equal_to_control": True}
    model = Path("/private/tmp/pdf-core-native-20261017/artifacts/docling-project--docling-layout-egret-large")
    assert model.resolve().name == "fff417c78abd6bab338c87706c95a8d79dc68f1e"
    assert {"config.json", "preprocessor_config.json", "model.safetensors"} <= {p.name for p in model.iterdir()}
    for path in model.iterdir():
        if path.is_file():
            hashes[str(path.resolve())] = sha(path)
    for folder in CONTROLS.values():
        for path in folder.rglob("*"):
            if path.is_file():
                hashes[str(path.resolve())] = sha(path)
    for path in HERE.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            hashes[str(path.resolve())] = sha(path)
    for name, version in previous["runtime"].items():
        assert importlib.metadata.version(name) == version, name
    old_runner = HERE.parent / "pdf-core-ocr-official-options-2026-10-19/run.py"
    diff = "".join(difflib.unified_diff(old_runner.read_text().splitlines(True), (HERE / "run.py").read_text().splitlines(True),
                                        fromfile=str(old_runner), tofile=str(HERE / "run.py")))
    (HERE / "runner-diff.patch").write_text(diff)
    hashes[str((HERE / "runner-diff.patch").resolve())] = sha(HERE / "runner-diff.patch")
    write(HERE / "registration.json", {"state": "frozen_before_candidate_inference", "profiles": profiles,
        "runtime": previous["runtime"], "hashes": hashes, "jobs": previous["jobs"],
        "diffs": diffs, "model_revision": model.resolve().name,
        "budgets": {"new_development_attempts": 14, "conditional_validation_attempts": 6,
            "automatic_retries": 0, "profile_seconds": 900, "page_and_init_seconds": 180,
            "max_tree_rss_bytes": 12 * 2**30, "prelaunch_available_bytes": 10 * 2**30, "available_floor_bytes": 8 * 2**30},
        "scope": "Official presets/modes only; CPU4, no external plugins, no SDK/output modifications, no existing sealed holdout reads.",
        "validation_gate": "At most one development survivor, once on six frozen additional pages; if neither survives, no validation inference."})
    print("Locked official model bytes/options/runtime, 14 cached controls and six validation sources.")


if __name__ == "__main__":
    main()
