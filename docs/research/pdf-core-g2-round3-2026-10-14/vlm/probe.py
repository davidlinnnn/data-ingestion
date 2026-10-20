"""Bounded Granite-Docling CPU task probes, not full ingest qualification."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
JOBS = ["seal-eq2", "english-scan-p1", "skillopt-p8"]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def child(name):
    import torch
    from PIL import Image
    import pypdfium2 as pdfium
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.pipeline_options import CodeFormulaVlmOptions, VlmConvertOptions
    from docling.datamodel.vlm_engine_options import TransformersVlmEngineOptions
    from docling.models.inference_engines.vlm import VlmEngineInput
    from docling.models.stages.code_formula.code_formula_vlm_model import CodeFormulaVlmModel
    from docling.models.stages.vlm_convert.vlm_convert_model import VlmConvertModel
    from docling_core.types.doc import DoclingDocument
    from docling_core.types.doc.document import DocTagsDocument

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    out = HERE / name
    registry = json.loads(REGISTRY.read_text())
    if name == "seal-eq2":
        case = next(c for c in registry["cases"] if c["id"] == "G1-E07")
        region = case["details"]["regions"][0]
        source = Path(region["image_path"])
        assert sha(source) == region["image_sha256"]
        image = Image.open(source).convert("RGB")
        image = image.resize(tuple(round(v * 1.67 / 3) for v in image.size), Image.Resampling.LANCZOS)
        locator = {"case": case["id"], "source_png": str(source), "sha256": sha(source),
                   "physical_page": 4, "bbox_top_left_pdf_points": region["bbox_top_left_pt"],
                   "render_scale": 1.67, "scope": "Same fixed equation crop as round2; no detection or backfill"}
        options = CodeFormulaVlmOptions.from_preset("granite_docling", engine_options=
                  TransformersVlmEngineOptions(device="cpu", torch_dtype="float32", compile_model=False))
        stage_class = CodeFormulaVlmModel
        prompt, budget = "<formula>", 512
    else:
        source_id, page_no, case_id = (("SRC04", 1, "G1-O03") if name == "english-scan-p1"
                                        else ("SRC07", 8, "G1-T02"))
        source = next(s for s in registry["sources"] if s["id"] == source_id)
        pdf = REPO / source["path"]
        assert sha(pdf) == source["sha256"]
        with pdfium.PdfDocument(pdf) as document:
            page = document[page_no - 1]
            page_size = list(page.get_size())
            image = page.render(scale=2).to_pil().convert("RGB")
        locator = {"case": case_id, "source_pdf": source["path"], "sha256": source["sha256"],
                   "physical_page": page_no, "page_size_points": page_size, "render_scale": 2,
                   "scope": "Complete original page, official engine/prompt/DocTags parser; not full VlmPipeline lifecycle"}
        options = VlmConvertOptions.from_preset("granite_docling", engine_options=
                  TransformersVlmEngineOptions(device="cpu", torch_dtype="float32", compile_model=False))
        stage_class = VlmConvertModel
        prompt, budget = options.model_spec.prompt, 4096
    image.save(out / "input.png")
    save(out / "input.json", {**locator, "pixels": image.size, "input_sha256": sha(out / "input.png")})
    downloaded = json.loads((HERE / "download.json").read_text())
    artifacts = HERE / "artifacts"
    artifacts.mkdir(exist_ok=True)
    link = artifacts / "ibm-granite--granite-docling-258M"
    if not link.exists():
        link.symlink_to(downloaded["snapshot_path"], target_is_directory=True)
    options.model_spec.revision = downloaded["revision"]
    tick = time.monotonic()
    stage = stage_class(enabled=True, enable_remote_services=False, artifacts_path=artifacts,
                        options=options, accelerator_options=AcceleratorOptions(device="cpu", num_threads=4))
    load_seconds = time.monotonic() - tick
    model = stage.engine.vlm_model
    devices = sorted({str(v.device) for v in model.parameters()})
    dtypes = sorted({str(v.dtype) for v in model.parameters()})
    assert devices == ["cpu"] and dtypes == ["torch.float32"]
    save(out / "method.json", {"model": downloaded["repo"], "revision": downloaded["revision"],
         "options": options.model_dump(mode="json", serialize_as_any=True), "devices": devices, "dtypes": dtypes,
         "torch_threads": torch.get_num_threads(), "interop_threads": torch.get_num_interop_threads(),
         "batch": 1, "max_new_tokens": budget, "prompt": prompt, "skip_special_tokens": False,
         "stage_construction_including_load_seconds": load_seconds,
         "versions": {p: importlib.metadata.version(p) for p in ["docling", "docling-core", "transformers", "torch"]}})
    original = model.generate

    def observed_generate(**kwargs):
        raw = original(**kwargs)
        prefix = kwargs["input_ids"].shape[1]
        tokens = raw[0, prefix:].tolist()
        eos = model.generation_config.eos_token_id
        eos_ids = eos if isinstance(eos, list) else [eos]
        save(out / "generation.json", {"input_tokens": prefix, "generated_tokens": len(tokens),
             "generated_ids": tokens, "eos_token_ids": eos, "last_token_is_eos": tokens[-1] in eos_ids,
             "at_token_limit": len(tokens) >= budget, "max_new_tokens": kwargs["max_new_tokens"]})
        return raw

    model.generate = observed_generate
    tick = time.monotonic()
    outputs = stage.engine.predict_batch([VlmEngineInput(image=image, prompt=prompt,
               temperature=0, max_new_tokens=budget, extra_generation_config={"skip_special_tokens": False})])
    elapsed = time.monotonic() - tick
    assert len(outputs) == 1
    text = outputs[0].text
    save(out / "raw-output.json", outputs[0].model_dump(mode="json"))
    (out / "output.txt").write_text(text)
    if name == "seal-eq2":
        (out / "cleaned.txt").write_text(stage._post_process([text])[0])
    else:
        doctags = DocTagsDocument.from_doctags_and_image_pairs([text], [image])
        document = DoclingDocument.load_from_doctags(doctag_document=doctags)
        document.save_as_json(out / "document.json")
        (out / "document.md").write_text(document.export_to_markdown())
        # The official parser numbers this isolated image as page1; input.json retains original physical page.
        save(out / "parser.json", {"text_items": len(document.texts), "tables": len(document.tables),
             "pictures": len(document.pictures), "page_keys": list(document.pages),
             "source_physical_page": locator["physical_page"], "parser_remap_applied": False})
    save(out / "result.json", {"execution_status": "completed", "inference_seconds": elapsed,
         "stage_construction_including_load_seconds": load_seconds, "quality_status": "requires_source_review"})


def main():
    summary = {"runner_sha256": sha(Path(__file__)), "registry_sha256": sha(REGISTRY), "observations": []}
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", DOCLING_DEVICE="cpu", OMP_NUM_THREADS="4")
    for name in JOBS:
        out = HERE / name
        out.mkdir(exist_ok=False)
        assert psutil.virtual_memory().available >= 8 * 1024**3
        started, peak, stopped = time.monotonic(), 0, None
        with (out / "child.log").open("wb") as log:
            process = subprocess.Popen(["rtk", "proxy", sys.executable, "-B", str(Path(__file__).resolve()), "--child", name],
                         cwd=REPO, env=env, stdout=log, stderr=log, start_new_session=True)
            try:
                while process.poll() is None:
                    try:
                        owner = psutil.Process(process.pid)
                        peak = max(peak, sum(p.memory_info().rss for p in [owner, *owner.children(recursive=True)]))
                    except psutil.NoSuchProcess:
                        pass
                    if peak > 6 * 1024**3 or time.monotonic() - started > 180:
                        stopped = "sampled_memory_stop" if peak > 6 * 1024**3 else "timeout"
                        break
                    time.sleep(.25)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        observation = {"case": name, "exit_code": process.returncode, "stopped": stopped,
                       "child_wall_seconds": time.monotonic() - started, "sampled_tree_peak_rss_bytes": peak,
                       "sample_seconds": .25, "limit_bytes": 6 * 1024**3, "timeout_seconds": 180}
        summary["observations"].append(observation)
        save(HERE / "observations.json", summary)
        print(json.dumps(observation), flush=True)
        if process.returncode or stopped:
            raise RuntimeError("Bounded probe failed; preserve artifacts and inspect before retry")
    assert sha(REGISTRY) == summary["registry_sha256"]


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        child(sys.argv[2])
    else:
        main()
