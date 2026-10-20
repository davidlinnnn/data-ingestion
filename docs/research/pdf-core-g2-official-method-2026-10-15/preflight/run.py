"""Exercise installed official pipeline with synthetic, transport-mocked responses.

No weights, credentials, real API, holdout, or custom output repair are used.
"""
from contextlib import ExitStack
from copy import deepcopy
import base64
import hashlib
from importlib.metadata import version
import inspect
from io import BytesIO
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from PIL import Image, ImageDraw
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
from docling.datamodel.pipeline_options_vlm_model import ResponseFormat
from docling.datamodel.stage_model_specs import VlmModelSpec
from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.models.inference_engines.vlm import VlmEngineInput
from docling.models.inference_engines.vlm.api_openai_compatible_engine import ApiVlmEngine
from docling.pipeline.vlm_pipeline import VlmPipeline

HERE = Path(__file__).resolve().parent
CODE = 'def f(x):\n    if x <= 2:\n        return {"k": [1, 2]}'
MATH = r"x^{2} + y_{i}"
INLINE_CODE = "items[i] <= limit"
FORMULA = r"z = \\frac{a}{b}".replace("\\\\", "\\")


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail_network(*args, **kwargs):
    raise AssertionError("Network transport is forbidden in offline preflight")


def document_fixtures():
    image = Image.new("RGB", (600, 800), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((360, 500, 540, 680), outline="black", width=4)
    draw.text((30, 20), "Synthetic parser fixture. No source recognition evaluated.", fill="black")
    image.save(HERE / "source.pdf", "PDF", save_all=True,
               append_images=[Image.new("RGB", (600, 800), "#eeeeee")], resolution=72)
    sample = Image.new("RGB", (20, 20), "green")
    buffer = BytesIO()
    sample.save(buffer, "PNG")
    uri = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    md = (f"Prefix ${MATH}$ and `{INLINE_CODE}` suffix.\n\n$$\n{FORMULA}\n$$\n\n"
          f"```python\n{CODE}\n```\n\n| Metric | Value |\n|---|---|\n| A | 12.5 |\n\n"
          f"![Diagram A]({uri})\n\nDiagram A.\n")
    html = (f"<html><body><p>Prefix <span class='math'>\\({MATH}\\)</span> and "
            f"<code>items[i] &lt;= limit</code> suffix.</p><div class='math'>\\[{FORMULA}\\]</div>"
            f"<pre><code class='language-python'>{CODE.replace('<', '&lt;')}</code></pre>"
            "<table><tr><th>Metric</th><th>Value</th></tr><tr><td>A</td><td>12.5</td></tr></table>"
            f"<figure><img src='{uri}' alt='Diagram A'/><figcaption>Diagram A.</figcaption></figure>"
            "</body></html>")
    dt = ("<doctag><inline><loc_20><loc_20><loc_450><loc_80>"
          f"<text>Prefix </text><formula>{MATH}</formula><text> and </text>"
          f"<code><_Python_>{INLINE_CODE.replace('<', '&lt;')}</code><text> suffix.</text></inline>"
          f"<formula><loc_20><loc_90><loc_400><loc_130>{FORMULA}</formula>"
          f"<code><loc_20><loc_150><loc_450><loc_250><_Python_>{CODE}</code>"
          "<otsl><loc_20><loc_280><loc_450><loc_350><ched>Metric<ched>Value<nl>"
          "<fcel>A<fcel>12.5<nl></otsl>"
          "<picture><loc_300><loc_360><loc_450><loc_450>"
          "<caption><loc_300><loc_455><loc_450><loc_480>Diagram A.</caption>"
          "</picture></doctag>")
    # DocTags is a token language, not HTML; source operators remain literal.
    dt = dt.replace("&lt;", "<")
    return {"markdown": [md, "Second page sentinel."],
            "html": [html, "<html><body><p>Second page sentinel.</p></body></html>"],
            "doctags": [dt, "<doctag><text><loc_20><loc_20><loc_450><loc_80>Second page sentinel.</text></doctag>"]}


def main():
    fixtures = document_fixtures()
    captures, active = [], {"format": None, "responses": [], "index": 0}

    def mock_post(url, *, headers=None, json=None, timeout=None, **kwargs):
        assert str(url) == "https://mock.invalid/v1/chat/completions"
        index = active["index"]
        text = active["responses"][index]
        active["index"] += 1
        response = {"id": f"mock-{active['format']}-{index}", "created": 0,
                    "object": "chat.completion", "model": "mock-only-no-inference",
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                                 "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        if active["format"] == "malformed-api":
            response = {"error": {"type": "synthetic_preflight_error", "message": "mock failure"}}
        captures.append({"format": active["format"], "index": index, "url": str(url),
                         "headers": deepcopy(headers), "timeout": timeout,
                         "payload": deepcopy(json), "response": response})
        return SimpleNamespace(ok=active["format"] != "malformed-api", text=__import__("json").dumps(response))

    results = []
    with ExitStack() as stack:
        stack.enter_context(patch("requests.sessions.Session.send", side_effect=fail_network))
        stack.enter_context(patch("socket.create_connection", side_effect=fail_network))
        stack.enter_context(patch("socket.socket.connect", side_effect=fail_network))
        stack.enter_context(patch("requests.post", side_effect=mock_post))
        # Inspect the actual engine request default separately, without page parsing.
        active.update(format="stock-temperature", responses=["stock mock"], index=0)
        engine = ApiVlmEngine(enable_remote_services=True, options=ApiVlmEngineOptions(
            url="https://mock.invalid/v1/chat/completions", params={"model": "requested-model-placeholder"}))
        engine.predict_batch([VlmEngineInput(image=Image.new("RGB", (20, 20)), prompt="mock",
                                            temperature=0.0, max_new_tokens=4096)])
        assert captures[-1]["payload"]["temperature"] == 0.0

        for name, responses in fixtures.items():
            folder = HERE / name
            folder.mkdir(exist_ok=True)
            active.update(format=name, responses=responses, index=0)
            for i, text in enumerate(responses):
                (folder / f"mock-response-{i + 1}.txt").write_text(text)
            spec = VlmModelSpec(name=f"offline-{name}", default_repo_id="requested-model-placeholder",
                                prompt=f"Return faithful {name} page content.",
                                response_format=ResponseFormat(name), max_new_tokens=8192)
            api = ApiVlmEngineOptions(url="https://mock.invalid/v1/chat/completions",
                params={"model": "requested-model-placeholder", "temperature": None,
                        "max_completion_tokens": 8192, "reasoning_effort": "low", "store": False}, concurrency=1)
            options = VlmPipelineOptions(enable_remote_services=True,
                accelerator_options=AcceleratorOptions(device="cpu", num_threads=4),
                images_scale=1.0, generate_page_images=True, generate_picture_images=False,
                vlm_options=VlmConvertOptions(engine_options=api, model_spec=spec,
                                              scale=1.0, batch_size=1, force_backend_text=False))
            save(folder / "options.json", options.model_dump(mode="json"))
            converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
                pipeline_cls=VlmPipeline, pipeline_options=options)})
            conv = converter.convert(HERE / "source.pdf", raises_on_error=True)
            assert active["index"] == 2
            doc = conv.document
            raw = doc.model_dump(mode="json")
            markdown = doc.export_to_markdown()
            save(folder / "document.json", raw)
            (folder / "document.md").write_text(markdown)
            texts = [item for item in raw["texts"]]
            table_cells = [c["text"] for t in raw["tables"] for c in t["data"]["table_cells"]]
            positions = [{"ref": item["self_ref"], "label": item["label"], "prov": item.get("prov", [])}
                         for collection in ("texts", "pictures", "tables") for item in raw[collection]]
            all_prov = [p for r in positions for p in r["prov"]]
            code_texts = [item["text"] for item in texts if item["label"] == "code"]
            result = {"format": name, "status": conv.status.value, "errors": [e.model_dump(mode="json") for e in conv.errors],
                "actual_api_calls": 0, "mock_calls": 2, "page_numbers": sorted(int(k) for k in raw["pages"]),
                "page_sizes": {k:v["size"] for k,v in raw["pages"].items()},
                "prose_tokens_present": all(s in markdown for s in ["Prefix", "suffix.", "Second page sentinel."]),
                "inline_latex_literal_present": MATH in markdown,
                "formula_literal_present": FORMULA in markdown,
                "formula_items": [item["text"] for item in texts if item["label"] == "formula"],
                "inline_group_count": sum(g["label"] == "inline" for g in raw["groups"]),
                "inline_code_literal_present": INLINE_CODE in markdown,
                "code_texts": code_texts, "code_exact_with_indentation": CODE in code_texts,
                "table_values_preserved": all(s in table_cells for s in ["Metric", "Value", "A", "12.5"]),
                "table_count": len(raw["tables"]), "picture_count": len(raw["pictures"]),
                "picture_embedded_image_count": sum(p.get("image") is not None for p in raw["pictures"]),
                "picture_caption_refs": [p.get("captions") for p in raw["pictures"]],
                "provenance": positions,
                "nonzero_bboxes": sum(p["bbox"]["r"] > p["bbox"]["l"] and abs(p["bbox"]["t"]-p["bbox"]["b"]) > 0 for p in all_prov),
                "all_bboxes_zero": bool(all_prov) and all(all(p["bbox"][v] == 0 for v in ["l","t","r","b"]) for p in all_prov),
                "transport_temperature_null": all(c["payload"].get("temperature", "missing") is None for c in captures if c["format"] == name)}
            save(folder / "result.json", result)
            results.append(result)
            assert result["status"] == "success"
            assert result["page_numbers"] == [1, 2]
            assert result["prose_tokens_present"]
            assert result["transport_temperature_null"]
            assert all("max_tokens" not in c["payload"] for c in captures if c["format"] == name)
            assert all(c["payload"]["max_completion_tokens"] == 8192 for c in captures if c["format"] == name)

        # Native helper swallows malformed HTTP responses; verify this cannot be
        # mistaken for successful source recognition by an outer runner.
        active.update(format="malformed-api", responses=["", ""], index=0)
        negative = converter.convert(HERE / "source.pdf", raises_on_error=False)
        negative_raw = negative.document.model_dump(mode="json")
        malformed = [c for c in captures if c["format"] == "malformed-api"]
        rejected_by_transport_capture = bool(malformed) and all("choices" not in c["response"] for c in malformed)
        assert rejected_by_transport_capture
        assert not negative_raw["texts"] and not negative_raw["tables"] and not negative_raw["pictures"]
        negative_control = {"fault": "malformed HTTP error envelope", "native_status": negative.status.value,
            "native_errors": [e.model_dump(mode="json") for e in negative.errors],
            "native_document_empty": True, "capture_validation_detected_failure": rejected_by_transport_capture,
            "must_not_treat_native_status_as_source_completion": True}
        save(HERE / "negative-control.json", negative_control)

    save(HERE / "transport-captures.json", captures)
    summary = {"runtime": {n: version(n) for n in ["docling", "docling-core", "docling-parse", "pillow"]},
               "scope": "Offline synthetic official pipeline/API engine/parser/assembly; no recognition-quality claim",
               "source_sha256": sha(HERE / "source.pdf"), "network_calls": 0,
               "holdout_reads": 0, "credentials_read": False, "weights_loaded": False,
               "installed_source_modified": False, "synthetic_mock_requests": len(captures),
               "negative_control": negative_control,
               "results": results,
               "source_files": {str(p):sha(p) for p in map(Path, [inspect.getsourcefile(VlmPipeline), inspect.getsourcefile(ApiVlmEngine)])}}
    save(HERE / "summary.json", summary)
    dt = next(r for r in results if r["format"] == "doctags")
    assert dt["inline_latex_literal_present"] and dt["formula_literal_present"]
    assert dt["inline_code_literal_present"] and dt["code_exact_with_indentation"]
    assert dt["table_values_preserved"] and dt["table_count"] == 1
    assert dt["picture_embedded_image_count"] == 1 and dt["picture_caption_refs"][0]
    assert dt["nonzero_bboxes"] == 11 and len(dt["formula_items"]) == 2
    assert all(r["all_bboxes_zero"] for r in results if r["format"] != "doctags")
    assert all(not r["inline_latex_literal_present"] for r in results if r["format"] != "doctags")
    save(HERE / "selfcheck.json", {"passed": True, "formats_tested": 3,
        "two_page_official_pipeline_and_assembly": True, "doctags_content_and_structure_checks": True,
        "native_markdown_html_math_and_geometry_limitations_recorded": True,
        "runtime_temperature_null_and_cap_8192_override_checked": True,
        "malformed_response_requires_external_capture_gate": True,
        "network_calls": 0, "recognition_quality_verified": False})
    print(json.dumps({"formats": [{k:r[k] for k in ["format","status","inline_group_count","inline_latex_literal_present","code_exact_with_indentation","table_values_preserved","picture_count","nonzero_bboxes","all_bboxes_zero"]} for r in results], "network_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
