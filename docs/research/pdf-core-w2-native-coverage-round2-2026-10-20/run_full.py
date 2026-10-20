"""Sequential S0 conversion, bounded supervision, observation only, no retry."""
import fcntl
import gc
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
import threading
import time
import traceback

import psutil

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "pdf-core-w2-native-coverage-2026-10-20"
JOBS = json.loads((HERE / "jobs.json").read_text())["jobs"]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8388608), b""):
            h.update(block)
    return h.hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str)+"\n")
    temp.replace(path)


def cpu():
    used = resource.getrusage(resource.RUSAGE_SELF)
    return used.ru_utime + used.ru_stime


def options():
    spec = importlib.util.spec_from_file_location("readonly_round1_runner", OLD / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.baseline_options()


def verify_registration():
    reg = json.loads((HERE / "registration.json").read_text())
    for rel, digest in reg["method_sha256"].items():
        assert sha(HERE / rel) == digest, rel
    for job in JOBS:
        assert sha(job["pdf"]) == job["pdf_sha256"], job["id"]
    return reg


def stage(name, job=None, limit=180):
    save(HERE / "stage.json", dict(stage=name, job=job, started=time.monotonic(), limit=limit))


def worker(start_index):
    import torch
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline, ThreadedPipelineStage, PreprocessThreadedStage
    from docling.datamodel.settings import settings

    verify_registration()
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    settings.debug.profile_pipeline_timings = True
    opts = options()
    save(HERE / "effective-options.json", opts.model_dump(mode="json", serialize_as_any=True))
    save(HERE / "runtime-identity.json", dict(
        versions={p: importlib.metadata.version(p) for p in ("docling-slim", "docling-core", "torch", "pypdfium2", "rapidocr")},
        runner_sha256=sha(__file__), models_unchanged=True, torch_threads=torch.get_num_threads(),
        torch_interop_threads=torch.get_num_interop_threads(), pipeline="StandardPdfPipeline", backend="PyPdfiumDocumentBackend"))
    current = {}
    event_lock = threading.Lock()

    def observe(original):
        def wrapped(self, batch):
            if not batch:
                return original(self, batch)
            begin = time.monotonic()
            result = original(self, batch)
            end = time.monotonic()
            events = [dict(stage=self.name, page=it.page_no, start=begin, end=end,
                           wall_seconds=end-begin, failed=bool(it.is_failed)) for it in result]
            with event_lock:
                current["events"].extend(events)
                if self.name == "layout":
                    for it in result:
                        if it.payload is not None and it.payload.predictions.layout is not None:
                            current["raw_layout"][str(it.page_no)] = it.payload.predictions.layout.model_dump(mode="json")
            return result
        return wrapped

    ThreadedPipelineStage._process_batch = observe(ThreadedPipelineStage._process_batch)
    PreprocessThreadedStage._process_batch = observe(PreprocessThreadedStage._process_batch)
    stage("initialize", limit=180)
    begin, used = time.monotonic(), cpu()
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
        pipeline_cls=StandardPdfPipeline, pipeline_options=opts, backend=PyPdfiumDocumentBackend)})
    converter.initialize_pipeline(InputFormat.PDF)
    pipeline = converter._get_pipeline(doc_format=InputFormat.PDF)
    save(HERE / f"initialization-{start_index:02d}.json", dict(wall_seconds=time.monotonic()-begin, cpu_seconds=cpu()-used))
    save(HERE / "reading-order-options.json", pipeline.reading_order_model.options.model_dump(mode="json"))
    for job in JOBS[start_index:]:
        dest = HERE / "jobs" / job["id"]
        dest.mkdir(exist_ok=False)
        stage("conversion", job["id"], job["baseline_timeout_seconds"])
        current.update(events=[], raw_layout={})
        begin, used = time.monotonic(), cpu()
        result = None
        try:
            result = converter.convert(Path(job["pdf"]), page_range=(job["first"], job["last"]), raises_on_error=False)
            record = dict(status=result.status.value, errors=[e.model_dump(mode="json") for e in result.errors],
                          wall_seconds=time.monotonic()-begin, cpu_seconds=cpu()-used,
                          pages_returned=len(result.pages))
            stage("saving", job["id"], job["baseline_timeout_seconds"])
            save_start = time.monotonic()
            save(dest / "stage-events.json", current["events"])
            save(dest / "layout-raw.json", current["raw_layout"])
            shapes = {}
            for page in result.pages:
                shapes[str(page.page_no)] = {name: [x.model_dump(mode="json") if hasattr(x, "model_dump") else x
                    for x in (getattr(page, name, None) or [])] for name in ("_shape_lines", "_shape_bounding_boxes")}
            save(dest / "private-shapes.json", shapes)
            (dest / "result.json").write_text(result.model_dump_json(indent=2, serialize_as_any=True))
            if result.document is not None:
                result.document.save_as_json(dest / "document.json")
                (dest / "document.md").write_text(result.document.export_to_markdown())
            save(dest / "timings.json", {k: v.model_dump(mode="json") for k, v in result.timings.items()})
            record["save_wall_seconds"] = time.monotonic()-save_start
        except Exception:
            record = dict(status="error", wall_seconds=time.monotonic()-begin, cpu_seconds=cpu()-used,
                          traceback=traceback.format_exc())
            save(dest / "stage-events.json", current.get("events", []))
            save(dest / "layout-raw.json", current.get("raw_layout", {}))
        save(dest / "conversion.json", dict(id=job["id"], first=job["first"], last=job["last"], retries=0, **record))
        print(json.dumps({"id": job["id"], **record}), flush=True)
        del result
        current.clear()
        gc.collect()
    stage("complete", limit=30)


