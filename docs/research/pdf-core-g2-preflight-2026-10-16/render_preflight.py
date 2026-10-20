"""Inspect exact VlmPipeline inputs and exercise approval before transport; no model."""
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch
from pydantic import AnyUrl

os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.models.inference_engines.vlm.api_openai_compatible_engine import ApiVlmEngine
from docling.models.inference_engines.vlm.base import VlmEngineOutput
from docling.pipeline.vlm_pipeline import VlmPipeline
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PRIOR = REPO / "docs/research/pdf-core-g2-dots-mlx-2026-10-16"
STUB = json.dumps([{"bbox": [0, 0, 100, 20], "category": "Text", "text": "Render preflight stub; no model result."}])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value):
    def encode(item):
        if isinstance(item, (set, frozenset)):
            return sorted(item)
        if isinstance(item, (Path, AnyUrl)):
            return str(item)
        raise TypeError(f"Unsupported config type: {type(item).__name__}")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=encode)


def canonical_sha(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def fingerprint(image, binding, engine_input):
    image = image.convert("RGB")
    return {**binding, "image_size": list(image.size),
            "pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
            "engine_input_sha256": canonical_sha(engine_input)}


def require_approved(actual, approval):
    if approval is None or approval.get("decision") != "approved" or actual != approval.get("fingerprint"):
        raise ValueError("Actual rendered input lacks matching inspection approval")


def cases():
    old = json.loads((PRIOR / "inputs.json").read_text())["pages"]
    selected = [next(x for x in old if x["id"] == name)
                for name in ["controls-p1", "validation-02-p1", "validation-02-p12"]]
    selected.insert(1, {"id": "wikiskill-p4", "physical_page": 4,
        "source_pdf": {"path": "docs/fixtures/agent-self-evolution-pilot-2026-10-11/01-2608.27454v1.pdf",
                       "sha256": "65afc6e12f6f707483fe1b79a97ab67c03abf4b4992f82fde03eb7b8d9ad4a69"}})
    return selected


def make_options():
    vlm = VlmConvertOptions.from_preset("dots_ocr", engine_options=ApiVlmEngineOptions(
        url="http://render-preflight.invalid/never-called", params={}))
    vlm.model_spec.revision = "c0111ce6bc07803dbc267932ffef0ae3a51dc951"
    return VlmPipelineOptions(vlm_options=vlm, generate_page_images=True,
                              images_scale=2, enable_remote_services=True)


def run(check=False):
    assert version("docling-slim") == "2.132.0" and version("docling-core") == "2.99.0"
    out = HERE / ("render-gate-v2" if check else "render-inputs-v2")
    out.mkdir(exist_ok=False)
    approvals = json.loads((HERE / "render-approvals-v2.json").read_text()) if check else None
    observations = []
    active = {}
    run_state = {"status": "running"}

    def persist():
        save(out / "results.json", {"status": run_state["status"], "purpose": "Actual pipeline render inspection/guard regression; stub is never a model prediction",
             "model_calls": 0, "network_calls": 0, "model_loaded": False, "holdout_reads": 0,
             "runner_sha256": sha(Path(__file__)), "registration_sha256": sha(HERE / "registration.json"),
             "options": json.loads(canonical_json(options.model_dump(mode="python"))),
             "runtime": {name: version(name) for name in ["docling-slim", "docling-core", "docling-parse"]},
             "records": observations})

    def forbidden_network(*args, **kwargs):
        raise AssertionError("No network allowed in render preflight")

    def inspect(engine, inputs):
        assert len(inputs) == 1
        item = inputs[0]
        image = item.image.convert("RGB")
        engine_input = item.model_dump(mode="json", exclude={"image"})
        actual = fingerprint(image, active["binding"], engine_input)
        record = active["record"]
        record["engine_entries"] += 1
        assert record["engine_entries"] == 1
        record["fingerprint"] = actual
        if check:
            approval = next((x for x in approvals["records"] if x["id"] == active["id"]), None)
            try:
                require_approved(actual, approval)
            except ValueError:
                record.update(decision="blocked", stub_transport_calls=0)
                raise
            record.update(decision="allowed", stub_transport_calls=1)
        else:
            record.update(decision="inspection_only", stub_transport_calls=1)
            image.save(out / f"{active['id']}.png")
            pixels = np.asarray(image)
            record.update(engine_input=engine_input,
                          fraction_all_rgb_below_64=float(np.mean(np.all(pixels < 64, axis=2))),
                          image_file_sha256=sha(out / f"{active['id']}.png"))
        return [VlmEngineOutput(text=STUB, stop_reason="preflight-stub-no-model")]

    options = make_options()
    with patch.object(ApiVlmEngine, "predict_batch", inspect), \
         patch.object(socket.socket, "connect", forbidden_network), \
         patch.object(socket, "create_connection", forbidden_network):
        for backend in [DoclingParseDocumentBackend, PyPdfiumDocumentBackend]:
            for case in cases():
                source = REPO / case["source_pdf"]["path"]
                active["id"] = f"{backend.__name__}--{case['id']}"
                record = {"id": active["id"], "fingerprint": None, "engine_entries": 0,
                          "decision": "not_entered", "stub_transport_calls": 0}
                active["record"] = record
                observations.append(record)
                persist()
                try:
                    assert "holdout" not in str(source) and sha(source) == case["source_pdf"]["sha256"]
                    active["binding"] = {"source_path": case["source_pdf"]["path"], "source_sha256": sha(source),
                        "physical_page": case["physical_page"], "backend": backend.__name__,
                        "images_scale": 2, "vlm_scale": 2, "options_sha256": canonical_sha(options.model_dump(mode="python"))}
                    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
                        pipeline_cls=VlmPipeline, backend=backend, pipeline_options=options)})
                    result = converter.convert(source, page_range=(case["physical_page"], case["physical_page"]), raises_on_error=False)
                    record["native_stub_conversion_status"] = result.status.value
                except Exception as exc:
                    record["exception"] = {"type": type(exc).__name__, "message": str(exc)}
                finally:
                    persist()
    assert len(observations) == 8 and "mlx_vlm" not in sys.modules
    if not check:
        assert all(x["engine_entries"] == 1 and x.get("native_stub_conversion_status") == "success" for x in observations)
        for row in observations:
            if "--validation-02-" in row["id"]:
                page = row["fingerprint"]["physical_page"]
                old = json.loads((PRIOR / "renderer-preflight/results.json").read_text())["records"]
                reference = next(x for x in old if x["page"] == page)
                key = "original_native" if row["fingerprint"]["backend"] == "DoclingParseDocumentBackend" else "official_pypdfium_backend"
                assert row["fingerprint"]["pixel_sha256"] == reference[key]["pixel_sha256"]
    else:
        assert sum(x["decision"] == "allowed" for x in observations) == 6
        assert sum(x["decision"] == "blocked" for x in observations) == 2
        assert all(x.get("native_stub_conversion_status") == "success" and x["stub_transport_calls"] == 1
                   for x in observations if x["decision"] == "allowed")
        assert all(x["stub_transport_calls"] == 0 for x in observations if x["decision"] == "blocked")
    run_state["status"] = "completed"
    persist()
    print(json.dumps({"records": len(observations), "model_calls": 0, "check": check}))


if __name__ == "__main__":
    assert sys.argv[1:] in [[], ["--check"], ["--config-fingerprint"]]
    if sys.argv[1:] == ["--config-fingerprint"]:
        options = make_options().model_dump(mode="python")
        print(json.dumps({"options_sha256": canonical_sha(options), "options": json.loads(canonical_json(options))}))
    else:
        run(check=bool(sys.argv[1:]))
