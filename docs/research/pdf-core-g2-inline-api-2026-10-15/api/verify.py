"""Offline request/response integrity checks; incomplete output stays unscored."""

import base64
from collections import Counter
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import sys

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from PIL import Image

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("frozen_inline_api_runner", HERE / "run.py")
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
REPO = run.REPO


def sha(value):
    return hashlib.sha256(value).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def strict_loads(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = item
        return result
    def constant(_):
        raise ValueError("Non-JSON numeric constant")
    return json.loads(value, object_pairs_hook=pairs, parse_constant=constant)


def restore_body(description, image):
    body = copy.deepcopy(description)
    assert body["messages"][1]["content"][1]["image_url"]["url"] == "IMAGE_BYTES_FROM_input.png"
    body["messages"][1]["content"][1]["image_url"]["url"] = "data:image/png;base64," + base64.b64encode(image).decode()
    return body


def self_check():
    run.self_check()
    request = run.payload(b"self-check-image", "JSON offline self-check", 4096)
    redacted = copy.deepcopy(request)
    redacted["messages"][1]["content"][1]["image_url"]["url"] = "IMAGE_BYTES_FROM_input.png"
    assert encode(restore_body(redacted, b"self-check-image")) == encode(request)
    assert sha(encode(restore_body(redacted, b"changed-image"))) != sha(encode(request))
    assert redacted["messages"][1]["content"][1]["image_url"]["url"] == "IMAGE_BYTES_FROM_input.png"
    for invalid in ['{"x":1,"x":2}', '{"x":NaN}']:
        try:
            strict_loads(invalid)
        except ValueError:
            continue
        raise AssertionError("Strict JSON accepted duplicate keys or non-JSON numbers")
    Draft202012Validator.check_schema(run.SCHEMA)


def validate_usage(usage, budget):
    assert isinstance(usage, dict)
    values = {key: usage[key] for key in ["prompt_tokens", "completion_tokens", "total_tokens"]}
    assert all(type(value) is int and value >= 0 for value in values.values())
    assert values["prompt_tokens"] + values["completion_tokens"] == values["total_tokens"]
    assert values["completion_tokens"] <= budget
    for category, field, maximum in [("completion_tokens_details", "reasoning_tokens", values["completion_tokens"]),
                                     ("prompt_tokens_details", "cached_tokens", values["prompt_tokens"])]:
        value = (usage.get(category) or {}).get(field)
        assert value is None or (type(value) is int and 0 <= value <= maximum)
        values[field] = value
    return values


def main():
    self_check()
    manifest = strict_loads(run.INPUT.read_text())
    method = strict_loads((HERE / "method.json").read_text())
    assert method["runner_sha256"] == sha((HERE / "run.py").read_bytes())
    assert method["existing_client_sha256"] == sha(run.CLIENT.read_bytes())
    assert method["input_manifest_sha256"] == sha(run.INPUT.read_bytes())
    assert method["model"] == "gpt-6-luna" and method["endpoint"] == "https://api.openai.com/v1/chat/completions"
    assert method["reasoning_effort"] == "low" and method["temperature_omitted"] and method["store"] is False
    assert method["image_detail"] == "high" and method["automatic_retries"] == 0 and method["schema"] == run.SCHEMA
    selected = manifest["inputs"]
    assert Counter(item["phase"] for item in selected) == {"paragraph": 17, "page": 5}
    observations = strict_loads((HERE / "observations.json").read_text()) if (HERE / "observations.json").exists() else []
    observed = {item["name"]: item for item in observations}
    assert len(observed) == len(observations) and len(observations) <= 22
    jobs = run.jobs()
    assert [row["name"] for row in observations] == [job[0] for job in jobs[:len(observations)]]
    validator = Draft202012Validator(run.SCHEMA)
    rows = []
    for item, job in zip(selected, jobs):
        name, case, source_path, budget, prompt = job
        assert name == case == item["id"] and source_path == item["image_path"]
        assert budget == (4096 if item["phase"] == "paragraph" else 8192)
        source_image = (REPO / source_path).read_bytes()
        assert sha(source_image) == item["image_sha256"] == item["cpu_baseline"]["engine_input_image"]["sha256"]
        with Image.open(REPO / source_path) as image:
            assert list(image.size) == item["image_pixels_wh"]
        request = run.payload(source_image, prompt, budget)
        assert request["model"] == "gpt-6-luna" and request["reasoning_effort"] == "low" and request["store"] is False
        assert not {"temperature", "top_p", "logprobs", "top_logprobs", "max_tokens", "tools"} & request.keys()
        assert request["max_completion_tokens"] == budget
        assert "stream" not in request
        assert request["response_format"] == {"type": "json_schema", "json_schema": {"name": "source_document_blocks", "strict": True, "schema": run.SCHEMA}}
        assert request["messages"][1]["content"][1]["image_url"]["detail"] == "high"
        row = {"id": name, "phase": item["phase"], "image_sha256": sha(source_image), "budget": budget,
               "status": "not_attempted", "quality_scored_by_this_verifier": False}
        folder = HERE / name
        if not (folder / "request-description.json").exists():
            assert name not in observed
            rows.append(row)
            continue
        assert (folder / "input.png").read_bytes() == source_image
        description = strict_loads((folder / "request-description.json").read_text())
        assert description["endpoint"] == method["endpoint"] and description["case"] == case
        assert description["source_input"] == source_path and description["input_sha256"] == sha(source_image)
        assert description["runner_sha256"] == method["runner_sha256"]
        assert description["authorization_persisted"] is False and description["image_placeholder_is_not_literal_request"] is True
        restored = restore_body(description["body_without_inline_image"], source_image)
        assert restored == request and sha(encode(restored)) == description["http_body_sha256"]
        row.update(status="prepared_no_response_record", request_body_sha256=description["http_body_sha256"])
        if name not in observed:
            error = folder / "transport-error.json"
            if error.exists():
                transport = strict_loads(error.read_text())
                assert isinstance(transport["elapsed_seconds"], (int, float)) and transport["elapsed_seconds"] >= 0
                row.update(status="transport_error_unscored", transport_error_type=transport["type"],
                           client_round_trip_seconds=transport["elapsed_seconds"], attempts=1)
            rows.append(row)
            continue
        record = observed[name]
        assert record["case"] == case and record["attempts"] == 1
        assert type(record["http_status"]) is int
        elapsed = record["client_round_trip_seconds"]
        assert isinstance(elapsed, (int, float)) and math.isfinite(elapsed) and elapsed >= 0
        assert record["request_id"] is None or isinstance(record["request_id"], str)
        raw = (folder / "response.json").read_bytes()
        assert sha(raw) == record["response_sha256"]
        row.update(http_status=record["http_status"], attempts=1, client_round_trip_seconds=elapsed,
                   observed_round_trip_below_180_seconds=elapsed < 180,
                   request_id=record["request_id"], response_sha256=sha(raw))
        if record["http_status"] != 200:
            row["status"] = "http_error_unscored"
            rows.append(row)
            continue
        response = strict_loads(raw)
        assert isinstance(response["choices"], list) and len(response["choices"]) == 1
        choice = response["choices"][0]
        assert choice["index"] == 0 and isinstance(choice["message"], dict)
        assert record["finish_reason"] == choice["finish_reason"]
        assert record["usage"] == response["usage"] and record["returned_model"] == response["model"]
        assert isinstance(response["model"], str) and response["model"]
        usage = validate_usage(response["usage"], budget)
        row.update(returned_model=response["model"], requested_model="gpt-6-luna", usage=usage,
                   returned_model_identity_matches_requested_family=response["model"] == "gpt-6-luna" or response["model"].startswith("gpt-6-luna-"),
                   finish_reason=choice["finish_reason"])
        message = choice["message"]
        if choice["finish_reason"] != "stop" or message.get("refusal") or not message.get("content"):
            row.update(status="incomplete_or_refused_unscored", refusal_present=bool(message.get("refusal")))
            rows.append(row)
            continue
        try:
            output = strict_loads(message["content"])
            validator.validate(output)
        except (ValueError, TypeError, ValidationError) as error:
            row.update(status="output_contract_failure_unscored", contract_error_type=type(error).__name__)
        else:
            saved = strict_loads((folder / "output.json").read_text())
            assert output == saved
            row.update(status="completed_contract_valid_unscored", blocks=len(output["blocks"]),
                       segments=sum(len(block["segments"]) for block in output["blocks"]))
        rows.append(row)
    phases = {}
    for phase in ["paragraph", "page"]:
        values = [row for row in rows if row["phase"] == phase]
        timed = [row["client_round_trip_seconds"] for row in values if "client_round_trip_seconds" in row]
        usages = [row["usage"] for row in values if "usage" in row]
        phases[phase] = {"selected": len(values), "attempted": sum(row.get("attempts", 0) for row in values),
            "statuses": dict(Counter(row["status"] for row in values)),
            "client_round_trip_seconds": {"count": len(timed), "sum": sum(timed), "min": min(timed) if timed else None,
                "max": max(timed) if timed else None, "mean": statistics.mean(timed) if timed else None},
            "usage": {**{key: sum(u[key] for u in usages) for key in ["prompt_tokens", "completion_tokens", "total_tokens"]},
                      "reasoning_tokens_if_reported": sum(u["reasoning_tokens"] for u in usages if u["reasoning_tokens"] is not None),
                      "reasoning_tokens_reported_count": sum(u["reasoning_tokens"] is not None for u in usages)}}
    result = {"checks": "passed", "scope": "Offline saved request/response integrity and output-contract checks only; no source semantic quality verdict, no API call/retry/key access",
        "timing_resource_interpretation": "HTTP client timeout180/connect20 and shared lock only; elapsed is observed RTT, no separate hard180 wall deadline, no local RSS/available-memory monitoring or remote hardware/cancellation evidence",
        "verifier_sha256": sha(Path(__file__).read_bytes()), "runner_sha256": method["runner_sha256"],
        "method_sha256": sha((HERE / "method.json").read_bytes()), "input_manifest_sha256": method["input_manifest_sha256"],
        "observations_sha256": sha((HERE / "observations.json").read_bytes()) if observations else None,
        "selected": 22, "observed_responses": len(observations),
        "all_selected_completed_contract_valid": all(row["status"] == "completed_contract_valid_unscored" for row in rows),
        "statuses": dict(Counter(row["status"] for row in rows)), "phases": phases, "jobs": rows}
    run.base.save(HERE / "verification.json", result)
    print(json.dumps({"verification_sha256": sha((HERE / "verification.json").read_bytes()),
                      "statuses": result["statuses"], "phases": phases}))


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-check"]:
        self_check()
        print("Offline payload reconstruction, changed-image hash and strict JSON checks passed; no API call.")
    else:
        assert not sys.argv[1:]
        main()
