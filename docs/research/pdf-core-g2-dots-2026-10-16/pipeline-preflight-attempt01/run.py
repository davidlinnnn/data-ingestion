"""Exercise official dots VlmPipeline assembly with mocked transport only."""
import base64
from contextlib import ExitStack
from io import BytesIO
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
from PIL import Image
from docling.datamodel.base_models import InputFormat
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline
from preflight import CODE, INLINE, FORMULA

HERE = Path(__file__).resolve().parent
OUT = HERE / "pipeline-preflight"


def main():
    OUT.mkdir(exist_ok=False)
    inputs = json.loads((HERE / "preflight/input.json").read_text())
    responses = [json.dumps(inputs), json.dumps([
        {"category": "Text", "bbox": [30,30,1100,130], "text": "Second page sentinel."},
        {"category": "Text", "bbox": [30,150,1100,250], "text": "Use `<b>bold</b>` literally."}])]
    captures = []
    def mock_post(url, *, json=None, **kwargs):
        assert str(url) == "https://mock.invalid/v1/chat/completions"
        content = json["messages"][0]["content"]
        img = next(x["image_url"]["url"] for x in content if x["type"] == "image_url")
        png = base64.b64decode(img.split(",",1)[1])
        captures.append({"image_size":Image.open(BytesIO(png)).size,
                         "prompt":next(x["text"] for x in content if x["type"]=="text"),
                         "model":json["model"], "max_tokens":json.get("max_tokens")})
        return SimpleNamespace(ok=True, text=__import__("json").dumps({"choices":[{
            "message":{"content":responses[len(captures)-1]},"finish_reason":"stop"}]}))
    def blocked(*a, **kw):
        raise AssertionError("Network forbidden in parser preflight")
    vlm = VlmConvertOptions.from_preset("dots_ocr", engine_options=ApiVlmEngineOptions(
        url="https://mock.invalid/v1/chat/completions",params={"model":"mock-dots-no-inference"}))
    options = VlmPipelineOptions(enable_remote_services=True, vlm_options=vlm,
        accelerator_options=AcceleratorOptions(device="cpu", num_threads=4),
        generate_page_images=True, images_scale=2)
    with ExitStack() as stack:
        stack.enter_context(patch("requests.post",side_effect=mock_post))
        stack.enter_context(patch("requests.sessions.Session.send",side_effect=blocked))
        stack.enter_context(patch("socket.socket.connect",side_effect=blocked))
        converter = DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(
            pipeline_cls=VlmPipeline,pipeline_options=options)})
        source = HERE.parent / "pdf-core-g2-official-method-2026-10-15/preflight/source.pdf"
        result = converter.convert(source)
    doc = result.document
    doc.save_as_json(OUT / "document.json")
    default = doc.export_to_markdown()
    native = doc.export_to_markdown(escape_underscores=False,escape_html=False)
    (OUT / "default.md").write_text(default)
    (OUT / "native-markdown.md").write_text(native)
    checks = {"status": result.status.value, "mock_calls": len(captures), "real_model_calls":0,
              "pages":sorted(doc.pages), "inline_native_options":INLINE in native,
              "code_literal":CODE in native, "formula_literal":FORMULA in native,
              "second_page": "Second page sentinel." in native,
              "html_inline_code_literal_preserved": "`<b>bold</b>`" in native,
              "errors":[x.model_dump(mode="json") for x in result.errors],
              "captures":captures, "output_repairs":0}
    (OUT / "results.json").write_text(json.dumps(checks,indent=2)+"\n")
    assert checks["mock_calls"] == 2 and checks["pages"] == [1,2]
    assert checks["inline_native_options"] and checks["code_literal"] and checks["formula_literal"]
    assert not checks["html_inline_code_literal_preserved"]
    print(json.dumps(checks,indent=2))


if __name__ == "__main__":
    main()
