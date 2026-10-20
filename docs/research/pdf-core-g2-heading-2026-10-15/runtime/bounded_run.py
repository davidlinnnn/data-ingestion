"""Bound all extraction/stage children together to 180 seconds and 6 GiB sampled RSS."""

import argparse
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil

parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True)
parser.add_argument("--pdf", required=True)
parser.add_argument("--document", required=True)
parser.add_argument("--pages", required=True, type=int)
parser.add_argument("--no-outline-ablation", action="store_true")
args = parser.parse_args()
output = Path(args.output).resolve()
output.mkdir(parents=True, exist_ok=True)
worker = Path(__file__).with_name("heading_stage.py").resolve()
env = os.environ.copy()
env.update({"HF_HOME": "/private/tmp/pdf-core-g2-heading-20261015/hf", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "DOCLING_DEVICE": "cpu", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "TOKENIZERS_PARALLELISM": "false"})
lock_start = time.monotonic()
samples, children = [], []
status = "failed"
stop_reason = None
child = None
with Path("/private/tmp/data-ingestion-pdf-qualification.lock").open("a+") as lock:
    while True:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() - lock_start > 30:
                raise TimeoutError("Qualification lock held for 30 seconds; retry after current worker exits")
            time.sleep(0.2)
    lock_wait = time.monotonic() - lock_start
    start = time.monotonic()
    code_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).resolve(), worker)}
    (output / "execution-method.json").write_text(json.dumps({"runner_sha256": code_hashes, "python": sys.executable, "environment_overrides": {k: env[k] for k in ("HF_HOME", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "DOCLING_DEVICE", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "TOKENIZERS_PARALLELISM")}}, indent=2) + "\n")
    try:
        available = psutil.virtual_memory().available
        if available < 8 * 1024 ** 3:
            raise RuntimeError(f"Available memory below 8 GiB prelaunch gate: {available}")
        for mode in ("capture-fresh", "reload"):
            cmd = ["rtk", "proxy", sys.executable, str(worker), mode, "--output", str(output)]
            if mode == "capture-fresh":
                cmd += ["--pdf", str(Path(args.pdf).resolve()), "--document", str(Path(args.document).resolve()), "--pages", str(args.pages)]
                if args.no_outline_ablation:
                    cmd.append("--no-outline-ablation")
            with (output / f"{mode}.log").open("w") as log:
                child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                children.append({"mode": mode, "command": cmd, "pid": child.pid})
                while child.poll() is None:
                    try:
                        processes = [psutil.Process(child.pid)]
                        processes += processes[0].children(recursive=True)
                        rss = sum(p.memory_info().rss for p in processes if p.is_running())
                    except psutil.NoSuchProcess:
                        rss = 0
                    elapsed = time.monotonic() - start
                    samples.append({"seconds": elapsed, "rss_bytes": rss, "mode": mode})
                    if elapsed > 180 or rss > 6 * 1024 ** 3:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait()
                        raise RuntimeError("180-second/6-GiB execution boundary exceeded")
                    time.sleep(0.05)
                children[-1]["exit_code"] = child.returncode
                if child.returncode:
                    raise RuntimeError(f"{mode} exited {child.returncode}; see {log.name}")
        status = "success"
    except BaseException as error:
        stop_reason = f"{type(error).__name__}: {error}"
        raise
    finally:
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
        record = {"status": status, "seconds": time.monotonic() - start,
                  "lock_wait_seconds_excluded": lock_wait,
                  "stop_reason": stop_reason,
                  "runner_sha256": code_hashes,
                  "available_memory_bytes_prelaunch": locals().get("available"),
                  "max_sampled_rss_bytes": max((s["rss_bytes"] for s in samples), default=0),
                  "limits": {"seconds": 180, "sampled_rss_bytes": 6 * 1024 ** 3, "sampling_seconds": 0.05},
                  "lock": "/private/tmp/data-ingestion-pdf-qualification.lock", "children": children, "samples": samples}
        (output / "bounded-execution.json").write_text(json.dumps(record, indent=2) + "\n")
        fcntl.flock(lock, fcntl.LOCK_UN)
print(json.dumps({k: v for k, v in record.items() if k != "samples"}))
