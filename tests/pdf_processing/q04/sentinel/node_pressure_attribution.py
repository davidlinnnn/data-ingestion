"""Read-only kind-node PSI deltas for a bounded Q04 diagnostic window."""

import argparse
import json
import os
from pathlib import Path
import signal
import time


CGROUPS = Path("/sys/fs/cgroup")
NODE = Path("/proc/pressure/memory")


def full_total(raw):
    return int(next(field[6:] for line in raw.splitlines()
                    if line.startswith("full ") for field in line.split()
                    if field.startswith("total=")))


def snapshot():
    groups = {}
    for path in CGROUPS.rglob("memory.pressure"):
        try:
            groups[str(path.relative_to(CGROUPS).parent)] = full_total(path.read_text())
        except FileNotFoundError:
            continue  # A departing Pod can remove its cgroup during the scan.
    return time.time(), full_total(NODE.read_text()), groups


def delta(before, after):
    started, node_before, groups_before = before
    ended, node_after, groups_after = after
    if ended <= started or node_after < node_before:
        raise ValueError("PSI clock or node counter moved backwards")
    if any(groups_after[name] < groups_before[name]
           for name in groups_after.keys() & groups_before.keys()):
        raise ValueError("cgroup PSI counter moved backwards")
    changed = {name: count - groups_before[name]
               for name, count in groups_after.items()
               if name in groups_before and count > groups_before[name]}
    return {"started_at": started, "ended_at": ended,
            "node_full_delta_us": node_after - node_before,
            "cgroup_full_delta_us": changed,
            "new_cgroups": sorted(groups_after.keys() - groups_before.keys()),
            "removed_cgroups": sorted(groups_before.keys() - groups_after.keys())}


def self_test():
    assert full_total("some avg10=0.00 total=3\nfull avg10=1.08 total=120\n") == 120
    row = delta((1, 100, {"pod-a": 5, "old": 1}),
                (2, 120, {"pod-a": 9, "new": 30}))
    assert row["node_full_delta_us"] == 20
    assert row["cgroup_full_delta_us"] == {"pod-a": 4}
    assert row["new_cgroups"] == ["new"] and row["removed_cgroups"] == ["old"]
    try:
        delta((1, 100, {"pod-a": 5}), (2, 120, {"pod-a": 4}))
    except ValueError:
        pass
    else:
        raise AssertionError("cgroup counter regression accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--interval", type=float, default=.25)
    parser.add_argument("--run-id", default="local-diagnostic")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.self_test:
        return
    if args.seconds <= 0 or args.interval <= 0:
        raise ValueError("positive diagnostic duration and interval required")
    stopped = False
    def request_stop(_signal, _frame):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, request_stop)
    pid = os.getpid()
    start_ticks = int(Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()[19])
    end = time.monotonic() + args.seconds
    previous = snapshot()
    print(json.dumps({"kind": "start", "time": previous[0],
                      "pid": pid, "start_ticks": start_ticks, "run_id": args.run_id,
                      "node_full_total_us": previous[1],
                      "cgroup_count": len(previous[2])}), flush=True)
    while not stopped and time.monotonic() < end:
        time.sleep(min(args.interval, max(0, end - time.monotonic())))
        current = snapshot()
        row = delta(previous, current)
        if row["node_full_delta_us"] or row["cgroup_full_delta_us"]:
            print(json.dumps(row), flush=True)
        previous = current
    print(json.dumps({"kind": "end", "time": previous[0],
                      "stopped_by_signal": stopped,
                      "node_full_total_us": previous[1],
                      "cgroup_count": len(previous[2])}), flush=True)


if __name__ == "__main__":
    main()
