"""Trace one object-service memory stall with its cgroup and VM counters."""

import argparse
import json
import os
from pathlib import Path
import re
import select
import signal
import time


ROOT = Path("/sys/kernel/tracing/instances")
VM_KEYS = {"pswpin", "pswpout", "pgmajfault", "pgfault", "allocstall_movable",
           "allocstall_normal", "pgscan_direct", "compact_stall"}
CG_KEYS = {"anon", "file", "pgfault", "pgmajfault", "workingset_refault_anon",
           "workingset_refault_file", "pgscan_direct", "pgscan_kswapd",
           "pgsteal_direct", "pgsteal_kswapd"}
OBJECT_LIMIT = 1073741824
BLOCKED = 'prev_comm == "minio" && prev_state == 2'


def fields(path, selected):
    return {name: int(value) for name, value in
            (line.split() for line in path.read_text().splitlines())
            if name in selected}


def full_total(path):
    line = next(line for line in path.read_text().splitlines() if line.startswith("full "))
    return int(next(value[6:] for value in line.split() if value.startswith("total=")))


def find_object():
    matches = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if (proc / "comm").read_text().strip() != "minio":
                continue
            group = (proc / "cgroup").read_text().strip().split("::", 1)[1]
            path = Path("/sys/fs/cgroup") / group.lstrip("/")
            if ("kubelet-kubepods" in group
                    and (path / "memory.max").read_text().strip() == str(OBJECT_LIMIT)):
                matches.append((int(proc.name), group, path))
        except (FileNotFoundError, ProcessLookupError):
            continue
    if len(matches) > 1:
        raise ValueError("multiple 1Gi MinIO cgroups")
    return matches[0] if matches else None


def snapshot(object_identity):
    row = {"kind": "sample", "time": time.time(),
           "vmstat": fields(Path("/proc/vmstat"), VM_KEYS)}
    if object_identity is None:
        row["object"] = None
        return row
    pid, group, path = object_identity
    try:
        row["object"] = {
            "pid": pid, "cgroup": group,
            "memory_current": int((path / "memory.current").read_text()),
            "memory_max": int((path / "memory.max").read_text()),
            "swap_current": int((path / "memory.swap.current").read_text()),
            "swap_max": (path / "memory.swap.max").read_text().strip(),
            "full_total_us": full_total(path / "memory.pressure"),
            "events": fields(path / "memory.events", {"high", "max", "oom", "oom_kill"}),
            "stat": fields(path / "memory.stat", CG_KEYS),
        }
    except FileNotFoundError:
        row["object"] = {"identity": "removed", "pid": pid, "cgroup": group}
    return row


def run(run_id, seconds):
    name = "q44_" + run_id.replace("-", "_")
    if not re.fullmatch(r"q44_[a-z0-9_]+", name):
        raise ValueError("invalid trace identity")
    directory = ROOT / name
    directory.mkdir(exist_ok=False)
    events = [directory / "events" / subsystem / event / "enable" for subsystem, event in (
        ("vmscan", "mm_vmscan_direct_reclaim_begin"),
        ("vmscan", "mm_vmscan_direct_reclaim_end"),
        ("vmscan", "mm_vmscan_memcg_reclaim_begin"),
        ("vmscan", "mm_vmscan_memcg_reclaim_end"),
        ("compaction", "mm_compaction_begin"),
        ("compaction", "mm_compaction_end"),
        ("sched", "sched_switch"),
    )]
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
        sched = directory / "events/sched/sched_switch"
        (sched / "filter").write_text(BLOCKED)
        (sched / "trigger").write_text("stacktrace if " + BLOCKED)
        for event in events:
            event.write_text("1")
        fd = os.open(directory / "trace_pipe", os.O_RDONLY | os.O_NONBLOCK)
        (directory / "tracing_on").write_text("1")
        pid = os.getpid()
        stat = Path(f"/proc/{pid}/stat").read_text()
        start_ticks = int(stat.rsplit(") ", 1)[1].split()[19])
        print(json.dumps({"kind": "start", "run_id": run_id, "pid": pid,
                          "start_ticks": start_ticks, "time": time.time(),
                          "monotonic": time.monotonic(), "instance": name,
                          "self_cgroup": Path(f"/proc/{pid}/cgroup").read_text().strip()}),
              flush=True)
        deadline = time.monotonic() + seconds
        next_sample = time.monotonic()
        next_lookup = time.monotonic()
        object_identity = None
        pending = ""
        while not stopped and time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_lookup and object_identity is None:
                object_identity = find_object()
                next_lookup = now + 1
                if object_identity:
                    print(json.dumps({"kind": "object_found", "time": time.time(),
                                      "pid": object_identity[0],
                                      "cgroup": object_identity[1]}), flush=True)
            if now >= next_sample:
                print(json.dumps(snapshot(object_identity)), flush=True)
                next_sample = now + .2
            if select.select([fd], [], [], min(.1, max(0, next_sample-time.monotonic())))[0]:
                try:
                    pending += os.read(fd, 65536).decode(errors="replace")
                except BlockingIOError:
                    continue
                *lines, pending = pending.split("\n")
                for line in lines:
                    if line:
                        print(json.dumps({"kind": "trace", "read_at": time.time(),
                                          "line": line}), flush=True)
        print(json.dumps(snapshot(object_identity)), flush=True)
        print(json.dumps({"kind": "end", "run_id": run_id,
                          "time": time.time(), "stopped_by_signal": stopped,
                          "buffer_stats": {p.parent.name: p.read_text()
                                           for p in directory.glob("per_cpu/cpu*/stats")}}), flush=True)
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
    parser.add_argument("--seconds", type=float, default=2500)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample"
            path.write_text("some avg10=0.00 total=98\nfull avg10=0.00 total=1990\n")
            assert full_total(path) == 1990
            path.write_text("pgmajfault 13\npgfault 25\nignored 99\n")
            assert fields(path, {"pgmajfault"}) == {"pgmajfault": 13}
        print("object-stall parsers PASS")
    else:
        if args.seconds <= 0:
            raise ValueError("positive trace duration required")
        run(args.run_id, args.seconds)
