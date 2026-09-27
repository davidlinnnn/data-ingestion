"""Bounded per-task direct-reclaim trace in a private tracefs instance."""

import argparse
import json
import os
from pathlib import Path
import re
import select
import signal
import time


TRACE_ROOT = Path("/sys/kernel/tracing/instances")
LINE = re.compile(
    r"^\s*(?P<comm>.+)-(?P<pid>\d+)\s+\[\d+\].*?\s"
    r"(?P<clock>\d+\.\d+): (?P<event>mm_vmscan_direct_reclaim_(?:begin|end)): "
    r"(?P<details>.*)$"
)


def parse(line):
    match = LINE.match(line)
    if not match:
        return None
    row = match.groupdict()
    row["pid"] = int(row["pid"])
    row["clock"] = float(row["clock"])
    return row


def process_identity(pid):
    root = Path("/proc") / str(pid)
    try:
        status = root.joinpath("status").read_text()
        cgroup = root.joinpath("cgroup").read_text().strip()
    except (FileNotFoundError, ProcessLookupError):
        return {"identity": "exited_before_read"}
    nspid = next((line.split()[1:] for line in status.splitlines()
                  if line.startswith("NSpid:")), [])
    return {"nspid": [int(value) for value in nspid], "cgroup": cgroup}


def run(run_id, seconds):
    name = "q44_" + run_id.replace("-", "_")
    if not re.fullmatch(r"q44_[a-z0-9_]+", name):
        raise ValueError("invalid trace identity")
    directory = TRACE_ROOT / name
    directory.mkdir(exist_ok=False)
    events = [directory / "events/vmscan" / ("mm_vmscan_direct_reclaim_" + edge) / "enable"
              for edge in ("begin", "end")]
    stopped = False

    def stop(_number, _frame):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    fd = None
    try:
        (directory / "tracing_on").write_text("0")
        (directory / "trace_clock").write_text("mono")
        for event in events:
            event.write_text("1")
        fd = os.open(directory / "trace_pipe", os.O_RDONLY | os.O_NONBLOCK)
        (directory / "tracing_on").write_text("1")
        stat = Path(f"/proc/{os.getpid()}/stat").read_text()
        start_ticks = int(stat.rsplit(") ", 1)[1].split()[19])
        print(json.dumps({"kind": "start", "run_id": run_id, "pid": os.getpid(),
                          "start_ticks": start_ticks,
                          "time": time.time(), "monotonic": time.monotonic(),
                          "trace_instance": name,
                          "self_identity": process_identity(os.getpid())}), flush=True)
        end = time.monotonic() + seconds
        pending = ""
        while not stopped and time.monotonic() < end:
            if not select.select([fd], [], [], min(.25, max(0, end-time.monotonic())))[0]:
                continue
            try:
                pending += os.read(fd, 65536).decode(errors="replace")
            except BlockingIOError:
                continue
            *lines, pending = pending.split("\n")
            for line in lines:
                row = parse(line)
                if row:
                    print(json.dumps({"kind": "event", "read_at": time.time(),
                                      **row, **process_identity(row["pid"])}), flush=True)
        print(json.dumps({"kind": "end", "run_id": run_id,
                          "time": time.time(), "stopped_by_signal": stopped}), flush=True)
    finally:
        (directory / "tracing_on").write_text("0")
        for event in events:
            event.write_text("0")
        if fd is not None:
            os.close(fd)
        directory.rmdir()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seconds", type=float, default=1500)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        example = " python-123 [001] ..... 413896.954591: mm_vmscan_direct_reclaim_end: nr_reclaimed=7"
        assert parse(example) == {"comm": "python", "pid": 123,
                                  "clock": 413896.954591,
                                  "event": "mm_vmscan_direct_reclaim_end",
                                  "details": "nr_reclaimed=7"}
    else:
        if args.seconds <= 0:
            raise ValueError("positive trace duration required")
        run(args.run_id, args.seconds)
