"""DEV request/envelope adapter. No network or credential access."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
R1 = HERE.parent
ROOT = R1.parents[2]
sys.path.insert(0, str(R1))
import method as m
import assemble

MODEL = "gpt-6.1-sol"
ENDPOINT = "https://api.openai.com/v1/chat/completions"


def read(path):
    return json.loads(Path(path).read_text())


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def contract(task):
    common = {"job_id": "exact supplied job_id", "group_sha256": "exact supplied group_sha256",
        "context_key": "exact supplied context_key", "status": "complete|incomplete",
        "incomplete_reason": "null for complete; nonempty string for incomplete", "payload": "see below"}
    if task == "source_reconstruction":
        payload = {"group_sha256": "same supplied group_sha256", "keep": ["every unconsumed text candidate"],
            "actions": [{"id": "unique string", "consume": ["exact text refs"],
                "evidence_refs": ["exact native refs or supplied @page refs"], "source_pages": ["integer physical page"],
                "placement": {"reference": "supplied visible_anchor", "side": "before|after"},
                "blocks": [{"kind": "paragraph|heading|formula|code", "segments": [
                    {"kind": "text|math|code", "text": "faithful source text; LaTeX for math"}]}]}]}
    elif task == "description_with_context_OCR":
        payload = {"images": {"each exact image_key": {"description": m.image_types.Description.model_json_schema(),
            "context_ocr": {"scope": "page_context", "text": "outside-crop source text or empty", "status": "ok|no_text|unreadable"}}}}
    elif task == "chart_assessment":
        payload = {"images": {"each exact image_key": m.image_types.Chart.model_json_schema()}}
    else:
        raise ValueError("unknown task")
    common["payload"] = payload
    return common


def materialize(job):
    bound = job["binding"]
    raw = read(ROOT / job["baseline"])
    scope = {"job_id": job["job_id"], "group_sha256": m.digest(bound),
        "context_key": bound["context_key"], "scope": bound,
        "native_text_candidates": [{k: x.get(k) for k in ("self_ref", "parent", "label", "text", "prov")}
            for x in raw["texts"] if x["self_ref"] in bound["text_candidates"]]}
    instruction = job["instruction"] + "\nReturn exactly one JSON object conforming to this response contract. "
    instruction += "Do not correct source facts, infer unreadable content, or put descriptions in source Markdown. "
    instruction += "An incomplete response has payload=null and an explicit reason.\n" + json.dumps(contract(job["task"]), ensure_ascii=False)
    content = [{"type": "text", "text": json.dumps(scope, ensure_ascii=False)}]
    for asset in job["image_assets"]:
        path = (R1 / "production" / asset["asset"]).resolve()
        if not path.is_relative_to(R1 / "production"):
            raise ValueError("asset escaped production")
        data = path.read_bytes()
        if sha(data) != asset["sha256"]:
            raise ValueError("changed source pixels")
        content.append({"type": "image_url", "image_url": {
            "url": "data:image/png;base64," + base64.b64encode(data).decode(), "detail": "high"}})
    body = {"model": MODEL, "store": False, "reasoning_effort": "low",
        "max_completion_tokens": job["per_job_completion_cap_proposal"],
        "response_format": {"type": "json_object"}, "messages": [
            {"role": "system", "content": instruction}, {"role": "user", "content": content}]}
    return body


def validate_payload(job, value):
    bound = job["binding"]
    if set(value) != {"job_id", "group_sha256", "context_key", "status", "incomplete_reason", "payload"}:
        raise ValueError("envelope fields")
    if (value["job_id"] != job["job_id"] or value["group_sha256"] != m.digest(bound)
            or value["context_key"] != bound["context_key"]):
        raise ValueError("foreign response binding")
    if value["status"] == "incomplete":
        if value["payload"] is not None or not isinstance(value["incomplete_reason"], str) or not value["incomplete_reason"].strip():
            raise ValueError("incomplete response must give reason and no payload")
        raise ValueError("source incomplete: " + value["incomplete_reason"][:120])
    if value["status"] != "complete" or value["incomplete_reason"] is not None:
        raise ValueError("invalid completion state")
    payload = value["payload"]
    if job["task"] == "source_reconstruction":
        validate_source_types(payload)
        m.apply(read(ROOT / job["baseline"]), bound, payload)
    else:
        expected = {x["image_key"] for x in bound["images"]}
        if set(payload) != {"images"} or set(payload["images"]) != expected:
            raise ValueError("missing/foreign image result")
        for observation in payload["images"].values():
            if job["task"] == "chart_assessment":
                m.image_types.Chart.model_validate(observation)
            else:
                if set(observation) != {"description", "context_ocr"}:
                    raise ValueError("description lane fields")
                parsed = m.image_types.Description.model_validate(observation["description"])
                if not parsed.description.strip():
                    raise ValueError("blank description")
                ocr = observation["context_ocr"]
                if (set(ocr) != {"scope", "text", "status"} or ocr["scope"] != "page_context"
                        or not isinstance(ocr["text"], str) or ocr["status"] not in {"ok", "no_text", "unreadable"}
                        or (ocr["status"] == "ok" and not ocr["text"].strip())
                        or (ocr["status"] == "no_text" and ocr["text"])):
                    raise ValueError("invalid context OCR")
    return payload


def validate_source_types(payload):
    def strings(value):
        return isinstance(value, list) and all(isinstance(x, str) for x in value)
    if (not isinstance(payload, dict) or set(payload) != {"group_sha256", "keep", "actions"}
            or not isinstance(payload["group_sha256"], str) or not strings(payload["keep"])
            or not isinstance(payload["actions"], list)):
        raise ValueError("source response types")
    for action in payload["actions"]:
        if (not isinstance(action, dict) or set(action) != {"id","consume","evidence_refs","source_pages","placement","blocks"}
                or not isinstance(action["id"], str) or not action["id"].strip()
                or not strings(action["consume"]) or not strings(action["evidence_refs"])
                or not isinstance(action["source_pages"], list)
                or any(type(x) is not int for x in action["source_pages"])
                or not isinstance(action["placement"], dict)
                or not isinstance(action["blocks"], list)):
            raise ValueError("source action types")
        for block in action["blocks"]:
            if (not isinstance(block, dict) or set(block) != {"kind","segments"}
                    or block["kind"] not in {"paragraph","heading","formula","code"}
                    or not isinstance(block["segments"], list)):
                raise ValueError("source block types")
            for segment in block["segments"]:
                if (not isinstance(segment, dict) or set(segment) != {"kind","text"}
                        or segment["kind"] not in {"text","math","code"}
                        or not isinstance(segment["text"], str)):
                    raise ValueError("source segment types")


def mock_payload(job):
    b = job["binding"]
    if job["task"] == "source_reconstruction":
        payload = {"group_sha256": m.digest(b), "keep": b["text_candidates"], "actions": []}
    elif job["task"] == "description_with_context_OCR":
        payload = {"images": {x["image_key"]: {"description": {"image_kind": "MOCK_NOT_ASSESSED",
            "description": "MOCK transport only; not source evidence", "visible_text": [], "components": [],
            "relations": [], "ordered_steps": [], "uncertainties": ["MOCK: semantic QA not performed"]},
            "context_ocr": {"scope": "page_context", "text": "", "status": "unreadable"}} for x in b["images"]}}
    else:
        payload = {"images": {x["image_key"]: {"chart_type": "unknown", "unit": None, "data": [],
            "uncertainties": ["MOCK: chart assessment not performed"]} for x in b["images"]}}
    return {"job_id": job["job_id"], "group_sha256": m.digest(b), "context_key": b["context_key"],
        "status": "complete", "incomplete_reason": None, "payload": deepcopy(payload)}
