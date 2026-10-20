"""Six new context inputs; reuse the previous strict-segment API client unchanged."""

import fcntl
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TEMPLATE = REPO / "docs/research/pdf-core-g2-inline-api-2026-10-15/api/run.py"
spec = importlib.util.spec_from_file_location("previous_inline_api", TEMPLATE)
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
base = prior.base
INPUT = HERE.parent / "inputs/input-manifest.json"
base.HERE = HERE


def jobs():
    rows = json.loads(INPUT.read_text())["inputs"]
    result = []
    for row in rows:
        width, height = row["image_pixels_wh"]
        prompt = (
            f"Image size: {width} by {height} pixels. Transcribe the complete visible source context. "
            "The image may assemble source fragments in reading order with white gaps. "
            "Keep logical paragraph/code/formula boundaries; a visual line wrap or white stitch gap alone is not a new paragraph. "
            "Do not repeat fragments or absorb an unrelated caption/sidebar into prose. "
            "Include all visible blocks, including neighboring context, exactly once; the caller will associate them separately. "
            "Use blocks with kind, bbox [left,top,right,bottom], ordered segments {kind,text}, code_language, and root uncertainties. "
            "Standalone formulas have kind formula and math segments. Keep inline math and code within their prose block."
        )
        result.append((row["id"], row["id"], row["image_path"], 4096, prompt))
    return result


def self_check():
    rows = json.loads(INPUT.read_text())["inputs"]
    assert len(rows) == 6 and len({r["id"] for r in rows}) == 6
    for row in rows:
        assert base.sha((REPO / row["image_path"]).read_bytes()) == row["image_sha256"]
    request = base.payload(b"test", "JSON test", 32)
    assert request["model"] == "gpt-6-luna" and request["reasoning_effort"] == "low"
    assert "temperature" not in request and request["store"] is False
    assert request["response_format"]["json_schema"]["strict"]
    assert "Authorization" not in json.dumps(request)
    assert base.ENDPOINT == "https://api.openai.com/v1/chat/completions"


base.self_check = self_check
base.__file__ = str(Path(__file__).resolve())
if __name__ == "__main__":
    self_check()
    if sys.argv[1:] == ["--self-check"]:
        print("Six context-input requests verified offline; no API call")
    else:
        assert sys.argv[1:] == []
        base.JOBS = jobs()
        base.save(HERE / "method.json", {"method": "Six new context images, direct API component; no official pipeline or production acceptance",
            "template_path": str(TEMPLATE.relative_to(REPO)), "template_sha256": base.sha(TEMPLATE.read_bytes()),
            "existing_client_path": str(prior.CLIENT.relative_to(REPO)), "existing_client_sha256": base.sha(prior.CLIENT.read_bytes()),
            "runner_sha256": base.sha(Path(__file__).read_bytes()), "input_manifest_sha256": base.sha(INPUT.read_bytes()),
            "model": base.MODEL, "endpoint": base.ENDPOINT, "reasoning_effort": "low", "temperature_omitted": True,
            "image_detail": "high", "max_completion_tokens": 4096, "store": False, "automatic_retries": 0,
            "http_timeout_seconds": 180, "connect_timeout_seconds": 20, "shared_lock": "/private/tmp/data-ingestion-pdf-qualification.lock",
            "changed_from_previous_method": "New producer-derived source context and generic context prompt; schema/system prompt/model/settings reused",
            "model_input_has_oracle_answers": False, "schema": prior.SCHEMA})
        with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            base.main()
