"""Revision of the CPU supervisor; the original experiment remains frozen."""
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import psutil

from cpu_baseline import HERE, child, write


def tree_rss(pid):
    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return 0
    processes = [root]
    try:
        processes += root.children(recursive=True)
    except psutil.NoSuchProcess:
        pass
    rss = 0
    for process in processes:
        try:
            rss += process.memory_info().rss
        except psutil.NoSuchProcess:
            # Enumeration cannot prevent a process exiting before its RSS read.
            continue
    return rss


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
                    rss = tree_rss(proc.pid)
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
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            write(HERE / "cpu-execution.json", {"status": status, "seconds": time.monotonic()-begin,
                  "exit_code": proc.returncode if proc else None, "peak_sampled_tree_rss_bytes": max((x["rss"] for x in samples), default=0),
                  "samples": samples, "calls_API": 0, "calls_VLM": 0, "automatic_retries": 0})
            print(status, flush=True)


if __name__ == "__main__":
    child() if sys.argv[1:] == ["--child"] else parent()
