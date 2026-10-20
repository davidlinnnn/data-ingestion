"""Independently bind each saved API exchange to the unchanged prepared request."""

import ast
import base64
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[2]
CANDIDATE = REPO / "docs/research/pdf-core-g2-context-candidate-2026-10-15"
MANIFEST = CANDIDATE / "input-manifest.json"
PARSER = REPO / "docs/research/pdf-core-g2-inline-api-2026-10-15/parsed/parse.py"
SCHEMA_METHOD = REPO / "docs/research/pdf-core-g2-inline-api-2026-10-15/api/method.json"
SYSTEM_RUNNER = REPO / "docs/research/pdf-core-g2-api-2026-10-14/run.py"
FROZEN = {
    MANIFEST: "3185cd4af958f49368419d202f1ec3fe2805b93672b3d0565c1fe28108e1378c",
    CANDIDATE / "adapter.py": "5d8eff53e4912e45f149e617958f0ac7caa5114fe13286d5c6e7c86d046f3272",
    PARSER: "bc4055773619576732a0c5ce51592c6e322c9c732611a701e8cdb7101300ce24",
    SCHEMA_METHOD: "d7457d9ea07d72c7a0413dadbdc7da3e7c912fd841e78e805275f031dac33eab",
    SYSTEM_RUNNER: "bc218bf3ebb0e15a3cfeea589ea1b0011140e1c43590d1053a15390b77e58e20",
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def loads(text):
    return json.loads(text, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON: " + value)))


def read(path):
    return loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def ref(path):
    return {"path": str(path.relative_to(REPO)), "sha256": sha(path)}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def checked(reference):
    path = REPO / reference["path"]
    if not path.resolve().is_relative_to(REPO) or "holdout" in str(path).lower():
        raise ValueError("reference outside the allowed exposed-source evidence")
    if sha(path) != reference["sha256"]:
        raise ValueError("changed frozen reference: " + reference["path"])
    return path


def system_message():
    tree = ast.parse(SYSTEM_RUNNER.read_text())
    return next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "COMMON"
                    for t in node.targets))


def expected_body(row, contract, image):
    return {"model": "gpt-6-luna", "store": False, "reasoning_effort": "low", "max_completion_tokens": 4096,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "source_document_blocks", "strict": True, "schema": read(SCHEMA_METHOD)["schema"]}},
            "messages": [{"role": "system", "content": system_message()},
                {"role": "user", "content": [{"type": "text", "text": contract["prompt"]},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(image).decode(),
                                                          "detail": "high"}}]}]}


def inputs():
    hashes = {}
    for path, expected in FROZEN.items():
        assert sha(path) == expected, path
        hashes[str(path.relative_to(REPO))] = expected
    hashes[str((HERE / "run.py").relative_to(REPO))] = sha(HERE / "run.py")
    manifest = read(MANIFEST)
    rows = manifest["inputs"]
    assert len(rows) == manifest["prepared_jobs"] == 36
    assert len({(r["source"], r["job_id"]) for r in rows}) == 36

    def references(value):
        if isinstance(value, dict):
            if "path" in value and "sha256" in value:
                path = checked(value)
                hashes[str(path.relative_to(REPO))] = value["sha256"]
            for child in value.values():
                references(child)
        elif isinstance(value, list):
            for child in value:
                references(child)

    references(manifest)
    for row in rows:
        contract = read(checked(row["request_contract_ref"]))
        references(contract)
        without_hash = dict(contract)
        assert without_hash.pop("input_contract_sha256") == digest(without_hash)
        assert contract["status"] == "prepared_not_sent"
        assert contract["image_ref"] == row["image_ref"]
        assert contract["image_pixels_wh"] == row["image_pixels_wh"]
        assert hashlib.sha256(contract["prompt"].encode()).hexdigest() == contract["prompt_sha256"]
        assert contract["provisional_model"] == "gpt-6-luna" and contract["reasoning_effort"] == "low"
        assert contract["image_detail"] == "high" and contract["max_completion_tokens"] == 4096
        assert contract["store"] is False and contract["automatic_retries"] == 0
        assert contract["changed_prompt_or_context_requires_new_inference"] is True
        raw = read(checked(row["provider_document_ref"]))
        by_ref = {i["self_ref"]: i for key in ("texts", "pictures", "tables", "groups", "key_value_items", "form_items")
                  for i in raw.get(key, [])}
        expected_scope = {"document_canonical_sha256": digest(raw),
            **{key: row[key] for key in ("target_item_refs", "context_only_refs", "member_item_refs")},
            "item_hashes": {r: digest(by_ref[r]) for r in row["target_item_refs"] + row["context_only_refs"] + row["member_item_refs"]}}
        assert contract["scope"] == expected_scope
        assert len(row["target_item_refs"]) == 1
        assert not set(row["target_item_refs"]) & set(row["context_only_refs"])
    existing = ROOT / "parsed/frozen-input-hashes.json"
    ledger = {"format": "g2-context-fixed-input-hashes-v1", "files": hashes,
              "input_count": 36, "holdout_reads": 0}
    if existing.exists():
        assert read(existing) == ledger, "fixed input identities changed"
    else:
        save(existing, ledger)
    return rows