def stop_reason(rss, available, elapsed, limit, deadline):
    if time.time() >= deadline:
        return "round_budget_stop"
    if rss > 8*2**30:
        return "rss_stop"
    if available < 4*2**30:
        return "available_memory_stop"
    if elapsed > limit:
        return "document_timeout"


def parent():
    reg = verify_registration()
    assert not (HERE / "execution.json").exists(), "one registered execution only; no implicit retry"
    (HERE / "jobs").mkdir(exist_ok=True)
    for name in ("cache", "tmp"):
        (HERE / name).mkdir(exist_ok=True)
    env = os.environ | dict(PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4", HF_HOME="/private/tmp/pdf-core-native-20261017/hf",
        MPLCONFIGDIR=str(HERE / "cache"), XDG_CACHE_HOME=str(HERE / "cache"), TMPDIR=str(HERE / "tmp"))
    begin = time.monotonic()
    all_samples, stops = [], []
    index, final_status = 0, "completed"
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "r") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while index < len(JOBS):
            if psutil.virtual_memory().available < 4*2**30 or time.time() >= reg["deadline_epoch"]:
                final_status = "prelaunch_resource_or_budget_stop"
                break
            stage("initialize", limit=180)
            with (HERE / f"worker-{index:02d}.log").open("w") as log:
                proc = subprocess.Popen(["rtk", "proxy", sys.executable, str(Path(__file__).resolve()), "--child", str(index)],
                    env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                reason = None
                try:
                    while proc.poll() is None:
                        try:
                            root = psutil.Process(proc.pid)
                            rss = sum(p.memory_info().rss for p in [root]+root.children(recursive=True) if p.is_running())
                        except psutil.NoSuchProcess:
                            rss = 0
                        state = json.loads((HERE / "stage.json").read_text())
                        available = psutil.virtual_memory().available
                        all_samples.append(dict(monotonic=time.monotonic(), rss=rss, available=available, **state))
                        reason = stop_reason(rss, available, time.monotonic()-state["started"], state["limit"], reg["deadline_epoch"])
                        if reason:
                            break
                        time.sleep(0.1)
                finally:
                    if proc.poll() is None:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
                if proc.returncode == 0 and reason is None:
                    index = len(JOBS)
                    break
                state = json.loads((HERE / "stage.json").read_text())
                jobid = state.get("job")
                reason = reason or "worker_error"
                stops.append(dict(reason=reason, job=jobid, exit_code=proc.returncode))
                if jobid is not None:
                    failed_index = next(i for i,j in enumerate(JOBS) if j["id"] == jobid)
                    dest = HERE / "jobs" / jobid
                    dest.mkdir(exist_ok=True)
                    if not (dest / "conversion.json").exists():
                        save(dest / "conversion.json", dict(id=jobid, status=reason, retries=0))
                    index = failed_index+1
                else:
                    final_status = reason
                    break
                if reason in {"available_memory_stop", "round_budget_stop"}:
                    final_status = reason
                    break
        save(HERE / "execution.json", dict(status=final_status, wall_seconds=time.monotonic()-begin,
            registered_jobs=len(JOBS), finished_records=sum((HERE/"jobs"/j["id"]/"conversion.json").exists() for j in JOBS),
            peak_sampled_tree_rss_bytes=max((s["rss"] for s in all_samples), default=0), stops=stops,
            samples=all_samples, automatic_retries=0))
    print(final_status, flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        assert len(JOBS) == 36 and sum(j["last"]-j["first"]+1 for j in JOBS) == 715
        assert stop_reason(9*2**30, 9*2**30, 1, 180, time.time()+30) == "rss_stop"
        assert stop_reason(1, 3*2**30, 1, 180, time.time()+30) == "available_memory_stop"
        assert stop_reason(1, 9*2**30, 181, 180, time.time()+30) == "document_timeout"
        assert stop_reason(1, 9*2**30, 1, 180, time.time()-1) == "round_budget_stop"
        assert stop_reason(1, 9*2**30, 1, 180, time.time()+30) is None
        assert options().accelerator_options.num_threads == 4
        print("36/715 registration, S0, timeout/RSS/available/budget guards checked; no inference")
    elif sys.argv[1:2] == ["--child"]:
        worker(int(sys.argv[2]))
    elif sys.argv[1:] == ["--run"]:
        parent()
    else:
        raise SystemExit("Use --selfcheck or --run")
