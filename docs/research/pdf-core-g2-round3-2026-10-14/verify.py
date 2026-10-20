"""Offline evidence integrity checks; never runs inference or rewrites earlier rounds."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


registry = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
assert sha(registry) == "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
prior = {}
for folder in ["pdf-core-g2-local-cpu-2026-10-14", "pdf-core-g2-round2-2026-10-14"]:
    manifest = read(REPO / "docs/research" / folder / "artifacts.json")
    for record in manifest["files"]:
        path = REPO / record["path"]
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
    prior[folder] = len(manifest["files"])

download = read(HERE / "vlm/download.json")
snapshot = Path(download["snapshot_path"])
assert snapshot.name == download["revision"] == "982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe"
assert (HERE / "vlm/artifacts/ibm-granite--granite-docling-258M").resolve() == snapshot.resolve()
for record in download["files"]:
    path = snapshot / record["name"]
    assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"]
    if record["official_lfs_sha256"]:
        assert sha(path) == record["official_lfs_sha256"]
effective_eos = read(snapshot / "generation_config.json")["eos_token_id"]
observations = read(HERE / "vlm/observations.json")
assert sha(HERE / "vlm/probe.py") == observations["runner_sha256"]
for record in observations["observations"]:
    assert record["exit_code"] == 0 and record["stopped"] is None
    folder = HERE / "vlm" / record["case"]
    method, generation, source = (read(folder / name) for name in ["method.json", "generation.json", "input.json"])
    assert source["input_sha256"] == sha(folder / "input.png")
    assert method["devices"] == ["cpu"] and method["dtypes"] == ["torch.float32"]
    assert generation["eos_token_ids"] == effective_eos
    assert generation["last_token_is_eos"] and not generation["at_token_limit"]
assert sha(HERE / "vlm/seal-eq2/input.png") == sha(REPO / "docs/research/pdf-core-g2-round2-2026-10-14/models/seal-eq2/input.png")

for folder in [HERE / "ocr", HERE / "vlm/table-crop"]:
    for record in read(folder / "artifacts.json")["files"]:
        path = (REPO if record["path"].startswith("docs/") else folder) / record["path"]
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
crop = HERE / "vlm/table-crop"
assert sha(crop / "run.py") == read(crop / "observations.json")["runner_sha256"]
crop_observation = read(crop / "observations.json")["observations"][0]
assert crop_observation["exit_code"] == 0 and crop_observation["stopped"] is None
assert sha(crop / "run/input.png") == "e15d7737e1fd4dc28dde61fd7845dc00a59cda731a521a6a8bebc39b3a9dfc9a"
crop_generation = read(crop / "run/generation.json")
assert crop_generation["last_token_is_eos"] and not crop_generation["at_token_limit"]
assert crop_generation["eos_token_ids"] == effective_eos

links = []
reports = [REPO / "docs/research/pdf-core-g2-round3-2026-10-14.md", *HERE.rglob("*.md")]
for path in reports:
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        linked = (path.parent / target.split("#")[0]).resolve()
        assert linked.exists() or linked in {HERE / "artifacts.json", HERE / "validation.json"}, (path, target)
        links.append({"from": str(path.relative_to(REPO)), "target": target})

files = []
for path in sorted(HERE.rglob("*")):
    if not path.is_file() or path.is_symlink() or "artifacts" in path.relative_to(HERE).parts:
        continue
    if path.name in {"artifacts.json", "validation.json"} or "__pycache__" in path.parts:
        continue
    files.append({"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size, "sha256": sha(path)})
save(HERE / "artifacts.json", {"scope": "Third round owned payloads; separate pinned weights and per-lane manifests excluded",
     "files": files})
save(HERE / "validation.json", {"g1_registry_unchanged": True, "prior_round_payloads_unchanged": prior,
     "granite_snapshot_hashes_and_official_lfs_match": True, "formula_input_byte_equal_round2": True,
     "generation_eos_matches_engine_loaded_snapshot_config": True, "local_markdown_links_checked": len(links),
     "payload_files": len(files), "payload_bytes": sum(f["bytes"] for f in files)})
print(json.dumps(read(HERE / "validation.json")))