def verify_exchange(row, observation):
    folder = HERE / row["source"] / row["job_id"]
    contract = read(checked(row["request_contract_ref"]))
    description_path = folder / "request-description.json"
    description = read(description_path)
    image = (folder / "input.png").read_bytes()
    assert hashlib.sha256(image).hexdigest() == row["image_ref"]["sha256"]
    assert image == checked(row["image_ref"]).read_bytes()
    assert description["endpoint"] == "https://api.openai.com/v1/chat/completions"
    assert description["source_input"] == row["image_ref"]["path"]
    assert description["input_sha256"] == row["image_ref"]["sha256"]
    assert description["authorization_persisted"] is False
    assert description["image_placeholder_is_not_literal_request"] is True
    assert description["runner_sha256"] == sha(HERE / "run.py")
    assert description["case"] in (row["job_id"], row["source"] + "/" + row["job_id"])
    for key, expected in (("source", row["source"]), ("job_id", row["job_id"]),
                          ("request_contract_ref", row["request_contract_ref"]),
                          ("frozen_manifest_row_sha256", digest(row)),
                          ("parent_manifest_sha256", sha(MANIFEST))):
        assert description[key] == expected
    body = deepcopy(description["body_without_inline_image"])
    assert body["messages"][1]["content"][1]["image_url"]["url"] == "IMAGE_BYTES_FROM_input.png"
    body["messages"][1]["content"][1]["image_url"]["url"] = "data:image/png;base64," + base64.b64encode(image).decode()
    assert body == expected_body(row, contract, image), "saved request differs from the full frozen prompt/schema/settings"
    encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    assert hashlib.sha256(encoded).hexdigest() == description["http_body_sha256"], "reconstructed HTTP bytes differ"
    response_path, output_path = folder / "response.json", folder / "output.json"
    response, output = read(response_path), read(output_path)
    assert observation["case"] == row["job_id"]
    assert observation["name"] == row["source"] + "/" + row["job_id"]
    assert observation["http_status"] == 200 and observation["attempts"] == 1
    assert observation["response_sha256"] == sha(response_path)
    assert observation["credential_redaction_applied"] is False
    elapsed = observation["client_round_trip_seconds"]
    assert isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool) and math.isfinite(elapsed) and elapsed > 0
    assert isinstance(observation["request_id"], str) and observation["request_id"]
    assert isinstance(response["id"], str) and response["id"]
    assert response["model"] == observation["returned_model"] and response["model"].startswith("gpt-6-luna")
    assert len(response["choices"]) == 1
    choice = response["choices"][0]
    assert choice["finish_reason"] == observation["finish_reason"] == "stop"
    assert choice["message"]["role"] == "assistant" and not choice["message"].get("refusal")
    assert loads(choice["message"]["content"]) == output
    usage = response["usage"]
    assert usage == observation["usage"]
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        assert type(usage[key]) is int and usage[key] > 0
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]
    for key, ceiling in (("prompt_tokens_details", usage["prompt_tokens"]), ("completion_tokens_details", usage["completion_tokens"])):
        for value in usage.get(key, {}).values():
            assert value is None or type(value) is int and 0 <= value <= ceiling
    return {"source": row["source"], "job_id": row["job_id"], "request_id": observation["request_id"],
            "response_id": response["id"], "http_body_sha256": description["http_body_sha256"],
            "request_description_ref": ref(description_path), "request_contract_ref": row["request_contract_ref"],
            "response_ref": ref(response_path), "output_ref": ref(output_path), "image_ref": ref(folder / "input.png"),
            "manifest_row_sha256": digest(row), "usage": usage, "elapsed_seconds": elapsed,
            "exact_frozen_request_verified": True, "raw_message_matches_saved_output": True}


def verify_all():
    rows = inputs()
    method = read(HERE / "method.json")
    assert method["system_prompt"] == system_message() and method["schema"] == read(SCHEMA_METHOD)["schema"]
    assert checked(method["client_ref"]) == SYSTEM_RUNNER
    assert checked(method["runner_ref"]) == HERE / "run.py"
    assert checked(method["input_manifest_ref"]) == MANIFEST
    assert checked(method["schema_ref"]) == SCHEMA_METHOD
    assert method["model"] == "gpt-6-luna" and method["reasoning_effort"] == "low" and method["image_detail"] == "high"
    assert method["max_completion_tokens"] == 4096 and method["store"] is False and method["temperature_omitted"] is True
    assert method["attempts_per_input"] == 1 and method["automatic_retries"] == 0 and method["sequential"] is True
    observations = read(HERE / "observations.json")
    assert len(observations) == 36
    records = [verify_exchange(row, observation) for row, observation in zip(rows, observations, strict=True)]
    assert len({r["request_id"] for r in records}) == len({r["response_id"] for r in records}) == 36
    report = {"format": "g2-context-exact-api-verification-v1", "passed": True,
              "verifier_ref": ref(Path(__file__)), "input_manifest_ref": ref(MANIFEST),
              "frozen_input_hashes_ref": ref(ROOT / "parsed/frozen-input-hashes.json"),
              "observations_ref": ref(HERE / "observations.json"), "verified_exchanges": len(records),
              "all_http_bodies_reconstructed": True, "all_raw_messages_match_saved_outputs": True,
              "unique_request_ids": True, "unique_response_ids": True,
              "semantic_quality_assessed": False, "holdout_reads": 0, "records": records}
    save(HERE / "verification.json", report)
    return rows, records


if __name__ == "__main__":
    if sys.argv[1:] == ["--inputs-only"]:
        print(json.dumps({"fixed_inputs_checked": len(inputs()), "new_outputs_read": 0}))
    else:
        assert not sys.argv[1:]
        print(json.dumps({"verified_exchanges": len(verify_all()[1]), "semantic_quality_assessed": False}))
