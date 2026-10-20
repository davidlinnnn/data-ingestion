"""One official RapidOCR PP-OCRv5 server pair; retained guard, no SDK modifications."""
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
GUARD = HERE.parent / "pdf-core-eval-interfaces-2026-10-18/C"
PROFILES = ("V5",)
BASE = HERE.parent / "pdf-core-ocr-regression-2026-10-19"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")
    temporary.replace(path)


def retained():
    path = HERE.parent / "pdf-core-native-round-2026-10-17/run.py"
    spec = importlib.util.spec_from_file_location("retained_native_options", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def options(profile):
    from rapidocr import ModelType, OCRVersion
    assert profile == "V5"
    value = retained().options("S0")
    receipt = read(HERE / "model-receipt.json")
    value.ocr_options.det_model_path = receipt["models"]["det"]["path"]
    value.ocr_options.rec_model_path = receipt["models"]["rec"]["path"]
    value.ocr_options.rapidocr_params.update({
        "Det.ocr_version": OCRVersion.PPOCRV5, "Det.model_type": ModelType.SERVER,
        "Rec.ocr_version": OCRVersion.PPOCRV5, "Rec.model_type": ModelType.SERVER})
    return value


def effective(profile):
    value = options(profile).model_dump(mode="json", serialize_as_any=True)
    # Pydantic serializes this set in process-dependent order; order has no meaning.
    value["chart_extraction_options"]["model_spec"]["supported_engines"].sort()
    return value


def verify():
    registration = read(HERE / "registration.json")
    for path, digest in registration["hashes"].items():
        assert sha(path) == digest, f"frozen input changed: {path}"
    for name, version in registration["runtime"].items():
        assert importlib.metadata.version(name) == version, name
    assert {p: effective(p) for p in PROFILES} == registration["profiles"]
    return registration


def stage(out, job, seconds):
    write(out / "stage.json", {"job": job, "started": time.monotonic(), "limit": seconds})


def worker(profile):
    registration = verify()
    import torch
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.settings import settings
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    settings.debug.profile_pipeline_timings = True
    out = HERE / profile
    stage(out, "initialize", 180)
    begin = time.monotonic()
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
        pipeline_cls=StandardPdfPipeline, pipeline_options=options(profile), backend=PyPdfiumDocumentBackend)})
    converter.initialize_pipeline(InputFormat.PDF)
    write(out / "initialization.json", {"seconds": time.monotonic() - begin})
    from omegaconf import OmegaConf
    pipeline = converter._get_pipeline(InputFormat.PDF)
    reader = pipeline.ocr_model.reader
    config = OmegaConf.to_container(reader.cfg, resolve=True, enum_to_str=True)
    for key in ("Det", "Cls", "Rec"):
        config[key]["ocr_version"] = reader.cfg[key].ocr_version.value
        config[key]["model_type"] = reader.cfg[key].model_type.value
    sessions = {key: model.session.session for key, model in (
        ("det", reader.text_det), ("cls", reader.text_cls), ("rec", reader.text_rec))}
    for key in ("Det", "Rec"):
        assert config[key]["ocr_version"] == "PP-OCRv5"
        assert config[key]["model_type"] == "server"
        assert config[key]["model_path"] == registration["model_receipt"]["models"][key.lower()]["path"]
    assert all(session.get_providers() == ["CPUExecutionProvider"] for session in sessions.values())
    assert config["Cls"]["model_path"] == options(profile).ocr_options.cls_model_path
    assert reader.text_rec.session.have_key()
    dictionary = reader.text_rec.session.get_character_list()
    (out / "recognizer-dictionary.txt").write_text("\n".join(dictionary) + "\n")
    write(out / "actual-models.json", {"resolved_config": config,
        "providers": {k: v.get_providers() for k, v in sessions.items()},
        "models": {key: {"path": config[key]["model_path"], "sha256": sha(config[key]["model_path"])}
                   for key in ("Det", "Cls", "Rec")},
        "recognizer_dictionary": {"source": "producer ONNX metadata", "embedded_characters": len(dictionary),
            "ctc_decoding_characters": len(reader.text_rec.postprocess_op.character),
            "sha256": sha(out / "recognizer-dictionary.txt")}})
    for job in registration["jobs"]:
        destination = out / job["id"]
        destination.mkdir(exist_ok=False)
        stage(out, job["id"], 180)
        settings.debug.debug_output_path = str(destination / "debug")
        settings.debug.visualize_raw_layout = True
        settings.debug.visualize_ocr = True
        settings.debug.visualize_layout = True
        write(destination / "attempt.json", {"source": job["pdf"], "attempt": 1, "automatic_retries": 0})
        begin = time.monotonic()
        try:
            result = converter.convert(Path(job["pdf"]), page_range=(1, 1), raises_on_error=False)
            write(destination / "result.json", result.model_dump(mode="json", serialize_as_any=True))
            assert len(result.pages) == 1 and result.document is not None, "no complete single-page result"
            result.document.save_as_json(destination / "document.json")
            (destination / "document.md").write_text(result.document.export_to_markdown())
            cells = [v.model_dump(mode="json") for v in result.pages[0].parsed_page.textline_cells]
            write(destination / "cells.json", cells)
            if profile == "R0" and job["id"] == "known":
                old = read(HERE.parent / "pdf-core-ocr-boundary-trace-2026-10-19/live/result.json")
                actual = result.document.model_dump(mode="json")
                control = {"cells": cells == old["pages"][0]["parsed_page"]["textline_cells"],
                    **{key: actual[key] == old["document"][key] for key in ("texts", "body", "furniture")},
                    "markdown": (destination / "document.md").read_bytes() == (HERE.parent / "pdf-core-ocr-boundary-trace-2026-10-19/live/document.md").read_bytes()}
                write(destination / "control.json", control)
            record = {"status": result.status.value, "cell_count": len(cells),
                "timings": {k: v.model_dump(mode="json") for k, v in result.timings.items()},
                "errors": [v.model_dump(mode="json") for v in result.errors]}
        except Exception as error:
            record = {"status": "error", "type": type(error).__name__, "message": str(error)}
        record["seconds"] = time.monotonic() - begin
        write(destination / "execution.json", record)
        if profile == "R0" and job["id"] == "known":
            assert record["status"] == "success" and all(read(destination / "control.json").values()), "R0 control failed; no more inference"
        print(json.dumps({"profile": profile, "job": job["id"], "status": record["status"],
            "seconds": record["seconds"]}), flush=True)
    stage(out, "complete", 10)
    verify()


