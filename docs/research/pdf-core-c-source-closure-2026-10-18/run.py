"""One registered official OCR-mode challenger; no source-specific processing."""
import fcntl
from hashlib import sha256
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
FROZEN = REPO / "docs/research/pdf-core-eval-interfaces-2026-10-18/C"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def options():
    old = load("retained_native_S0", REPO / "docs/research/pdf-core-native-round-2026-10-17/run.py")
    from docling.datamodel.pipeline_options import OcrMode
    value = old.options("S0")
    before = value.model_dump(mode="json", serialize_as_any=True)
    value.ocr_options.mode = OcrMode.FULL_PAGE
    after = value.model_dump(mode="json", serialize_as_any=True)
    expected = json.loads(json.dumps(before))
    expected["ocr_options"].update(mode=after["ocr_options"]["mode"], force_full_page_ocr=True)
    assert after == expected, "only OCR mode and its derived compatibility property may change"
    assert before["ocr_options"]["mode"] != after["ocr_options"]["mode"]
    return value


def verify():
    registration = json.loads((HERE / "registration.json").read_text())
    for path, digest in registration["inputs"].items():
        assert sha256((REPO / path).read_bytes()).hexdigest() == digest, path
    actual = options().model_dump(mode="json", serialize_as_any=True)
    for config in (actual, registration["effective_options"]):
        config["chart_extraction_options"]["model_spec"]["supported_engines"].sort()
    assert actual == registration["effective_options"]
    assets = json.loads((FROZEN / "native-preregistration.json").read_text())["active_asset_hashes"]
    for path, digest in assets.items():
        assert sha256(Path(path).read_bytes()).hexdigest() == digest
    return registration


def child():
    registration = verify()
    import torch
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
        pipeline_cls=StandardPdfPipeline, pipeline_options=options(), backend=PyPdfiumDocumentBackend)})
    begin = time.monotonic()
    converter.initialize_pipeline(InputFormat.PDF)
    write(HERE / "initialization.json", {"seconds": time.monotonic()-begin})
    for job in registration["ranges"]:
        source = REPO / job["source"]["path"]
        assert sha256(source.read_bytes()).hexdigest() == job["source"]["sha256"]
        dest = HERE / "native" / job["range_id"]
        dest.mkdir(parents=True, exist_ok=False)
        begin = time.monotonic()
        result = converter.convert(source, page_range=(job["first"], job["last"]), raises_on_error=False)
        result.document.save_as_json(dest / "document.json")
        (dest / "document.md").write_text(result.document.export_to_markdown())
        record = {"range_id": job["range_id"], "status": result.status.value,
                  "seconds": time.monotonic()-begin, "pages": [p.page_no for p in result.pages]}
        write(dest / "conversion.json", record)
        print(json.dumps(record), flush=True)
        if result.status.value != "success":
            raise RuntimeError("partial conversion; no retry")
    verify()


def parent():
    registration = verify()
    assert not (HERE / "execution.json").exists(), "registered attempt already exists"
    sys.path.insert(0, str(FROZEN))
    from cpu_baseline_v2 import tree_rss
    begin = time.monotonic()
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.update(HF_HOME="/private/tmp/pdf-core-native-20261017/hf", HF_HUB_OFFLINE="1",
               TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4")
    samples, worker, status = [], None, "not_started"
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if psutil.virtual_memory().available < 10*2**30:
                status = "insufficient_prelaunch_memory"
                return
            with (HERE / "worker.log").open("x") as log:
                worker = subprocess.Popen(["rtk", "proxy", sys.executable, "-B", str(Path(__file__).resolve()), "--child"],
                                          stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                status = "running"
                while worker.poll() is None:
                    rss = tree_rss(worker.pid)
                    available = psutil.virtual_memory().available
                    samples.append({"seconds": time.monotonic()-begin, "rss": rss, "available": available})
                    if time.monotonic()-begin >= registration["wall_seconds"] or rss >= 12*2**30 or available < 8*2**30:
                        status = "time_or_memory_budget_stop"
                        break
                    time.sleep(.25)
                if status == "running":
                    status = "completed" if worker.returncode == 0 else "worker_error"
        except Exception:
            status = "parent_harness_error"
            raise
        finally:
            if worker is not None and worker.poll() is None:
                try:
                    os.killpg(worker.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                worker.wait()
            write(HERE / "execution.json", {"status": status, "seconds": time.monotonic()-begin,
                  "exit_code": worker.returncode if worker else None, "samples": samples,
                  "peak_sampled_tree_rss": max((s["rss"] for s in samples), default=0),
                  "new_API_calls": 0, "new_VLM_calls": 0, "retries": 0})
            print(status, flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        child()
    elif sys.argv[1:] == ["--check"]:
        r = verify()
        print(json.dumps({"single_changed_option": "ocr_options.mode", "pages": sum(j["last"]-j["first"]+1 for j in r["ranges"]), "API_calls": 0}))
    elif sys.argv[1:] == ["--live"]:
        parent()
    else:
        raise SystemExit("use --check, --live or --child")
