"""Finish the current child under guards while the W3 parent is paused."""
import datetime
import json
import os
from pathlib import Path
import signal
import time

import psutil

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/E1_sampled_v2"
PARENT_PID = 71653


def main():
    parent = psutil.Process(PARENT_PID)
    assert parent.status() == psutil.STATUS_STOPPED
    assert parent.cmdline()[-2:] == ["--run", "E1_sampled_v2"]
    stage = json.loads((RUN / "stage.json").read_text())
    job = stage["job"]
    children = parent.children(recursive=True)
    samples = []
    reason = "finish_current_before_budget_stop"
    while True:
        processes = []
        for process in children:
            try:
                if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                    processes.append(process)
            except psutil.NoSuchProcess:
                pass
        if not processes:
            break
        try:
            rss = sum(p.memory_info().rss for p in processes)
            cpu = sum(sum(p.cpu_times()[:2]) for p in processes)
        except psutil.NoSuchProcess:
            continue
        available = psutil.virtual_memory().available
        samples.append(dict(monotonic=time.monotonic(), rss=rss, cpu_seconds=cpu, available=available))
        if rss > 12 * 2**30 or available < 4 * 2**30 or time.monotonic() - stage["started"] > stage["limit"]:
            reason = "active_child_resource_or_timeout_guard"
            for process in reversed(processes):
                try:
                    process.kill()
                except psutil.NoSuchProcess:
                    pass
            break
        time.sleep(.1)
    # Pending SIGINT is delivered on resume, before a next document can launch.
    os.kill(PARENT_PID, signal.SIGINT)
    os.kill(PARENT_PID, signal.SIGCONT)
    result = dict(stopped_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), job_id=job,
                  reason=reason, parent_pid=PARENT_PID,
                  note="Parent paused to prevent next launch; current child completed under continued 12/4GiB guards. These samples cover only the final observation interval; original parent samples for this attempt were not persisted. Conversion wall/CPU remain available in conversion.json. No automatic retry.",
                  peak_observed_tree_rss_bytes=max((s["rss"] for s in samples), default=0),
                  min_observed_available_bytes=min((s["available"] for s in samples), default=None), samples=samples)
    (RUN / "budget-stop-supervision.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("samples", "note")}))


if __name__ == "__main__":
    main()
