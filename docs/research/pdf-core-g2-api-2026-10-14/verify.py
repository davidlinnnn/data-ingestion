"""Offline request reconstruction, frozen-evidence and credential-leak checks."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


assert sha((REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json").read_bytes()) == "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
prior = {}
for name in ["pdf-core-g2-local-cpu-2026-10-14", "pdf-core-g2-round2-2026-10-14", "pdf-core-g2-round3-2026-10-14"]:
    files = read(REPO / "docs/research" / name / "artifacts.json")["files"]
    for record in files:
        path = REPO / record["path"]
        assert path.stat().st_size == record["bytes"] and sha(path.read_bytes()) == record["sha256"], path
    prior[name] = len(files)

spec = importlib.util.spec_from_file_location("api_probe", HERE / "run.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.self_check()
observations = read(HERE / "observations.json")
assert len(observations) == len(runner.JOBS) == 4
for job, record in zip(runner.JOBS, observations):
    name, case, source, budget, prompt = job
    out = HERE / name
    description = read(out / "request-description.json")
    image = (out / "input.png").read_bytes()
    assert image == (REPO / source).read_bytes()
    assert description["input_sha256"] == sha(image)
    assert description["runner_sha256"] == sha((HERE / "run.py").read_bytes())
    encoded = json.dumps(runner.payload(image, prompt, budget), ensure_ascii=False, separators=(",", ":")).encode()
    assert sha(encoded) == description["http_body_sha256"]
    assert record["case"] == case and record["attempts"] == 1
    assert record["http_status"] == 200 and record["finish_reason"] == "stop"
    assert record["returned_model"] == "gpt-6-luna"
    assert sha((out / "response.json").read_bytes()) == record["response_sha256"]
    response = read(out / "response.json")
    assert not response["choices"][0]["message"].get("refusal")
    assert read(out / "output.json") == json.loads(response["choices"][0]["message"]["content"])
    assert record["usage"]["completion_tokens"] < budget

results = read(HERE / "review/results.json")
table = results["cases"]["skillopt-p8"]["evaluation"]
assert table["fixed_numeric_denominator"] == table["source_numeric_bindings_correct"] == 84
assert table["source_numeric_binding_errors"] == table["extra_numeric_observations"] == 0
assert len(table["critical_comparisons"]) == 8 and table["all_critical_numeric_bindings_preserved"]
assert table["panel_header_issues"] == [] and table["duplicate_panels"] == {}
links = 0
for path in [REPO / "docs/research/pdf-core-g2-api-2026-10-14.md", *HERE.rglob("*.md")]:
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if "://" in target or target.startswith("#"):
            continue
        linked = (path.parent / target.split("#")[0]).resolve()
        assert linked.exists() or linked in {HERE / "artifacts.json", HERE / "validation.json"}, (path, target)
        links += 1

files = []
for path in sorted(HERE.rglob("*")):
    if not path.is_file() or "__pycache__" in path.parts or path.name in {"artifacts.json", "validation.json"}:
        continue
    if path.suffix != ".png":
        text = path.read_text()
        assert not re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}", text), "Possible credential; do not print matched content"
    files.append({"path": str(path.relative_to(REPO)), "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())})
save(HERE / "artifacts.json", {"scope": "API probe owned payloads; excludes manifests and ephemeral caches", "files": files})
save(HERE / "validation.json", {"prior_round_payloads_unchanged": prior, "g1_registry_unchanged": True,
     "requests_reconstruct_to_recorded_body_hash": True, "four_source_images_byte_unchanged": True,
     "four_http200_stop_json_results": True, "credential_pattern_scan_clean": True,
     "table_numeric_bindings_correct": 84, "critical_numeric_comparisons": 8,
     "local_markdown_links_checked": links, "payload_files": len(files), "payload_bytes": sum(f["bytes"] for f in files)})
print(json.dumps(read(HERE / "validation.json")))
