"""Bounded, offline CPU task probes using the existing stock Docling runner."""

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
REPO = HERE.parents[2]
PROTOTYPE = REPO / "docs/prototypes/pdf-checkpoint-prototype"
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
JOBS = [
    ("memory-r1-p8", "SRC06", 8, False),
    ("skillopt-p8", "SRC07", 8, False),
    ("seal-p4", "SRC11", 4, False),
    ("nccu-p3-native", "SRC03", 3, False),
    ("nccu-p3-full-ocr", "SRC03", 3, True),
    ("english-scan-p1-ocr", "SRC04", 1, True),
]
LIMIT = 6 * 1024**3
TIMEOUT = 180


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def worker(job):
    name, source_id, page, scan = job
    source = next(s for s in json.loads(REGISTRY.read_text())["sources"] if s["id"] == source_id)
    pdf = REPO / source["path"]
    assert sha(pdf) == source["sha256"]
    spec = importlib.util.spec_from_file_location("g2_existing_experiment", PROTOTYPE / "experiment.py")
    experiment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(experiment)
    import torch
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    original_options = experiment.options

    def options(scan=False):
        result = original_options(scan)
        result.layout_batch_size = result.ocr_batch_size = result.table_batch_size = 1
        return result

    experiment.options = options
    original_convert = experiment.DocumentConverter.convert
    out = HERE / "runs" / name

    def observed_convert(self, *args, **kwargs):
        result = original_convert(self, *args, **kwargs)
        # Save the first complete serialized provider result before downstream exports.
        raw = result.model_dump_json(indent=2)
        assert isinstance(json.loads(raw), dict)
        (out / "conversion-result.json").write_text(raw)
        return result

    experiment.DocumentConverter.convert = observed_convert
    sys.argv = [str(PROTOTYPE / "experiment.py"), "baseline", str(pdf), "--out", str(out),
                "--start", str(page), "--end", str(page)] + (["--scan"] if scan else [])
    experiment.main()
    metrics = json.loads((out / "metrics.json").read_text())
    assert metrics["source_sha256"] == source["sha256"]
    assert metrics["page_stage_inputs"]["LayoutModel"] == 1
    method = json.loads((out / "method.json").read_text())
    assert method["options"]["accelerator_options"]["device"] == "cpu"
    assert method["options"]["layout_batch_size"] == 1


def main():
    (HERE / "runs").mkdir(exist_ok=False)
    environment = os.environ.copy()
    environment.update(HF_HOME=str(PROTOTYPE / "PROTOTYPE-wipe-me/hf"), HF_HUB_OFFLINE="1",
                       TRANSFORMERS_OFFLINE="1", DOCLING_DEVICE="cpu", OMP_NUM_THREADS="4",
                       TOKENIZERS_PARALLELISM="false")
    summary = {"scope": "Local macOS CPU diagnostic probes; no Canonical acceptance or SLO qualification",
               "registry_sha256": sha(REGISTRY), "runner_sha256": sha(Path(__file__)),
               "existing_runner_sha256": sha(PROTOTYPE / "experiment.py"),
               "sampled_tree_rss_stop_bytes": LIMIT, "timeout_seconds_per_child": TIMEOUT,
               "offline": True, "device": "cpu", "jobs": []}
    save(HERE / "summary.json", summary)
    for job in JOBS:
        name, source_id, page, scan = job
        folder = HERE / "runs" / name
        folder.mkdir()
        available = psutil.virtual_memory().available
        assert available >= 8 * 1024**3, "Less than 8 GiB available before starting a child"
        command = ["rtk", "proxy", sys.executable, "-B", str(Path(__file__).resolve()), "--worker", name]
        started = time.monotonic()
        peak, stopped = 0, None
        print(json.dumps({"event": "start", "job": name}), flush=True)
        with (folder / "child.log").open("wb") as log:
            process = subprocess.Popen(command, cwd=REPO, env=environment, stdout=log, stderr=log,
                                       start_new_session=True)
            try:
                while process.poll() is None:
                    try:
                        parent = psutil.Process(process.pid)
                        peak = max(peak, sum(p.memory_info().rss for p in
                                   [parent, *parent.children(recursive=True)]))
                    except psutil.NoSuchProcess:
                        pass
                    except (psutil.AccessDenied, PermissionError):
                        stopped = "resource_monitor_unavailable"
                        break
                    if peak > LIMIT:
                        stopped = "sampled_memory_stop"
                        break
                    if time.monotonic() - started > TIMEOUT:
                        stopped = "timeout"
                        break
                    time.sleep(.25)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        row = {"name": name, "source_id": source_id, "original_physical_page": page,
               "force_full_page_ocr": scan, "command": command,
               "available_before_bytes": available, "seconds_including_process_start_exit": time.monotonic()-started,
               "sampled_tree_peak_rss_bytes": peak, "sample_period_seconds": .25,
               "exit_code": process.returncode, "stopped": stopped,
               "execution_status": "completed" if process.returncode == 0 and stopped is None else "failed"}
        summary["jobs"].append(row)
        save(HERE / "summary.json", summary)
        print(json.dumps(row), flush=True)
        if row["execution_status"] != "completed":
            break
    assert sha(REGISTRY) == summary["registry_sha256"]


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker(next(job for job in JOBS if job[0] == sys.argv[2]))
    else:
        main()
