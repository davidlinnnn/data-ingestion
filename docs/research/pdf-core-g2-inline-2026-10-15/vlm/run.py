"""Pinned Granite CPU paragraph components and unchanged official page pipeline."""

import fcntl
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
PACKAGE = REPO / "docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages"
OLD = REPO / "docs/research/pdf-core-g2-round3-2026-10-14/vlm"
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
DOWNLOAD = json.loads((OLD / "download.json").read_text())
SNAPSHOT = Path(DOWNLOAD["snapshot_path"])
PARAGRAPHS = HERE.parent / "inputs/input-manifest.json"
PAGES = [("wikiskill-p21", "SRC01", 21), ("dgm-p51", "SRC10", 51),
         ("seal-p3", "SRC11", 3), ("seal-p4", "SRC11", 4), ("controls-p1", "SRC05", 1)]
SOURCES = ["docling/document_converter.py", "docling/pipeline/vlm_pipeline.py",
           "docling/models/stages/vlm_convert/vlm_convert_model.py",
           "docling/models/inference_engines/vlm/transformers_engine.py",
           "docling/models/inference_engines/vlm/base.py", "docling/datamodel/stage_model_specs.py",
           "docling_core/types/doc/document.py", "docling_core/types/doc/doctags.py"]
LIMIT, TIMEOUT = 6 * 1024**3, 180
LOCK = "/private/tmp/data-ingestion-pdf-qualification.lock"


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jobs(phase):
    if phase == "page":
        registry = json.loads(REGISTRY.read_text())
        return [{"id": name, "source": next(s for s in registry["sources"] if s["id"] == sid),
                 "physical_page_1based": page} for name, sid, page in PAGES]
    manifest = json.loads(PARAGRAPHS.read_text())
    return manifest["candidates"]


def frozen(phase):
    paths = [Path(__file__), OLD / "probe.py", OLD / "download.json", REGISTRY]
    paths += [PACKAGE / p for p in SOURCES]
    for file in DOWNLOAD["files"]:
        path = SNAPSHOT / file["name"]
        assert sha(path) == file["sha256"], f"Cached model bytes changed: {path}"
        paths.append(path)
    for job in jobs(phase):
        if phase == "page":
            path = REPO / job["source"]["path"]
            assert sha(path) == job["source"]["sha256"]
        else:
            path = REPO / job["image_path"]
            assert sha(path) == job["image_sha256"]
        paths.append(path)
    if phase == "paragraph":
        paths.append(PARAGRAPHS)
    return {str(path.relative_to(REPO)): sha(path) for path in paths}


def trim_terminal_ids(ids, special_ids):
    trimmed = list(ids)
    while trimmed and trimmed[-1] in special_ids:
        trimmed.pop()
    return trimmed


def self_check():
    assert trim_terminal_ids([4, 5, 6, 0, 0], {0}) == [4, 5, 6]
    assert trim_terminal_ids([0, 4, 5], {0}) == [0, 4, 5]
    assert trim_terminal_ids([], {0}) == []
    assert "</doctag>".rstrip("<|end_of_text|>") != "</doctag>"
    print("Token-aware terminal-ID removal self-check passed; no inference.")


def parse(text, image, out, name):
    from docling_core.types.doc import DoclingDocument
    from docling_core.types.doc.document import DocTagsDocument
    folder = out / name
    folder.mkdir()
    try:
        document = DoclingDocument.load_from_doctags(DocTagsDocument.from_doctags_and_image_pairs([text], [image]))
        document.save_as_json(folder / "document.json")
        (folder / "document.md").write_text(document.export_to_markdown())
        save(folder / "parser.json", {"status": "completed", "text_items": len(document.texts),
             "tables": len(document.tables), "pictures": len(document.pictures), "parser_page_keys": list(document.pages),
             "source_page_remap_applied": False, "parser_coordinates": "supplied image pixels, page1; source mapping is separate"})
    except Exception as error:
        save(folder / "parser.json", {"status": "failed", "error_type": type(error).__name__, "error": str(error)})


