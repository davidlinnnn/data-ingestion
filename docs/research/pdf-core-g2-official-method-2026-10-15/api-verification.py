"""Independently verify saved exchanges and replay stock assembly offline.

Never reads credentials or holdout PDF bytes. No HTTP is permitted during replay.
"""
import ast
import base64
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime
import hashlib
from importlib.metadata import version
import inspect
from io import BytesIO
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import patch
import warnings

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from PIL import Image
import requests
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
from docling.datamodel.pipeline_options_vlm_model import ResponseFormat
from docling.datamodel.stage_model_specs import VlmModelSpec
from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.models.inference_engines.vlm.api_openai_compatible_engine import ApiVlmEngine
from docling.pipeline.vlm_pipeline import VlmPipeline

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MODEL = "gpt-6-luna"
ENDPOINT = "https://api.openai.com/v1/chat/completions"
HOLDOUT = "docs/fixtures/pdf-core-g2-holdout-2026-10-15/"


def sha(path):
    assert not (str(path.relative_to(REPO)).startswith(HOLDOUT) and path.suffix == ".pdf") if path.is_relative_to(REPO) else True
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def request_body(payload):
    return requests.Request("POST", ENDPOINT, json=payload).prepare().body


def differences(left, right, path=""):
    if isinstance(left, dict) and isinstance(right, dict) and left.keys() == right.keys():
        return [d for key in left for d in differences(left[key], right[key], path + "/" + str(key))]
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [d for i, (a, b) in enumerate(zip(left, right)) for d in differences(a, b, path + "/" + str(i))]
    return [] if left == right else [{"path": path, "stored_official": left, "replayed_persisted_response": right}]


def legacy_redact(text):
    # Explain the frozen observer's known overbroad redaction; never repair files.
    return re.sub(r"sk-(?:proj-)?[A-Za-z0-9_.*-]{6,}", "[REDACTED]", text)


def verify_payload(saved, image_bytes, prompt):
    payload = deepcopy(saved["body_without_inline_image"])
    image = payload["messages"][0]["content"][0]["image_url"]
    assert image == {"url": "IMAGE_BYTES_FROM_input.png"}
    image["url"] = "data:image/png;base64," + base64.b64encode(image_bytes).decode()
    expected = {"messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": image}, {"type": "text", "text": prompt}]}],
        "temperature": None, "model": MODEL, "max_completion_tokens": 8192,
        "reasoning_effort": "low", "store": False}
    assert payload == expected
    assert hashlib.sha256(request_body(payload)).hexdigest() == saved["http_body_sha256"]
    assert hashlib.sha256(image_bytes).hexdigest() == saved["input_sha256"]
    assert saved["authorization_persisted"] is False
    return payload


def selfcheck(prompt):
    image = b"synthetic bytes for request verifier only"
    payload = {"messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(image).decode()}},
        {"type": "text", "text": prompt}]}],
        "temperature": None, "model": MODEL, "max_completion_tokens": 8192,
        "reasoning_effort": "low", "store": False}
    saved = {"body_without_inline_image": deepcopy(payload),
             "http_body_sha256": hashlib.sha256(request_body(payload)).hexdigest(),
             "input_sha256": hashlib.sha256(image).hexdigest(), "authorization_persisted": False}
    saved["body_without_inline_image"]["messages"][0]["content"][0]["image_url"]["url"] = "IMAGE_BYTES_FROM_input.png"
    assert verify_payload(saved, image, prompt) == payload
    rejected = []
    for name in ["model", "prompt", "body_hash", "image_bytes"]:
        bad = deepcopy(saved)
        candidate_image = image
        if name == "model":
            bad["body_without_inline_image"]["model"] = "other-model"
        elif name == "prompt":
            bad["body_without_inline_image"]["messages"][0]["content"][1]["text"] += " changed"
        elif name == "body_hash":
            bad["http_body_sha256"] = "0" * 64
        else:
            candidate_image += b"changed"
        try:
            verify_payload(bad, candidate_image, prompt)
        except AssertionError:
            rejected.append(name)
        else:
            raise AssertionError("tampered request accepted")
    assert len(rejected) == 4
    return rejected


def verify_refs(value, checked):
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and re.fullmatch(r"[0-9a-f]{64}", value.get("sha256", "")):
            path = REPO / value["path"]
            if value["path"].startswith(HOLDOUT) and path.suffix == ".pdf":
                return
            assert sha(path) == value["sha256"], value["path"]
            checked.add(value["path"])
        for item in value.values():
            verify_refs(item, checked)
    elif isinstance(value, list):
        for item in value:
            verify_refs(item, checked)


