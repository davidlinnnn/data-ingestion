"""#159: CodeFormulaV2 through docling's own formula stage, on the 46 formulas prepare.py wrote.

    env HF_HUB_OFFLINE=1 scripts/heavy-lock codeformula-159 -- \
        CF_ENV/bin/python docs/research/codeformula-vs-vlm-2026-11-07/run_cf.py OUT MODELS

CF_ENV is a venv with requirements.lock.txt (docling-slim 2.148.0); MODELS holds
docling-project--CodeFormulaV2 at the revision of weights-codeformulav2.json. Two inputs per formula:

  official  docling's crop: the source page rendered by PyPdfiumDocumentBackend at the stage's
            images_scale (1.67, 120 dpi) with expansion_factor (0.18) added on every side
  same      the crop formula@1 sends the VLM (inputs/<crop_sha256>.png)

The model is CodeFormulaVlmModel with CodeFormulaVlmOptions.from_preset("codeformulav2") and the
default AcceleratorOptions, so docling picks the engine and device. Each paper's formulas run as one
batch, as docling batches one document's formulas. outputs.json gets per formula and input the
text docling writes into the item, the engine's raw text and stop reason, and the batch time.
"""

import hashlib
import io
import json
import platform
import sys
import time
from pathlib import Path

import torch
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import InputFormat, ItemAndImageEnrichmentElement
from docling.datamodel.document import InputDocument
from docling.datamodel.pipeline_options import CodeFormulaVlmOptions
from docling.models.stages.code_formula.code_formula_vlm_model import CodeFormulaVlmModel
from docling_core.types.doc import BoundingBox, DocItemLabel, DoclingDocument
from PIL import Image

HERE = Path(__file__).resolve().parent
REVISION = json.loads((HERE / "weights-codeformulav2.json").read_text())["revision"]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def official_crop(source: Path, item: dict) -> Image.Image:
    document = InputDocument(path_or_stream=source, format=InputFormat.PDF,
                             backend=PyPdfiumDocumentBackend)  # fmt: skip
    page = document._backend.load_page(item["page"] - 1)
    try:
        box = BoundingBox.model_validate(item["bbox"])
        factor = CodeFormulaVlmModel.expansion_factor  # the stage reads options.expansion_factor
        return page.get_page_image(scale=CodeFormulaVlmModel.images_scale,
                                   cropbox=box.expand_by_scale(factor, factor))  # fmt: skip
    finally:
        page.unload()
        document._backend.unload()


def main(out: Path, models: Path) -> int:
    frozen = json.loads((HERE / "freeze.json").read_text())["sha256"]
    for name, path in (("items.json", out / "items.json"), ("run_cf.py", HERE / "run_cf.py"),
                       ("weights-codeformulav2.json", HERE / "weights-codeformulav2.json")):  # fmt: skip
        assert sha(path.read_bytes()) == frozen[name], f"{name} changed since freeze.json"
    weights = json.loads((HERE / "weights-codeformulav2.json").read_text())["files"]
    for f in weights:
        local = models / "docling-project--CodeFormulaV2" / f["file"]
        assert sha(local.read_bytes()) == f["sha256"], f"{f['file']} differs from the manifest"
    items = json.loads((out / "items.json").read_text())
    options = CodeFormulaVlmOptions.from_preset("codeformulav2")
    assert options.expansion_factor == CodeFormulaVlmModel.expansion_factor == 0.18
    assert options.stop_on_repetition
    options.model_spec.revision = REVISION
    # In a docling pipeline on CPU the layout stage calls torch.set_num_threads(num_threads)
    torch.set_num_threads(AcceleratorOptions().num_threads)
    model = CodeFormulaVlmModel(enabled=True, enable_remote_services=False,
                                artifacts_path=models, options=options,
                                accelerator_options=AcceleratorOptions())  # fmt: skip
    # AUTO_INLINE delegates to the engine it selected; record that engine's raw outputs
    engine = getattr(model.engine, "actual_engine", None) or model.engine
    raw: list = []
    predict_batch = engine.predict_batch
    engine.predict_batch = lambda inputs: raw.extend(predict_batch(inputs)) or raw[-len(inputs):]

    def enrich(images: list[Image.Image]) -> tuple[list[str], list, float]:
        doc = DoclingDocument(name="formulas")
        elements = [ItemAndImageEnrichmentElement(
            item=doc.add_text(label=DocItemLabel.FORMULA, text=""), image=image)
            for image in images]  # fmt: skip
        raw.clear()
        start = time.perf_counter()
        texts = [item.text for item in model(doc, elements)]
        return texts, list(raw), time.perf_counter() - start

    papers: dict[int, list[dict]] = {}
    for item in items:
        papers.setdefault(item["paper"], []).append(item)
    enrich([Image.open(out / "inputs" / f"{items[0]['crop_sha256']}.png").convert("RGB")])  # warm-up
    results: dict[str, dict] = {i["label"]: {} for i in items}
    for paper, group in sorted(papers.items()):
        crops = {"official": [], "same": []}
        for item in group:
            image = official_crop(out / "sources" / f"{item['source_sha256']}.pdf", item)
            data = png(image)
            (out / "inputs" / f"{sha(data)}.png").write_bytes(data)
            crops["official"].append((sha(data), image))
            data = (out / "inputs" / f"{item['crop_sha256']}.png").read_bytes()
            crops["same"].append((sha(data), Image.open(io.BytesIO(data)).convert("RGB")))
        for variant, pairs in crops.items():
            texts, outputs, seconds = enrich([image for _, image in pairs])
            assert len(texts) == len(outputs) == len(group)
            for item, (digest, image), text, output in zip(group, pairs, texts, outputs,
                                                          strict=True):  # fmt: skip
                results[item["label"]][variant] = {
                    "crop_sha256": digest, "crop_px": list(image.size), "text": text,
                    "raw_text": output.text, "stop_reason": output.stop_reason,
                    "batch_size": len(group), "batch_seconds": round(seconds, 3)}  # fmt: skip
            print(f"p{paper:02d} {variant} {len(group)} in {seconds:.1f} s", flush=True)
    (HERE / "outputs.json").write_text(json.dumps({
        "model": f"docling-project/CodeFormulaV2@{REVISION}",
        "engine": type(engine).__name__, "device": str(getattr(engine, "device", "")),
        "torch_threads": torch.get_num_threads(), "machine": platform.platform(),
        "items": results}, indent=1, ensure_ascii=False) + "\n")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
