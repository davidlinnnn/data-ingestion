"""Bounded diagnostic: record actual PSI memory-stall entry stacks and task identity."""
import argparse
import json
import os
from pathlib import Path
import re
import select
import signal
import time


def identity(tid):
    path = Path("/proc") / str(tid)
    try:
        status = dict(line.split(":", 1) for line in (path / "status").read_text().splitlines())
        return {"tid": tid, "tgid": int(status["Tgid"]),
                "cgroup": (path / "cgroup").read_text().strip(),
                "nspid": [int(x) for x in status.get("NSpid", "").split()],
                "nstgid": [int(x) for x in status.get("NStgid", "").split()],
                "start_ticks": int((path / "stat").read_text().rsplit(") ", 1)[1].split()[19]),
                "tgid_start_ticks": int((Path("/proc") / status["Tgid"].strip() / "stat").read_text().rsplit(") ", 1)[1].split()[19]),
                "name": status["Name"].strip(), "threads": int(status["Threads"])}
    except (FileNotFoundError, ProcessLookupError):
        return {"tid": tid, "absent_at_read": True}


def run(run_id, seconds):
    if not re.fullmatch(r"[a-z0-9-]+", run_id) or seconds <= 0:
        raise ValueError("invalid run identity or duration")
    directory = Path("/sys/kernel/tracing/instances") / ("q44_" + run_id.replace("-", "_"))
    directory.mkdir(exist_ok=False)
    fd = None
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        (directory / "tracing_on").write_text("0")
        (directory / "trace_clock").write_text("mono")
        (directory / "set_ftrace_filter").write_text("psi_memstall_enter")
        (directory / "current_tracer").write_text("function")
        (directory / "options/func_stack_trace").write_text("1")
        fd = os.open(directory / "trace_pipe", os.O_RDONLY | os.O_NONBLOCK)
        print(json.dumps({"kind": "start", "run_id": run_id, "time": time.time(),
                          "monotonic": time.monotonic(), "pid": os.getpid(),
                          "start_ticks": int(Path("/proc/self/stat").read_text().rsplit(") ", 1)[1].split()[19]),
                          "self_cgroup": Path("/proc/self/cgroup").read_text().strip()}), flush=True)
        (directory / "tracing_on").write_text("1")
        deadline = time.monotonic() + seconds
        pending = ""
        seen = set()
        while not stopped and time.monotonic() < deadline:
            if not select.select([fd], [], [], .1)[0]:
                continue
            try:
                pending += os.read(fd, 65536).decode(errors="replace")
            except BlockingIOError:
                continue
            *lines, pending = pending.split("\n")
            for line in lines:
                if not line:
                    continue
                row = {"kind": "trace", "read_at": time.time(), "line": line}
                match = re.search(r"-(\d+)\s+\[", line)
                if match and int(match[1]) not in seen:
                    tid = int(match[1]); seen.add(tid)
                    row["identity"] = identity(tid)
                print(json.dumps(row), flush=True)
        (directory / "tracing_on").write_text("0")
        print(json.dumps({"kind": "end", "run_id": run_id, "time": time.time(),
                          "buffer_stats": {p.parent.name: p.read_text()
                                           for p in directory.glob("per_cpu/cpu*/stats")}}), flush=True)
    finally:
        (directory / "tracing_on").write_text("0")
        if fd is not None:
            os.close(fd)
        (directory / "current_tracer").write_text("nop")
        directory.rmdir()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seconds", type=float, required=True)
    args = parser.parse_args()
    run(args.run_id, args.seconds)