def main():
    assert (HERE / "execution.json").is_file(), "Wait for actual execution to finish"
    registration, execution = read(HERE / "registration.json"), read(HERE / "execution.json")
    contract = read(HERE / "review/contract.json")
    assert sha(HERE / "run.py") == registration["runner_sha256"]
    registered = datetime.fromisoformat(registration["registered_at_utc"]).timestamp()
    assert datetime.fromisoformat(contract["frozen_at_utc"]).timestamp() <= registered
    module = ast.parse((HERE / "run.py").read_text())
    prompt = next(ast.literal_eval(node.value) for node in module.body
                  if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PROMPT" for t in node.targets))
    assert all(token not in prompt for token in ["ReflACT", "RefIACT", "23.3", "40.5", "#/texts/", "wikiskill", "seal-p", "dgm-p"])
    assert version("docling") == "2.102.0" and version("docling-core") == "2.96.0"
    negatives = selfcheck(prompt)
    checked = set()
    verify_refs(registration, checked)
    verify_refs(contract, checked)
    prior = read(HERE / "prior-inputs.json")
    verify_refs(prior, checked)
    prior_payloads = set()
    for reference in prior["prior_manifest_refs"]:
        manifest = read(REPO / reference["path"])
        manifest_checked = set()
        verify_refs(manifest, manifest_checked)
        checked.update(manifest_checked)
        prior_payloads.update(manifest_checked)
    preflight = read(HERE / "preflight/summary.json")
    for name, expected in preflight["source_files"].items():
        assert sha(Path(name)) == expected
    observations, conversions = read(HERE / "observations.json"), read(HERE / "conversions.json")
    assert execution["all_exchanges_usable"] and execution["attempted_requests"] == 8
    assert execution["automatic_retries"] == 0 and execution["model_output_repair"] is False
    assert execution["holdout_reads"] == 0 and execution["credentials_persisted"] is False
    rows = contract["scope"]["page_manifest"]
    expected_ids = [(r["source"], r["physical_page_1based"]) for r in rows]
    assert len(set(expected_ids)) == 8
    assert [(r["source"], r["page"]) for r in observations] == expected_ids
    assert len({r["request_id"] for r in observations}) == 8 and all(r["request_id"] for r in observations)
    records, responses = [], {}
    totals = {k: 0 for k in ["prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens", "cached_tokens"]}
    for (source, page), observed in zip(expected_ids, observations):
        folder = HERE / "api" / f"{source}-p{page}"
        request, response = read(folder / "request.json"), read(folder / "response.json")
        image = (folder / "input.png").read_bytes()
        verify_payload(request, image, prompt)
        assert request["source"] == source and request["physical_page_1based"] == page
        assert request["endpoint"] == ENDPOINT
        choice = response["choices"][0]
        assert response["model"] == observed["returned_model"] == MODEL
        assert response["created"] >= registered
        assert observed["http_status"] == 200 and observed["attempts"] == 1
        assert choice["finish_reason"] == observed["finish_reason"] == "stop"
        assert not choice["message"].get("refusal") and not observed["refusal"]
        content = choice["message"]["content"]
        assert isinstance(content, str) and content.strip()
        assert (folder / "raw-doctags.txt").read_text() == content
        assert response["usage"] == observed["usage"]
        usage = response["usage"]
        assert usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"]
        for name in ["prompt_tokens", "completion_tokens", "total_tokens"]:
            totals[name] += usage[name]
        totals["reasoning_tokens"] += usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
        totals["cached_tokens"] += usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        locations = [int(x) for x in re.findall(r"<loc_(-?\d+)>", content)]
        with Image.open(BytesIO(image)) as im:
            dimensions = list(im.size)
        records.append({"source": source, "physical_page_1based": page,
            "request_body_bytes_verified": True, "input_png_sha256": sha(folder / "input.png"),
            "input_png_pixels_wh": dimensions, "response_sha256": sha(folder / "response.json"),
            "raw_doctags_sha256": sha(folder / "raw-doctags.txt"),
            "response_id": response.get("id"), "request_id": observed["request_id"],
            "response_created": response["created"],
            "saved_response_content_matches_saved_doctags": True,
            "observer_redaction_applied": observed["credential_redaction_applied"],
            "persisted_redaction_marker_count": content.count("[REDACTED]"),
            "original_http_response_preservation_confirmed": not observed["credential_redaction_applied"],
            "location_tokens": len(locations),
            "location_min": min(locations, default=None), "location_max": max(locations, default=None),
            "outside_requested_0_500_count": sum(not 0 <= x <= 500 for x in locations),
            "one_doctag_envelope": bool(re.fullmatch(r"\s*<doctag>.*</doctag>\s*", content, flags=re.S)),
            "seconds": observed["seconds"], "usage": usage})
        responses[(source, page)] = response

    # Replay the saved unedited HTTP responses through the independently built
    # stock converter. Any unmocked network transport is a hard failure.
    replayed, active = [], {"source": None, "pages": [], "index": 0}
    def no_network(*args, **kwargs):
        raise AssertionError("Network forbidden during verification")
    def post(url, *, headers=None, json=None, timeout=None, **kwargs):
        assert str(url) == ENDPOINT and timeout == 180 and not kwargs
        source, page = active["source"], active["pages"][active["index"]]
        active["index"] += 1
        saved = read(HERE / "api" / f"{source}-p{page}" / "request.json")
        assert hashlib.sha256(request_body(json)).hexdigest() == saved["http_body_sha256"]
        return SimpleNamespace(ok=True, text=__import__("json").dumps(responses[(source, page)]))
    engine = ApiVlmEngineOptions(url=ENDPOINT, timeout=180, concurrency=1,
        params={"model": MODEL, "temperature": None, "max_completion_tokens": 8192,
                "reasoning_effort": "low", "store": False})
    spec = VlmModelSpec(name="gpt-6-luna-official-doctags-candidate2", default_repo_id=MODEL,
        prompt=prompt, response_format=ResponseFormat.DOCTAGS, max_new_tokens=8192)
    options = VlmPipelineOptions(enable_remote_services=True,
        accelerator_options=AcceleratorOptions(device="cpu", num_threads=4), images_scale=1.0,
        generate_page_images=True, generate_picture_images=False,
        vlm_options=VlmConvertOptions(engine_options=engine, model_spec=spec, scale=2.0,
                                      batch_size=1, force_backend_text=False))
    assert execution["safe_options"]["actual_engine_options"] == engine.model_dump(mode="json")
    with ExitStack() as stack:
        stack.enter_context(patch("requests.sessions.Session.send", side_effect=no_network))
        stack.enter_context(patch("socket.create_connection", side_effect=no_network))
        stack.enter_context(patch("socket.socket.connect", side_effect=no_network))
        stack.enter_context(patch("requests.post", side_effect=post))
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
            pipeline_cls=VlmPipeline, pipeline_options=options)})
        for conversion in conversions:
            source, pages = conversion["source"], conversion["requested_physical_pages"]
            active.update(source=source, pages=pages, index=0)
            source_row = next(r for r in rows if r["source"] == source)
            with warnings.catch_warnings(record=True) as native_warnings:
                warnings.simplefilter("always")
                replay = converter.convert(REPO / source_row["source_pdf_ref"]["path"],
                                           page_range=(min(pages), max(pages)), raises_on_error=False)
            raw = replay.document.export_to_dict()
            saved = read(HERE / "documents" / source / "document.json")
            diff = differences(saved, raw)
            redacted_pages = [r for r in records if r["source"] == source and r["observer_redaction_applied"]]
            if redacted_pages:
                assert source == "seal" and [r["physical_page_1based"] for r in redacted_pages] == [2]
                assert len(diff) == 3
                string_diffs = [d for d in diff if isinstance(d["stored_official"], str)]
                assert len(string_diffs) == 2
                assert all(d["path"].endswith(("/text", "/orig")) and
                           legacy_redact(d["stored_official"]) == d["replayed_persisted_response"] for d in string_diffs)
                text = next(d for d in string_diffs if d["path"].endswith("/text"))
                span = next(d for d in diff if d not in string_diffs)
                assert span["path"] == text["path"].removesuffix("/text") + "/prov/0/charspan/1"
                assert span["stored_official"] == len(text["stored_official"])
                assert span["replayed_persisted_response"] == len(text["replayed_persisted_response"])
            else:
                assert not diff, source + " official assembly differs from stored document"
            with warnings.catch_warnings(record=True) as export_warnings:
                warnings.simplefilter("always")
                markdown_exact = replay.document.export_to_markdown() == (HERE / "documents" / source / "document.md").read_text()
            assert markdown_exact == (not bool(diff))
            assert active["index"] == len(pages)
            assert conversion["actual_requests"] == len(pages)
            assert conversion["source_page_map"] == {str(i + 1): p for i, p in enumerate(pages)}
            assert conversion["official_document_pages"] == list(range(1, len(pages) + 1))
            assert conversion["custom_output_repair"] is False
            positions = [p for key in ["texts", "tables", "pictures"] for item in raw[key] for p in item.get("prov", [])]
            outside, zero, invalid = 0, 0, 0
            for position in positions:
                box = position["bbox"]
                size = raw["pages"][str(position["page_no"])]["size"]
                invalid += box["r"] <= box["l"] or abs(box["b"] - box["t"]) <= 0
                zero += all(box[x] == 0 for x in ["l", "t", "r", "b"])
                outside += not (0 <= box["l"] <= box["r"] <= size["width"] and
                                0 <= min(box["t"], box["b"]) <= max(box["t"], box["b"]) <= size["height"])
            replayed.append({"source": source, "saved_official_document_exactly_reproduced": not bool(diff),
                "saved_markdown_exactly_reproduced": markdown_exact, "source_page_map": conversion["source_page_map"],
                "persisted_observer_redaction_differences": [{"path": d["path"],
                    "stored_length_or_value": len(d["stored_official"]) if isinstance(d["stored_official"], str) else d["stored_official"],
                    "replayed_length_or_value": len(d["replayed_persisted_response"]) if isinstance(d["replayed_persisted_response"], str) else d["replayed_persisted_response"],
                    "legacy_redaction_matches": [m.group(0) for m in re.finditer(r"sk-(?:proj-)?[A-Za-z0-9_.*-]{6,}", d["stored_official"])] if isinstance(d["stored_official"], str) else []} for d in diff],
                "all_replay_differences_explained_by_frozen_observer_redaction": bool(diff),
                "native_warning_count": len(native_warnings),
                "native_warning_messages": sorted({str(w.message) for w in native_warnings}),
                "markdown_export_warning_count": len(export_warnings),
                "markdown_export_warning_messages": sorted({str(w.message) for w in export_warnings}),
                "official_page_sizes": {k: v["size"] for k,v in raw["pages"].items()},
                "provenance_count": len(positions), "zero_bboxes": zero,
                "degenerate_bboxes": invalid, "bboxes_outside_official_page": outside,
                "bbox_origin": "Model-predicted DocTags coordinates interpreted by stock Core parser; not measured source evidence"})
    summary = {"passed": True, "scope": "Independent saved HTTP reconstruction and stock official converter replay; no semantic acceptance claim",
        "registration_sha256": sha(HERE / "registration.json"), "source_contract_sha256": sha(HERE / "review/contract.json"),
        "registered_before_all_responses": True, "requests_verified": len(records), "one_attempt_each": True,
        "source_documents": 4, "source_pages": 8, "model": MODEL,
        "exact_http_body_reconstruction": True, "saved_response_and_doctags_content_identical": True,
        "original_http_response_preserved_pages": sum(not r["observer_redaction_applied"] for r in records),
        "observer_false_positive_redaction_pages": [r["source"] + "-p" + str(r["physical_page_1based"]) for r in records if r["observer_redaction_applied"]],
        "output_repair": False,
        "official_document_and_markdown_replay_exact": all(r["saved_official_document_exactly_reproduced"] for r in replayed),
        "unredacted_documents_replay_exact_and_only_known_redaction_diff": True,
        "location_contract_satisfied": all(r["outside_requested_0_500_count"] == 0 for r in records),
        "location_tokens_outside_contract": sum(r["outside_requested_0_500_count"] for r in records),
        "source_page_identity_map_does_not_prove_geometry": True,
        "frozen_references_verified": len(checked), "prior_payload_paths_verified": len(prior_payloads),
        "holdout_pdf_reads": 0, "credentials_read": False, "network_calls": 0,
        "usage": totals, "requests": records, "official_replay": replayed,
        "selfcheck": {"passed": True, "rejected_tampered_request_controls": negatives},
        "official_implementation_paths": {"pipeline": inspect.getsourcefile(VlmPipeline), "api_engine": inspect.getsourcefile(ApiVlmEngine)}}
    (HERE / "api-verification.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:summary[k] for k in ["passed","requests_verified","exact_http_body_reconstruction","official_document_and_markdown_replay_exact","original_http_response_preserved_pages","observer_false_positive_redaction_pages","location_contract_satisfied","location_tokens_outside_contract","usage","holdout_pdf_reads"]}, indent=2))


if __name__ == "__main__":
    main()