def instrument(engine, out):
    model = engine.vlm_model
    devices = sorted({str(p.device) for p in model.parameters()})
    dtypes = sorted({str(p.dtype) for p in model.parameters()})
    assert devices == ["cpu"] and dtypes == ["torch.float32"]
    save(out / "actual-model.json", {"devices": devices, "dtypes": dtypes, "engine_device": engine.device,
         "engine_options": engine.options.model_dump(mode="json"), "model_config": engine.model_config.model_dump(mode="json")})
    tokenizer = engine._get_tokenizer()
    generate, predict = model.generate, engine.predict_batch
    state = {"calls": 0}

    def observed_generate(**kwargs):
        raw = generate(**kwargs)
        sequences = raw.sequences if hasattr(raw, "sequences") else raw
        prefix = kwargs["input_ids"].shape[1]
        ids = sequences[0, prefix:].tolist()
        eos = model.generation_config.eos_token_id
        eos_ids = eos if isinstance(eos, list) else [eos]
        special = {i for i in [*eos_ids, getattr(tokenizer, "pad_token_id", None)] if i is not None}
        trimmed = trim_terminal_ids(ids, special)
        state["token_aware"] = tokenizer.decode(trimmed, skip_special_tokens=False, clean_up_tokenization_spaces=False)
        state["unclean"] = tokenizer.decode(ids, skip_special_tokens=False, clean_up_tokenization_spaces=False)
        save(out / "generation.json", {"input_ids": kwargs["input_ids"][0].tolist(), "input_tokens": prefix,
            "generated_ids": ids, "full_sequence_ids": sequences[0].tolist(), "generated_tokens": len(ids),
            "eos_token_ids": eos, "pad_token_id": getattr(tokenizer, "pad_token_id", None), "pad_token": getattr(tokenizer, "pad_token", None),
            "last_token_is_eos": bool(ids and ids[-1] in eos_ids), "at_token_limit": len(ids) >= kwargs["max_new_tokens"],
            "actual_received_max_new_tokens": kwargs["max_new_tokens"], "do_sample": kwargs.get("do_sample"),
            "use_cache": kwargs.get("use_cache"), "removed_terminal_special_ids": ids[len(trimmed):],
            "input_tensors": {key: {"shape": list(v.shape), "device": str(v.device), "dtype": str(v.dtype)}
                              for key, v in kwargs.items() if hasattr(v, "shape") and hasattr(v, "device")}})
        (out / "unclean-decode.txt").write_text(state["unclean"])
        (out / "token-aware-decode.txt").write_text(state["token_aware"])
        return raw

    original_decode = engine.processor.batch_decode
    def observed_decode(*args, **kwargs):
        texts = original_decode(*args, **kwargs)
        save(out / "decoder-before-rstrip.json", {"kwargs": kwargs, "texts": texts})
        return texts

    def observed_predict(inputs):
        assert len(inputs) == 1 and state["calls"] == 0
        state["calls"] += 1
        value = inputs[0]
        value.image.save(out / "engine-input.png")
        save(out / "engine-input.json", {"prompt": value.prompt, "temperature": value.temperature,
             "max_new_tokens": value.max_new_tokens, "stop_strings": value.stop_strings,
             "extra_generation_config": value.extra_generation_config,
             "pixels_wh": value.image.size, "image_sha256": sha(out / "engine-input.png")})
        outputs = predict(inputs)
        save(out / "engine-output.json", [v.model_dump(mode="json") for v in outputs])
        (out / "engine-output.txt").write_text(outputs[0].text)
        return outputs

    model.generate, engine.processor.batch_decode, engine.predict_batch = observed_generate, observed_decode, observed_predict
    return state


