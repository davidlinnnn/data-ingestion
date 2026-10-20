"""Official cell-matching ablation on registered original PDF page intervals."""
import datetime
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
W3 = HERE.parent / "pdf-core-w3-structured-elements-2026-10-20"
PYTHON = "/private/tmp/pdf-core-native-std-20261017/venv/bin/python"
DEADLINE = datetime.datetime.fromisoformat("2026-10-20T13:35:36+00:00").timestamp()


def save(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temp.replace(path)


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    for name, digest in load(HERE / "oracle-freeze.json")["files_sha256"].items():
        assert sha(HERE / name) == digest, name


def child(job_id):
    verify()
    from docling.datamodel.pipeline_options import HeadingHierarchyOptions
    spec = importlib.util.spec_from_file_location("w3_readonly_worker", W3 / "worker.py")
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    original = worker.options
    plan = next(d for d in load(HERE / "cell-plan.json")["documents"] if d["job_id"] == job_id)
    assert sha(Path(plan["pdf"])) == plan["pdf_sha256"]
    dest = HERE / "cell-runs" / job_id

    def options():
        opts = original()
        opts.generate_page_images = False
        opts.generate_picture_images = False
        opts.heading_hierarchy_options = HeadingHierarchyOptions(enabled=True, use_bookmarks=True, use_numbering=False, use_style=False)
        opts.table_structure_options.do_cell_matching = False
        assert opts.accelerator_options.num_threads == 4
        assert not any((opts.do_code_enrichment, opts.do_formula_enrichment, opts.do_picture_description, opts.do_picture_classification, opts.do_chart_extraction, opts.enable_remote_services))
        save(dest / "option-diff.json", dict(only_effective_change_from_research_E0="table_structure_options.do_cell_matching: True -> False", source_pages="Original PDF with page_range; no rewritten PDF", images="off, as memory-safe research baseline", driver_sha256=sha(Path(__file__))))
        return opts

    worker.HERE = dest
    worker.JOBS = plan["interval_jobs"]
    worker.options = options
    worker.verify_registration = verify
    worker.worker(0)


def parent():
    verify()
    plan = load(HERE / "cell-plan.json")
    root = HERE / "cell-runs"
    root.mkdir(exist_ok=False)
    records = []
    began = time.monotonic()
    env = os.environ | dict(PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4", HF_HOME="/private/tmp/pdf-core-native-20261017/hf", MPLCONFIGDIR=str(HERE / "cache"), XDG_CACHE_HOME=str(HERE / "cache"), TMPDIR=str(HERE / "tmp"))
    for directory in (HERE / "cache", HERE / "tmp"):
        directory.mkdir(exist_ok=True)
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "r") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for document in plan["documents"]:
            if time.time() >= DEADLINE or psutil.virtual_memory().available < 4 * 2**30 or (HERE / "stop-after-current").exists():
                break
            job_id = document["job_id"]
            dest = root / job_id
            dest.mkdir()
            (dest / "jobs").mkdir()
            save(dest / "stage.json", dict(stage="initialize", job=job_id, started=time.monotonic(), limit=180))
            samples, reason = [], None
            started = time.monotonic()
            with (dest / "process.log").open("w") as log:
                process = subprocess.Popen(["rtk", "proxy", PYTHON, "-B", str(Path(__file__).resolve()), "--child", job_id], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    while process.poll() is None:
                        try:
                            current = psutil.Process(process.pid)
                            processes = [current] + current.children(recursive=True)
                            rss = sum(p.memory_info().rss for p in processes if p.is_running())
                            cpu = sum(sum(p.cpu_times()[:2]) for p in processes if p.is_running())
                        except psutil.NoSuchProcess:
                            rss, cpu = 0, 0
                        available = psutil.virtual_memory().available
                        stage = load(dest / "stage.json")
                        samples.append(dict(monotonic=time.monotonic(), rss=rss, cpu_seconds=cpu, available=available, stage=stage["stage"]))
                        if rss > 12 * 2**30:
                            reason = "rss_stop"
                        elif available < 4 * 2**30:
                            reason = "available_memory_stop"
                        elif time.time() >= DEADLINE:
                            reason = "budget_stop"
                        elif time.monotonic() - stage["started"] > stage["limit"]:
                            reason = "document_timeout"
                        if reason:
                            break
                        time.sleep(.1)
                except KeyboardInterrupt:
                    reason = "explicit_stop"
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    outputs = [dict(path=str(path.relative_to(HERE)), **load(path)) for path in sorted((dest / "jobs").glob("*/conversion.json"))]
                    record = dict(job_id=job_id, stop=reason, exit_code=process.returncode, attempt_wall_seconds=time.monotonic()-started,
                                  peak_tree_rss_bytes=max((s["rss"] for s in samples), default=None),
                                  min_available_bytes=min((s["available"] for s in samples), default=None), outputs=outputs)
                    save(dest / "supervision.json", dict(**record, samples=samples))
                    records.append(record)
                    save(root / "progress.json", dict(records=records, planned_documents=len(plan["documents"])))
                    print(json.dumps({k:v for k,v in record.items() if k != "outputs"}), flush=True)
            if reason in ("budget_stop", "available_memory_stop", "explicit_stop"):
                break
    save(root / "execution.json", dict(records=records, wall_seconds=time.monotonic()-began, planned_documents=len(plan["documents"]), automatic_retries=0))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--child"]:
        child(sys.argv[2])
    elif sys.argv[1:] == ["--run"]:
        parent()
    else:
        raise SystemExit("--run or --child JOB_ID")
