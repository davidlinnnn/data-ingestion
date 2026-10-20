"""Run the36 frozen development requests using the existing memory-only client."""
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FROZEN = REPO / "docs/research/pdf-core-g2-context-candidate-2026-10-15"
CLIENT = REPO / "docs/research/pdf-core-g2-api-2026-10-14/run.py"
MANIFEST = FROZEN / "input-manifest.json"
spec = importlib.util.spec_from_file_location("frozen_memory_only_api_client", CLIENT)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
original_payload, original_save = base.payload, base.save
rows = json.loads(MANIFEST.read_text())["inputs"]
by_folder = {r["source"] + "/" + r["job_id"]: r for r in rows}
schema_path = REPO / "docs/research/pdf-core-g2-inline-api-2026-10-15/api/method.json"
SCHEMA = json.loads(schema_path.read_text())["schema"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def payload(image, prompt, budget):
    request = original_payload(image, prompt, budget)
    request["response_format"] = {"type": "json_schema", "json_schema": {
        "name": "source_document_blocks", "strict": True, "schema": SCHEMA}}
    return request


def save(path, value):
    if path.name == "request-description.json":
        row = by_folder[str(path.parent.relative_to(HERE))]
        value = {**value, "source": row["source"], "job_id": row["job_id"],
                 "request_contract_ref": row["request_contract_ref"],
                 "frozen_manifest_row_sha256": digest(row),
                 "parent_manifest_sha256": sha(MANIFEST)}
    original_save(path, value)


def jobs():
    result = []
    for name, row in by_folder.items():
        contract_path = REPO / row["request_contract_ref"]["path"]
        assert sha(contract_path) == row["request_contract_ref"]["sha256"]
        contract = json.loads(contract_path.read_text())
        result.append((name, row["job_id"], row["image_ref"]["path"],
                       contract["max_completion_tokens"], contract["prompt"]))
    return result


def self_check():
    assert len(rows) == len(by_folder) == 36
    assert sha(CLIENT) == "bc218bf3ebb0e15a3cfeea589ea1b0011140e1c43590d1053a15390b77e58e20"
    assert sha(schema_path) == "d7457d9ea07d72c7a0413dadbdc7da3e7c912fd841e78e805275f031dac33eab"
    for row in rows:
        assert sha(REPO / row["image_ref"]["path"]) == row["image_ref"]["sha256"]
        contract = json.loads((REPO / row["request_contract_ref"]["path"]).read_text())
        assert contract["provisional_model"] == base.MODEL == "gpt-6-luna"
        assert contract["image_detail"] == "high" and contract["reasoning_effort"] == "low"
        assert contract["max_completion_tokens"] == 4096 and not contract["automatic_retries"]
        assert contract["store"] is False
    request = payload(b"test", "JSON test", 32)
    assert request["response_format"]["json_schema"]["strict"]
    assert request["model"] == "gpt-6-luna" and request["store"] is False
    assert request["reasoning_effort"] == "low" and "temperature" not in request
    assert "Authorization" not in json.dumps(request)
    assert base.ENDPOINT == "https://api.openai.com/v1/chat/completions"


base.HERE = HERE
base.payload = payload
base.save = save
base.self_check = self_check
base.__file__ = str(Path(__file__).resolve())
if __name__ == "__main__":
    self_check()
    if sys.argv[1:] == ["--self-check"]:
        print("36 exact frozen input/prompt/schema requests verified offline; no API call")
    else:
        assert sys.argv[1:] == []
        assert not (HERE / "method.json").exists(), "Frozen development run is one-attempt; do not rerun"
        for source in sorted({r["source"] for r in rows}):
            (HERE / source).mkdir(exist_ok=False)
        base.JOBS = jobs()
        save(HERE / "method.json", {"scope": "Candidate1 direct API component on36 frozen exposed development inputs; no official VlmPipeline/holdout",
            "client_ref": {"path": str(CLIENT.relative_to(REPO)), "sha256": sha(CLIENT)},
            "runner_ref": {"path": str(Path(__file__).resolve().relative_to(REPO)), "sha256": sha(Path(__file__))},
            "input_manifest_ref": {"path": str(MANIFEST.relative_to(REPO)), "sha256": sha(MANIFEST)},
            "schema_ref": {"path": str(schema_path.relative_to(REPO)), "sha256": sha(schema_path)},
            "system_prompt": base.COMMON, "schema": SCHEMA, "model": base.MODEL,
            "endpoint": base.ENDPOINT, "reasoning_effort": "low", "image_detail": "high",
            "max_completion_tokens": 4096, "store": False, "temperature_omitted": True,
            "attempts_per_input": 1, "automatic_retries": 0, "sequential": True,
            "http_timeout_seconds": 180, "connect_timeout_seconds": 20,
            "fail_fast": "The unchanged client stops on transport/non200/incomplete result; all unattempted jobs remain named missing outcomes",
            "shared_lock": "/private/tmp/data-ingestion-pdf-qualification.lock",
            "credentials": "Process memory only via hidden getpass; never persisted",
            "official_reference": "https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create"})
        with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            base.main()