def worker(phase, name):
    import torch
    from PIL import Image
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
    from docling.datamodel.vlm_engine_options import TransformersVlmEngineOptions
    from docling.models.stages.vlm_convert.vlm_convert_model import VlmConvertModel
    from docling.models.inference_engines.vlm import VlmEngineInput
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    job = next(j for j in jobs(phase) if j["id"] == name)
    out = HERE / phase / "runs" / name
    save(out / "source-input.json", job)
    options = VlmConvertOptions.from_preset("granite_docling", engine_options=TransformersVlmEngineOptions(
        device="cpu", torch_dtype="float32", compile_model=False, quantized=False, trust_remote_code=False))
    options.model_spec.revision = DOWNLOAD["revision"]
    accelerator = AcceleratorOptions(device="cpu", num_threads=4)
    start = time.monotonic()
    if phase == "page":
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.pipeline.vlm_pipeline import VlmPipeline
        pipeline_options = VlmPipelineOptions(vlm_options=options, accelerator_options=accelerator,
            artifacts_path=HERE / "artifacts", generate_page_images=True, generate_picture_images=False,
            images_scale=1.0, enable_remote_services=False)
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_cls=VlmPipeline, pipeline_options=pipeline_options)})
        converter.initialize_pipeline(InputFormat.PDF)
        pipeline = next(iter(converter.initialized_pipelines.values()))
        stage = pipeline.build_pipe[0]
        state = instrument(stage.engine, out)
        load_seconds = time.monotonic() - start
        result = converter.convert(REPO / job["source"]["path"], page_range=(job["physical_page_1based"], job["physical_page_1based"]))
        (out / "conversion-result.json").write_text(result.model_dump_json(indent=2))
        result.document.save_as_json(out / "document.json")
        (out / "document.md").write_text(result.document.export_to_markdown())
        page = result.pages[0]
        page.image.save(out / "pipeline-page-image.png")
        parse(state["token_aware"], page.image, out, "token-aware-parser-candidate")
        save(out / "source-mapping.json", {"original_source": job["source"], "original_physical_page_1based": job["physical_page_1based"],
            "actual_pipeline_page_no": page.page_no, "source_page_size_points": page.size.model_dump(mode="json"),
            "pipeline_page_image_pixels_wh": page.image.size, "official_parser_pages": {str(k): v.size.model_dump(mode="json") for k, v in result.document.pages.items()},
            "mapping_rule": "Official parser uses image pixels and isolated page1; map x/y by original PDF point width/height divided by parser image width/height, preserve original physical page separately. No page/coordinate repair applied."})
        method_options = pipeline_options.model_dump(mode="json", serialize_as_any=True)
        status = str(result.status)
    else:
        image = Image.open(REPO / job["image_path"]).convert("RGB")
        stage = VlmConvertModel(enabled=True, enable_remote_services=False, artifacts_path=HERE / "artifacts", options=options, accelerator_options=accelerator)
        state = instrument(stage.engine, out)
        load_seconds = time.monotonic() - start
        outputs = stage.engine.predict_batch([VlmEngineInput(image=image, prompt=options.model_spec.prompt,
            temperature=0, max_new_tokens=1024, extra_generation_config={"skip_special_tokens": False})])
        parse(outputs[0].text, image, out, "official-parser-component")
        parse(state["token_aware"], image, out, "token-aware-parser-candidate")
        save(out / "source-mapping.json", {"producer_candidate": job, "parser_coordinates": "paragraph PNG pixels; isolated parser page1",
             "mapping_rule": "Use frozen producer fragment placement and per-fragment pixel→original physical PDF transform. A stitched paragraph may span multiple source pages; do not pretend paragraph page1 is original source page."})
        method_options, status = options.model_dump(mode="json", serialize_as_any=True), "component_completed"
    assert state["calls"] == 1
    save(out / "method.json", {"path": "official VlmPipeline" if phase == "page" else "paragraph engine/prompt/official parser component; not VlmPipeline",
        "options": method_options, "model_repo": DOWNLOAD["repo"], "model_revision": DOWNLOAD["revision"],
        "actual_torch_threads": torch.get_num_threads(), "actual_torch_interop_threads": torch.get_num_interop_threads(),
        "construction_including_model_load_seconds": load_seconds, "total_worker_seconds": time.monotonic() - start,
        "model_calls": state["calls"], "status": status,
        "versions": {p: importlib.metadata.version(p) for p in ["docling", "docling-core", "torch", "transformers"]}})


