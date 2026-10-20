"""Offline six-input integrity check; reuse the prior verifier's pure helpers."""

from collections import Counter
import copy
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
REPO = HERE.parents[3]
HELPERS = REPO / "docs/research/pdf-core-g2-inline-api-2026-10-15/api/verify.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = load("boundary_api_runner", HERE / "run.py")
helpers = load("previous_inline_verification_helpers", HELPERS)
sha, encode, strict_loads = helpers.sha, helpers.encode, helpers.strict_loads


def self_check():
    run.self_check()
    request = run.base.payload(b"self-check-image", "JSON offline self-check", 4096)
    description = copy.deepcopy(request)
    description["messages"][1]["content"][1]["image_url"]["url"] = "IMAGE_BYTES_FROM_input.png"
    assert encode(helpers.restore_body(description, b"self-check-image")) == encode(request)
    assert sha(encode(helpers.restore_body(description, b"changed-image"))) != sha(encode(request))
    assert description["messages"][1]["content"][1]["image_url"]["url"] == "IMAGE_BYTES_FROM_input.png"
    for invalid in ['{"x":1,"x":2}', '{"x":NaN}']:
        try:
            strict_loads(invalid)
        except ValueError:
            continue
        raise AssertionError("Strict JSON accepted duplicate keys or non-JSON numbers")
    Draft202012Validator.check_schema(run.prior.SCHEMA)


