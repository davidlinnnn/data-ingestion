"""Read-only checks of frozen native input interfaces; never runs providers."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


for name, digest in read(ROOT / "artifact-hashes.json").items():
    assert sha(ROOT / name) == digest, name
for path, digest in read(ROOT / "referenced-hashes.json").items():
    assert sha(path) == digest, path
spec = importlib.util.spec_from_file_location("frozen_native_C_producer", ROOT / "producer.py")
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)
inventory = read(ROOT / "producer-inventory.json")
custody = read(ROOT / "producer-custody-v1.json")
assert sha(ROOT / "producer-inventory.json") == custody["files"]["producer-inventory.json"]
assert len(inventory["pictures"]) == 29 and not inventory["range_errors"]
pages = [(r["source"]["sha256"], p) for r in inventory["ranges"] for p in r["pages"]]
assert len(pages) == len(set(pages)) == 55
for r in inventory["ranges"]:
    assert sha(r["source"]["path"]) == r["source"]["sha256"]
    assert sha(r["baseline"]) == r["baseline_sha256"]
docs = {}
for image in inventory["pictures"]:
    assert image["status"] == "input_ready" and sha(image["crop"]) == image["crop_sha256"]
    assert image["image_key"] == producer.digest([image["document_revision"], image["owner_ref"], image["crop_sha256"]])
    if image["baseline"] not in docs:
        docs[image["baseline"]] = producer.DoclingDocument.load_from_json(image["baseline"])
    doc = docs[image["baseline"]]
    picture = next(p for p in doc.pictures if p.self_ref == image["owner_ref"])
    assert producer.seam.native_mapping(doc, picture) == image["mapping"]
requests = read(ROOT / "requests.json")
assert len(requests["jobs"]) == 58 and len(requests["local_OCR_jobs"]) == 29
assert requests["remote_execution_ready"] is False and requests["live_run_budget_enforcement_ready"] is False
assert requests["endpoint"] == "https://api.openai.com/v1/chat/completions"
assert len({j["job_id"] for j in requests["jobs"]}) == 58
for job in requests["jobs"]:
    raw = producer.materialize(job)
    assert hashlib.sha256(raw).hexdigest() == job["request_sha256"]
    assert len(raw) == job["materialized_request_bytes"] <= job["request_bytes_max"]
    assert job["body_without_image"]["max_completion_tokens"] == job["output_tokens_cap"] == 6144
assert sum(j["input_tokens_reserve"] for j in requests["jobs"]) == requests["input_tokens_reserve_total"]
assert sum(j["output_tokens_cap"] for j in requests["jobs"]) == requests["completion_tokens_cap_total"]
controls = producer.self_check(requests["jobs"])
assert len(controls["negative_controls_rejected"]) == 15
coverage = read(ROOT / "source-coverage.json")
assert coverage["source_groups_matched"] == len(coverage["groups"]) == 19
assert coverage["material_input_partial_groups"] == coverage["material_caption_failure_groups"] == 1
assert coverage["full_C_coverage_gate"] == "blocked" and coverage["N_3_complete_profile"] is None
assert read(ROOT / "cpu-output-validation.json")["completed_CPU_pages"] == 44
assert read(ROOT / "cpu-execution.json")["status"] == "parent_harness_error"
for r in inventory["ranges"]:
    folder = ROOT / "bundles" / r["range_id"]
    doc = producer.DoclingDocument.load_from_json(folder / "document.json")
    assert producer.seam.markdown(doc).encode() == (folder / "document.md").read_bytes()
    sidecar = read(folder / "supplement.json")
    assert sidecar["provider_results"] == [] and sidecar["acceptance"] == "unattempted_not_accepted"
assert "torch" not in sys.modules and "onnxruntime" not in sys.modules
print(json.dumps({"status": "read_only_C_interface_checks_passed", "pages": 55, "native_crops": 29,
    "candidate_remote_requests": 58, "local_OCR_jobs": 29, "source_groups_matched": 19,
    "material_source_blocks": 2, "negative_controls": 15, "model_API_calls_by_check": 0,
    "remote_execution_ready": False, "full_C": "blocked", "N_3": None}))