def main(phase):
    folder = HERE / phase
    expected = json.loads((folder / "frozen-inputs.json").read_text())
    assert frozen(phase) == expected
    (folder / "runs").mkdir(exist_ok=False)
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", DOCLING_DEVICE="cpu", OMP_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false", PYTHONDONTWRITEBYTECODE="1")
    summary = {"phase": phase, "runner_sha256": sha(Path(__file__)), "resource_policy": {"shared_lock": LOCK,
        "available_min_bytes": 8 * 1024**3, "sampled_tree_rss_limit_bytes": LIMIT, "timeout_seconds_per_child": TIMEOUT, "sample_period_seconds": .25}, "jobs": []}
    save(folder / "summary.json", summary)
    for job in jobs(phase):
        out = folder / "runs" / job["id"]
        out.mkdir()
        with open(LOCK, "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            available = psutil.virtual_memory().available
            assert available >= 8 * 1024**3, "Less than 8 GiB available; no model child started"
            command = ["rtk", "proxy", sys.executable, "-B", str(Path(__file__)), "--worker", phase, job["id"]]
            start, peak, stopped = time.monotonic(), 0, None
            print(json.dumps({"start": job["id"], "phase": phase}), flush=True)
            with (out / "child.log").open("wb") as log:
                process = subprocess.Popen(command, cwd=REPO, env=env, stdout=log, stderr=log, start_new_session=True)
                try:
                    while process.poll() is None:
                        try:
                            owner = psutil.Process(process.pid)
                            peak = max(peak, sum(p.memory_info().rss for p in [owner, *owner.children(recursive=True)]))
                        except psutil.NoSuchProcess:
                            pass
                        except (psutil.AccessDenied, PermissionError):
                            stopped = "resource_monitor_unavailable"
                            break
                        if peak > LIMIT or time.monotonic() - start > TIMEOUT:
                            stopped = "sampled_memory_stop" if peak > LIMIT else "timeout"
                            break
                        time.sleep(.25)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            row = {"id": job["id"], "command": command, "child_pid_and_pgid": process.pid,
                   "available_before_bytes": available, "child_wall_seconds": time.monotonic() - start,
                   "sampled_tree_peak_rss_bytes": peak, "exit_code": process.returncode, "stopped": stopped}
            summary["jobs"].append(row)
            save(folder / "summary.json", summary)
            print(json.dumps(row), flush=True)
            if row["exit_code"] or stopped:
                break
    assert frozen(phase) == expected


if __name__ == "__main__":
    if sys.argv[1:] == ["--self-check"]:
        self_check()
    elif len(sys.argv) == 3 and sys.argv[1] == "--freeze":
        phase = sys.argv[2]
        folder = HERE / phase
        folder.mkdir()
        artifacts = HERE / "artifacts"
        artifacts.mkdir(exist_ok=True)
        link = artifacts / "ibm-granite--granite-docling-258M"
        if not link.exists():
            link.symlink_to(SNAPSHOT, target_is_directory=True)
        save(folder / "frozen-inputs.json", frozen(phase))
        print(f"{phase} source/model/runtime/runner bytes frozen; no inference.")
    elif len(sys.argv) == 4 and sys.argv[1] == "--worker":
        assert frozen(sys.argv[2]) == json.loads((HERE / sys.argv[2] / "frozen-inputs.json").read_text())
        worker(sys.argv[2], sys.argv[3])
    else:
        main(sys.argv[1])
