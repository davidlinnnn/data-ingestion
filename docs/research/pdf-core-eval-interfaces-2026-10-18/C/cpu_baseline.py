"""Fill missing fixed source ranges once using the existing offline S0 CPU profile."""
import fcntl
import hashlib
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
REPO = HERE.parents[3]
OLD = REPO / "docs/research/pdf-core-native-round-2026-10-17"


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def child():
    frozen = json.loads((HERE / "native-preregistration.json").read_text())
    def check_assets():
        for path, expected in frozen["active_asset_hashes"].items():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, path
    check_assets()
    import torch
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    spec = importlib.util.spec_from_file_location("retained_S0", OLD / "run.py")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    opts = old.options("S0")
    actual = opts.model_dump(mode="json", serialize_as_any=True)
    expected = json.loads((OLD / "S0/effective-options.json").read_text())
    comparable = json.loads(json.dumps(actual))
    # This disabled model advertises engines as an unordered SDK set.
    for config in (comparable, expected):
        config["chart_extraction_options"]["model_spec"]["supported_engines"].sort()
    assert comparable == expected, "S0 options drift"
    write(HERE / "native/effective-options.json", actual)
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
        pipeline_cls=StandardPdfPipeline, pipeline_options=opts, backend=PyPdfiumDocumentBackend)})
    begin = time.monotonic()
    converter.initialize_pipeline(InputFormat.PDF)
    write(HERE / "native/initialization.json", {"seconds": time.monotonic()-begin})
    for job in json.loads((HERE / "scope.json").read_text())["ranges"]:
        if job["upstream"] != "fresh_missing_CPU_S0":
            continue
        dst = HERE / "native" / job["range_id"]
        dst.mkdir(exist_ok=False)
        begin = time.monotonic()
        assert hashlib.sha256((REPO / job["source"]["path"]).read_bytes()).hexdigest() == job["source"]["sha256"], "source bytes changed"
        check_assets()
        result = converter.convert(REPO / job["source"]["path"], page_range=(job["first"], job["last"]), raises_on_error=False)
        result.document.save_as_json(dst / "document.json")
        record = {"status": result.status.value, "seconds": time.monotonic()-begin,
                  "range_id": job["range_id"], "pages": [p.page_no for p in result.pages],
                  "errors": [e.model_dump(mode="json") for e in result.errors]}
        write(dst / "conversion.json", record)
        print(json.dumps(record), flush=True)
        if result.status.value != "success":
            raise RuntimeError("partial conversion; no retry")


def parent():
    if (HERE / "cpu-execution.json").exists():
        raise RuntimeError("CPU attempt already exists; never silently rerun inference")
    begin = time.monotonic()
    env = os.environ.copy()
    env.update(HF_HOME="/private/tmp/pdf-core-native-20261017/hf", HF_HUB_OFFLINE="1",
               TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4")
    samples, proc, status = [], None, "not_started"
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if psutil.virtual_memory().available < 10*2**30:
                status = "insufficient_prelaunch_memory"
                return
            with (HERE / "cpu-worker.log").open("x") as log:
                proc = subprocess.Popen(["rtk", "proxy", sys.executable, "-B", str(Path(__file__).resolve()), "--child"],
                                        stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                status = "running"
                while proc.poll() is None:
                    tree = psutil.Process(proc.pid)
                    rss = sum(p.memory_info().rss for p in [tree]+tree.children(recursive=True) if p.is_running())
                    free = psutil.virtual_memory().available
                    samples.append({"seconds": time.monotonic()-begin, "rss": rss, "available": free})
                    if time.monotonic()-begin >= 1500 or rss >= 12*2**30 or free < 8*2**30:
                        status = "time_or_memory_budget_stop"
                        break
                    time.sleep(.25)
                if status == "running":
                    status = "completed" if proc.returncode == 0 else "worker_error"
        except Exception:
            status = "parent_harness_error"
            raise
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            write(HERE / "cpu-execution.json", {"status": status, "seconds": time.monotonic()-begin,
                  "exit_code": proc.returncode if proc else None, "peak_sampled_tree_rss_bytes": max((x["rss"] for x in samples), default=0),
                  "samples": samples, "calls_API": 0, "calls_VLM": 0, "automatic_retries": 0})
            print(status, flush=True)


if __name__ == "__main__":
    child() if sys.argv[1:] == ["--child"] else parent()
