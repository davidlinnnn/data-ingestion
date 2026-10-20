"""Single bounded CPU baseline prerequisite; reuse the frozen G2 conversion worker."""

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
FROZEN_RUNNER = REPO / "docs/research/pdf-core-g2-local-cpu-2026-10-14/run.py"
PROTOTYPE = REPO / "docs/prototypes/pdf-checkpoint-prototype"
JOB = ("controls-p1", "SRC05", 1, False)
OUT = HERE / "controls"
LIMIT, TIMEOUT = 6 * 1024**3, 180


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def worker():
    spec = importlib.util.spec_from_file_location("frozen_g2_local_cpu", FROZEN_RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HERE = OUT
    module.worker(JOB)


def main():
    folder = OUT / "runs" / JOB[0]
    folder.mkdir(parents=True, exist_ok=False)
    available = psutil.virtual_memory().available
    assert available >= 8 * 1024**3, "Less than 8 GiB available before starting child"
    environment = os.environ.copy()
    environment.update(HF_HOME=str(PROTOTYPE / "PROTOTYPE-wipe-me/hf"),
                       HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", DOCLING_DEVICE="cpu",
                       OMP_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false")
    command = ["rtk", "proxy", sys.executable, "-B", str(Path(__file__).resolve()), "--worker"]
    summary = {"purpose": "Old Docling 2.102 CPU baseline prerequisite for SRC05 physical page 1",
               "runner_sha256": sha(Path(__file__)), "frozen_runner_sha256": sha(FROZEN_RUNNER),
               "frozen_experiment_sha256": sha(PROTOTYPE / "experiment.py"),
               "source_id": JOB[1], "original_physical_page": JOB[2],
               "force_full_page_ocr": False, "offline": True, "device": "cpu",
               "threads": 4, "batch_size": 1, "command": command,
               "available_before_bytes": available, "timeout_seconds": TIMEOUT,
               "sampled_tree_rss_stop_bytes": LIMIT, "sample_period_seconds": .25,
               "rss_guard_semantics": "sampled process-tree soft stop; not cgroup peak or hard limit"}
    save(OUT / "summary.json", summary)
    started, peak, samples, stopped = time.monotonic(), 0, 0, None
    with (folder / "child.log").open("wb") as log:
        process = subprocess.Popen(command, cwd=REPO, env=environment, stdout=log, stderr=log,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                try:
                    owner = psutil.Process(process.pid)
                    peak = max(peak, sum(p.memory_info().rss for p in
                               [owner, *owner.children(recursive=True)]))
                    samples += 1
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
    summary.update(seconds_including_process_start_exit=time.monotonic()-started,
                   sampled_tree_peak_rss_bytes=peak, samples=samples,
                   exit_code=process.returncode, stopped=stopped,
                   execution_status="completed" if process.returncode == 0 and stopped is None else "failed")
    save(OUT / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    assert summary["execution_status"] == "completed", summary


if __name__ == "__main__":
    worker() if sys.argv[1:] == ["--worker"] else main()