def main():
    self_check()
    method = strict_loads((HERE / "method.json").read_text())
    manifest = strict_loads(run.INPUT.read_text())
    assert method["runner_sha256"] == sha((HERE / "run.py").read_bytes())
    assert method["template_path"] == str(run.TEMPLATE.relative_to(REPO))
    assert method["template_sha256"] == sha(run.TEMPLATE.read_bytes())
    assert method["existing_client_path"] == str(run.prior.CLIENT.relative_to(REPO))
    assert method["existing_client_sha256"] == sha(run.prior.CLIENT.read_bytes())
    assert method["input_manifest_sha256"] == sha(run.INPUT.read_bytes())
    assert method["model"] == "gpt-6-luna" and method["endpoint"] == "https://api.openai.com/v1/chat/completions"
    assert method["reasoning_effort"] == "low" and method["temperature_omitted"] and method["store"] is False
    assert method["image_detail"] == "high" and method["automatic_retries"] == 0
    assert method["max_completion_tokens"] == 4096 and method["schema"] == run.prior.SCHEMA
    assert method["http_timeout_seconds"] == 180 and method["connect_timeout_seconds"] == 20
    assert method["shared_lock"] == "/private/tmp/data-ingestion-pdf-qualification.lock"
    assert run.base.COMMON == run.prior.base.COMMON
    audit_path = HERE.parent / "source-audit.json"
    audit = strict_loads(audit_path.read_text())
    assert len(audit["source_files"]) == 20
    for source in audit["source_files"]:
        assert sha((REPO / source["path"]).read_bytes()) == source["sha256"]
    selected = manifest["inputs"]
    assert len(selected) == 6 and Counter(row["phase"] for row in selected) == {"boundary": 6}
    observations_path = HERE / "observations.json"
    observations = strict_loads(observations_path.read_text()) if observations_path.exists() else []
    observed = {row["name"]: row for row in observations}
    jobs = run.jobs()
    assert len(observed) == len(observations) <= len(jobs) == 6
    assert [row["name"] for row in observations] == [job[0] for job in jobs[:len(observations)]]
    validator = Draft202012Validator(run.prior.SCHEMA)
    rows = []
    for item, job in zip(selected, jobs, strict=True):
        name, case, source_path, budget, prompt = job
        assert name == case == item["id"] and source_path == item["image_path"] and budget == 4096
        image_bytes = (REPO / source_path).read_bytes()
        assert sha(image_bytes) == item["image_sha256"]
        with Image.open(REPO / source_path) as image:
            assert image.format == "PNG" and list(image.size) == item["image_pixels_wh"]
        request = run.base.payload(image_bytes, prompt, budget)
        assert request["model"] == "gpt-6-luna" and request["reasoning_effort"] == "low" and request["store"] is False
        assert not {"temperature", "top_p", "logprobs", "top_logprobs", "max_tokens", "tools", "stream"} & request.keys()
        assert request["max_completion_tokens"] == 4096
        assert request["messages"][0] == {"role": "system", "content": run.base.COMMON}
        assert request["messages"][1]["content"][0] == {"type": "text", "text": prompt}
        assert request["messages"][1]["content"][1]["image_url"]["detail"] == "high"
        assert request["response_format"] == {"type": "json_schema", "json_schema": {
            "name": "source_document_blocks", "strict": True, "schema": run.prior.SCHEMA}}
        row = {"id": name, "phase": "boundary", "image_sha256": sha(image_bytes), "budget": budget,
               "status": "not_attempted", "quality_scored_by_this_verifier": False}
        folder = HERE / name
        if not (folder / "request-description.json").exists():
            assert name not in observed
            rows.append(row)
            continue
        assert (folder / "input.png").read_bytes() == image_bytes
        description = strict_loads((folder / "request-description.json").read_text())
        assert description["endpoint"] == method["endpoint"] and description["case"] == case
        assert description["source_input"] == source_path and description["input_sha256"] == sha(image_bytes)
        assert description["runner_sha256"] == method["runner_sha256"]
        assert description["authorization_persisted"] is False and description["image_placeholder_is_not_literal_request"] is True
        restored = helpers.restore_body(description["body_without_inline_image"], image_bytes)
        assert restored == request and sha(encode(restored)) == description["http_body_sha256"]
        row.update(status="prepared_no_response_record", request_body_sha256=description["http_body_sha256"])
        if name not in observed:
            error_path = folder / "transport-error.json"
            if error_path.exists():
                error = strict_loads(error_path.read_text())
                assert isinstance(error["elapsed_seconds"], (int, float)) and error["elapsed_seconds"] >= 0
                row.update(status="transport_error_unscored", transport_error_type=error["type"],
                           client_round_trip_seconds=error["elapsed_seconds"], attempts=1)
            rows.append(row)
            continue
        record = observed[name]
        assert record["case"] == case and record["attempts"] == 1 and type(record["http_status"]) is int
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
        row.update(returned_model=response["model"], requested_model="gpt-6-luna",
                   usage=helpers.validate_usage(response["usage"], budget), finish_reason=choice["finish_reason"],
                   returned_model_identity_matches_requested_family=response["model"] == "gpt-6-luna" or response["model"].startswith("gpt-6-luna-"))
        message = choice["message"]
        if choice["finish_reason"] != "stop" or message.get("refusal") or not message.get("content"):
            row.update(status="incomplete_or_refused_unscored", refusal_present=bool(message.get("refusal")))
        else:
            try:
                output = strict_loads(message["content"])
                validator.validate(output)
            except (ValueError, TypeError, ValidationError) as error:
                row.update(status="output_contract_failure_unscored", contract_error_type=type(error).__name__)
            else:
                assert output == strict_loads((folder / "output.json").read_text())
                row.update(status="completed_contract_valid_unscored", blocks=len(output["blocks"]),
                           segments=sum(len(block["segments"]) for block in output["blocks"]))
        rows.append(row)
    timed = [row["client_round_trip_seconds"] for row in rows if "client_round_trip_seconds" in row]
    usage = [row["usage"] for row in rows if "usage" in row]
    stats = {"selected": len(rows), "attempted": sum(row.get("attempts", 0) for row in rows),
        "client_round_trip_seconds": {"count": len(timed), "sum": sum(timed), "min": min(timed) if timed else None,
            "max": max(timed) if timed else None, "mean": statistics.mean(timed) if timed else None},
        "usage": {**{key: sum(value[key] for value in usage) for key in ["prompt_tokens", "completion_tokens", "total_tokens"]},
            "reasoning_tokens_if_reported": sum(value["reasoning_tokens"] for value in usage if value["reasoning_tokens"] is not None)}}
    result = {"checks": "passed", "scope": "Offline saved request/response integrity and JSON contract only; incomplete results unscored; no semantic approval, API call/retry/key access",
        "timing_resource_interpretation": "HTTP timeout180/connect20 and shared lock; observed RTT only, no separate hard180 wall deadline, local RSS/available-memory observer or remote hardware/cancellation proof",
        "verifier_sha256": sha(Path(__file__).read_bytes()), "reused_verifier_helpers_sha256": sha(HELPERS.read_bytes()),
        "runner_sha256": method["runner_sha256"], "template_sha256": method["template_sha256"],
        "existing_client_sha256": method["existing_client_sha256"], "method_sha256": sha((HERE / "method.json").read_bytes()),
        "input_manifest_sha256": method["input_manifest_sha256"], "source_audit_sha256": sha(audit_path.read_bytes()),
        "source_audit_files_verified": 20, "observations_sha256": sha(observations_path.read_bytes()) if observations_path.exists() else None,
        "selected": 6, "observed_responses": len(observations), "statuses": dict(Counter(row["status"] for row in rows)),
        "all_selected_completed_contract_valid": all(row["status"] == "completed_contract_valid_unscored" for row in rows),
        "phases": {"boundary": stats}, "jobs": rows}
    run.base.save(HERE / "verification.json", result)
    print(json.dumps({"verification_sha256": sha((HERE / "verification.json").read_bytes()),
                      "statuses": result["statuses"], "phases": result["phases"]}))


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-check"]:
        self_check()
        print("Offline payload reconstruction, changed-image hash and strict JSON checks passed; no API call.")
    else:
        assert not sys.argv[1:]
        main()
