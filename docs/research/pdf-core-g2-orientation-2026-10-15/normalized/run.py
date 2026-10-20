"""Reuse frozen baseline observation/guard code on an explicitly derived source."""

import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BASELINE = HERE.parent / "baseline"
spec = importlib.util.spec_from_file_location("frozen_baseline_observer", BASELINE / "run.py")
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
baseline.HERE = HERE
baseline.REGISTRY = HERE / "input-manifest.json"
baseline.REGISTRY_SHA = baseline.sha(baseline.REGISTRY)
baseline.JOBS = [(f"normalized-p{page}-full", page, True, ["en"]) for page in range(3, 7)]
baseline.__file__ = str(Path(__file__).resolve())


def check():
    for name, digest in json.loads((BASELINE / "artifact-sha256.json").read_text()).items():
        assert baseline.sha(BASELINE / name) == digest, f"Frozen baseline changed: {name}"
    manifest = json.loads(baseline.REGISTRY.read_text())
    assert baseline.sha(baseline.REPO / manifest["original_registry_path"]) == manifest["original_registry_sha256"]
    assert importlib.metadata.version("docling") == "2.102.0"
    assert importlib.metadata.version("docling-core") == "2.96.0"
    files = baseline.frozen_files()
    extra = [Path(__file__).resolve(), HERE / "prepare.py", BASELINE / "run.py",
             BASELINE / "artifact-sha256.json", HERE / "input-manifest.json"]
    for page in manifest["pages"]:
        for key in ("normalized_image", "orientation_result", "source_mapping"):
            path = baseline.REPO / page[f"{key}_path"]
            assert baseline.sha(path) == page[f"{key}_sha256"]
            extra.append(path)
    original = manifest["original_source"]
    assert baseline.sha(baseline.REPO / original["path"]) == original["sha256"]
    extra.append(baseline.REPO / original["path"])
    files.update({str(p.relative_to(baseline.REPO)): baseline.sha(p) for p in extra})
    return files


baseline.check = check


if __name__ == "__main__":
    if sys.argv[1:] == ["--freeze"]:
        assert not (HERE / "frozen-inputs.json").exists()
        baseline.save(HERE / "frozen-inputs.json", check())
        print("Derived inputs, original source, classifier mappings and unchanged baseline frozen; no inference.")
    elif len(sys.argv) == 3 and sys.argv[1] == "--worker":
        assert check() == json.loads((HERE / "frozen-inputs.json").read_text())
        baseline.worker(next(j for j in baseline.JOBS if j[0] == sys.argv[2]))
    else:
        baseline.main()
        summary = json.loads((HERE / "summary.json").read_text())
        summary["scope"] = "Four Standard CPU probes of DERIVED classifier-normalized raster PDF pages; not original G1 bytes"
        summary["source_manifest"] = str(baseline.REGISTRY.relative_to(baseline.REPO))
        summary["source_id_alias"] = "SRC05 is local worker compatibility alias for DERIVED-NORMALIZED-CONTROLS"
        baseline.save(HERE / "summary.json", summary)