def parent(profile):
    verify()
    assert all(read(BASE / "R0/known/control.json").values()), "retained R0 control required"
    sys.path.insert(0, str(GUARD))
    from cpu_baseline_v2 import tree_rss
    out = HERE / profile
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.update(HF_HOME="/private/tmp/pdf-core-native-20261017/hf", HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4", OMP_THREAD_LIMIT="4")
    samples, process, status = [], None, "not_started"
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out.mkdir(exist_ok=False)
        begin = time.monotonic()
        try:
            if psutil.virtual_memory().available < 10 * 2**30:
                status = "insufficient_prelaunch_memory"
                return
            with (out / "worker.log").open("x") as log:
                process = subprocess.Popen(["rtk", "proxy", sys.executable, "-B", str(Path(__file__).resolve()), "--worker", profile],
                    stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                status = "running"
                while process.poll() is None:
                    now = time.monotonic()
                    current = read(out / "stage.json") if (out / "stage.json").exists() else {"started": begin, "limit": 180, "job": "imports"}
                    rss, available = tree_rss(process.pid), psutil.virtual_memory().available
                    samples.append({"seconds": now - begin, "job": current["job"], "rss": rss, "available": available})
                    if now - begin >= 900 or now - current["started"] >= current["limit"] or rss >= 12 * 2**30 or available < 8 * 2**30:
                        status = "time_or_memory_budget_stop"
                        break
                    time.sleep(.25)
                if status == "running":
                    status = "completed" if process.returncode == 0 else "worker_error"
        except Exception:
            status = "parent_harness_error"
            raise
        finally:
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            write(out / "execution.json", {"status": status, "seconds": time.monotonic() - begin,
                "exit_code": process.returncode if process else None, "samples": samples,
                "peak_sampled_tree_rss_bytes": max((s["rss"] for s in samples), default=0),
                "API_calls": 0, "automatic_retries": 0})
            print(profile, status, flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2 and args[0] in ("--run", "--worker") and args[1] in PROFILES:
        (parent if args[0] == "--run" else worker)(args[1])
    elif args == ["--check"]:
        verify()
        print("Frozen inputs/options/runtime verified; zero inference.")
    else:
        raise SystemExit("use --check or --run/--worker V5")
