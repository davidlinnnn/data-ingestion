"""Offline integrity checks for this image round; never runs a model or an API."""
import hashlib
import importlib.util
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


assert sha(REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json") == "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
prior = {}
for name in ["pdf-core-g2-local-cpu-2026-10-14", "pdf-core-g2-round2-2026-10-14",
             "pdf-core-g2-round3-2026-10-14", "pdf-core-g2-api-2026-10-14"]:
    records = read(REPO / "docs/research" / name / "artifacts.json")["files"]
    for record in records:
        path = REPO / record["path"]
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
    prior[name] = len(records)
for lane in ["classifier", "description"]:
    download = read(HERE / lane / "download.json")
    snapshot = Path(download["snapshot_path"])
    assert snapshot.name == download["revision"]
    for record in download["files"]:
        path = snapshot / record["name"]
        assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"]
        official = record.get("official_lfs_sha256") or record.get("lfs_sha256")
        if official:
            assert sha(path) == official
for record in read(HERE / "classifier/artifacts.json")["files"]:
    path = (REPO if record["path"].startswith("docs/") else HERE / "classifier") / record["path"]
    assert path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], path
classifier = read(HERE / "classifier/observations.json")
assert classifier["exit_code"] == 0 and classifier["stopped"] is None and len(classifier["completed_inputs"]) == 12
assert classifier["runner_sha256"] == sha(HERE / "classifier/probe.py")
description = read(HERE / "description/observations.json")
assert description["runner_sha256"] == sha(HERE / "description/probe.py")
assert description["observations"][0]["exit_code"] == 0 and description["observations"][0]["stopped"] is None
method = read(HERE / "description/run/method.json")
assert method["devices"] == ["cpu"] and method["dtypes"] == ["torch.float32"]
for case in ["g1-s05", "g1-s07"]:
    generation = read(HERE / "description/run" / case / "generation.json")
    assert generation["last_token_is_eos"] and not generation["at_token_limit"]
layout = read(HERE / "layout/summary.json")
assert layout["runner_sha256"] == sha(HERE / "layout/run.py")
assert len(layout["jobs"]) == 2 and all(r["exit_code"] == 0 and r["stopped"] is None for r in layout["jobs"])

spec = importlib.util.spec_from_file_location("image_api_probe", HERE / "api/run.py")
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
api.self_check()
observations = read(HERE / "api/observations.json")
assert len(observations) == len(api.base.JOBS) == 6
for job, record in zip(api.base.JOBS, observations):
    name, case, source, budget, prompt = job
    folder = HERE / "api" / name
    description = read(folder / "request-description.json")
    assert sha(folder / "input.png") == sha(REPO / source) == description["input_sha256"]
    request = api.base.payload((folder / "input.png").read_bytes(), prompt, budget)
    encoded = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()
    assert hashlib.sha256(encoded).hexdigest() == description["http_body_sha256"]
    assert description["runner_sha256"] == sha(HERE / "api/run.py")
    assert record["case"] == case and record["http_status"] == 200 and record["attempts"] == 1
    assert record["finish_reason"] == "stop" and record["returned_model"] == "gpt-6-luna"
    assert record["response_sha256"] == sha(folder / "response.json")
    response = read(folder / "response.json")
    assert not response["choices"][0]["message"].get("refusal")
    assert read(folder / "output.json") == json.loads(response["choices"][0]["message"]["content"])
charts = read(HERE / "review/chart-checks.json")
assert charts["fixed_numeric_observations"] == 13
assert all(r["passed"] and r["numeric_errors"] == 0 for r in charts["results"])
assert len(charts["negative_controls"]) == 7 and all(r["rejected"] for r in charts["negative_controls"])

links = 0
for path in [REPO / "docs/research/pdf-core-g2-images-2026-10-14.md", *HERE.rglob("*.md")]:
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        linked = (path.parent / target.split("#")[0]).resolve()
        assert linked.exists() or linked in {HERE / "artifacts.json", HERE / "validation.json"}, (path, target)
        links += 1
files = []
for path in sorted(HERE.rglob("*")):
    if not path.is_file() or path.is_symlink() or "artifacts" in path.relative_to(HERE).parts or "__pycache__" in path.parts:
        continue
    if path.name == "artifacts.json" or path == HERE / "validation.json":
        continue
    if path.suffix != ".png":
        assert not re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", path.read_text()), "Possible credential; never print matching text"
    files.append({"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size, "sha256": sha(path)})
save(HERE / "artifacts.json", {"scope": "Owned image-round payloads; excludes manifests, model-cache symlinks and ephemeral Python caches", "files": files})
save(HERE / "validation.json", {"g1_registry_unchanged": True, "prior_payloads_unchanged": prior,
    "local_model_hashes_and_official_lfs_match": True, "api_requests_reconstruct_to_body_hash": True,
    "six_http200_stop_json_results": True, "credential_pattern_scan_clean": True,
    "chart_numeric_observations": 13, "chart_negative_controls": 7,
    "local_markdown_links_checked": links, "payload_files": len(files), "payload_bytes": sum(x["bytes"] for x in files)})
print(json.dumps(read(HERE / "validation.json")))
