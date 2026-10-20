"""W2 bounded smoke only: frozen two-paper manifest, one native page each."""
import fcntl
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import traceback

import psutil

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASELINE = REPO / "docs/research/pdf-core-native-round-2026-10-17/run.py"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")
    tmp.replace(path)


def cpu():
    r = resource.getrusage(resource.RUSAGE_SELF)
    return r.ru_utime + r.ru_stime


def baseline_options():
    spec = importlib.util.spec_from_file_location("w2_readonly_s0", BASELINE)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    opts = baseline.options("S0")
    for field in ("do_picture_classification", "do_picture_description", "do_chart_extraction",
                  "do_code_enrichment", "do_formula_enrichment"):
        assert getattr(opts, field) is False, field
    assert opts.accelerator_options.num_threads == 4
    assert opts.ocr_batch_size == opts.layout_batch_size == opts.table_batch_size == 1
    assert opts.layout_options.model_spec.revision == "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8"
    return opts


def frozen():
    data = json.loads((HERE / "freeze.json").read_text())
    for rel, expected in data["sha256"].items():
        path = (HERE / rel).resolve()
        assert path.is_relative_to(HERE), rel
        assert sha(path) == expected, f"frozen input changed: {rel}"
    jobs = json.loads((HERE / "smoke-jobs.json").read_text())["jobs"]
    assert len(jobs) == 2 and {j["layout"] for j in jobs} == {"single", "double"}
    for job in jobs:
        assert job["first"] == job["last"]
        assert job["last"] <= 12
        assert sha(HERE / job["pdf"]) == job["pdf_sha256"]
    return jobs


def child():
    import torch
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    from docling.datamodel.settings import settings

    jobs = frozen()
    out = HERE / "smoke"
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    settings.debug.profile_pipeline_timings = True
    opts = baseline_options()
    save(out / "effective-options.json", opts.model_dump(mode="json", serialize_as_any=True))
    save(out / "identity.json", dict(baseline_sha256=sha(BASELINE), runner_sha256=sha(__file__),
        versions={p: importlib.metadata.version(p) for p in (
            "docling-slim", "docling-core", "pypdfium2", "torch", "rapidocr", "psutil")},
        pipeline="StandardPdfPipeline", backend="PyPdfiumDocumentBackend", retries=0,
        independent_ocr_experiments=0, vlm_calls=0, holdout_reads=0))
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
        pipeline_cls=StandardPdfPipeline, pipeline_options=opts, backend=PyPdfiumDocumentBackend)})
    save(out / "stage.json", dict(stage="initialize"))
    wall, used = time.monotonic(), cpu()
    converter.initialize_pipeline(InputFormat.PDF)
    save(out / "initialization.json", dict(wall_seconds=time.monotonic()-wall, cpu_seconds=cpu()-used))
    for job in jobs:
        dest = out / job["id"]
        dest.mkdir(exist_ok=False)
        save(out / "stage.json", dict(stage="convert", job=job["id"]))
        wall, used = time.monotonic(), cpu()
        try:
            result = converter.convert(HERE / job["pdf"], page_range=(job["first"], job["last"]),
                                       raises_on_error=False)
            record = dict(wall_seconds=time.monotonic()-wall, cpu_seconds=cpu()-used,
                          status=result.status.value, errors=[e.model_dump(mode="json") for e in result.errors])
            save(out / "stage.json", dict(stage="save", job=job["id"]))
            start_save = time.monotonic()
            (dest / "result.json").write_text(result.model_dump_json(indent=2, serialize_as_any=True))
            result.document.save_as_json(dest / "document.json")
            (dest / "document.md").write_text(result.document.export_to_markdown())
            save(dest / "timings.json", {k: v.model_dump(mode="json") for k, v in result.timings.items()})
            record["save_wall_seconds"] = time.monotonic()-start_save
        except Exception:
            record = dict(status="error", wall_seconds=time.monotonic()-wall,
                          cpu_seconds=cpu()-used, traceback=traceback.format_exc())
        save(dest / "conversion.json", record)
        print(json.dumps({"job": job["id"], **record}), flush=True)
        if record["status"] != "success":
            raise RuntimeError("smoke stopped on conversion failure; no retries")
    save(out / "stage.json", dict(stage="complete"))


def parent():
    frozen()
    out = HERE / "smoke"
    assert not out.exists(), "preserve existing run; never retry implicitly"
    # Existing baseline lock is opened read-only: no writes outside W2.
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "r") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out.mkdir()
        for name in ("cache", "tmp"):
            (HERE / name).mkdir(exist_ok=True)
        env = os.environ | dict(PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4",
            HF_HOME="/private/tmp/pdf-core-native-20261017/hf", MPLCONFIGDIR=str(HERE / "cache"),
            XDG_CACHE_HOME=str(HERE / "cache"), TMPDIR=str(HERE / "tmp"))
        samples = []
        start = time.monotonic()
        status = "running"
        with (out / "worker.log").open("w") as log:
            proc = subprocess.Popen(["rtk", "proxy", sys.executable, str(Path(__file__).resolve()), "--child"],
                env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                while proc.poll() is None:
                    try:
                        root = psutil.Process(proc.pid)
                        rss = sum(p.memory_info().rss for p in [root]+root.children(recursive=True)
                                  if p.is_running())
                    except psutil.NoSuchProcess:
                        rss = 0
                    stage = json.loads((out / "stage.json").read_text()) if (out / "stage.json").exists() else {}
                    free = psutil.virtual_memory().available
                    samples.append(dict(seconds=time.monotonic()-start, rss=rss, available=free, **stage))
                    if rss > 12*2**30 or free < 8*2**30 or time.monotonic()-start > 900:
                        status = "resource_stop"
                        break
                    time.sleep(0.1)
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                    if status == "running":
                        status = "interrupted"
                elif status == "running":
                    status = "completed" if proc.returncode == 0 else "worker_error"
                save(out / "execution.json", dict(status=status, exit_code=proc.returncode,
                    wall_seconds=time.monotonic()-start, peak_sampled_tree_rss_bytes=max(s["rss"] for s in samples),
                    job_peak_sampled_tree_rss_bytes={j["id"]: max((s["rss"] for s in samples
                        if s.get("job") == j["id"] and s.get("stage") == "convert"), default=0) for j in frozen()},
                    samples=samples))
        print(status)


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        opts = baseline_options()
        assert importlib.metadata.version("docling-slim") == "2.132.0"
        assert importlib.metadata.version("docling-core") == "2.99.0"
        assert not opts.ocr_options.force_full_page_ocr
        print("S0 identity, CPU4/batch1/enrichment-off self-check passed; no models loaded")
    elif sys.argv[1:] == ["--child"]:
        child()
    elif sys.argv[1:] == ["--smoke"]:
        parent()
    else:
        raise SystemExit("Only --selfcheck and frozen --smoke are supported; no full-run command")
