"""Replay DF guards and correlate the small-key window with direct PSI callers."""
from collections import Counter
import gzip
import json
from pathlib import Path
import re
import statistics
import sys

from ancestor_probe_co import full, violation


root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/private/tmp/q44-object-small-key-df")
summary = json.loads((root / "summary.json").read_text())


def lines(name):
    path = root / name
    text = path.read_text() if path.exists() else gzip.decompress(
        Path(str(path) + ".gz").read_bytes()).decode()
    return [json.loads(line) for line in text.splitlines()]


samples = lines("samples.jsonl")
trace = lines("object-stall-trace.jsonl")
baseline = summary["baseline"]
observed = [row for row in samples if baseline["time"] <= row["time"]]
rows = [row for batch in summary["batches"] for row in batch["rows"]]

assert summary["status"] == "NO_PSI_IN_SMALL_KEY_REPLAY"
assert summary["restoration"] == "verified_zero_replicas_and_no_owned_pods"
assert not summary["restoration_errors"]
assert summary["object_decision"]["decision"] == "restored"
assert summary["final_health"] == {"healthy": True, "running": [], "objects": 200}
assert summary["candidate"]["pod_uid"] != summary["object_decision"]["pod"]["pod_uid"]
assert len(summary["batches"]) == 16 and len(rows) == 256
assert sum(row["bytes"] for row in rows) == 2737516
assert all(row["key"].startswith("t09a/object-probe-20260928-df/") for row in rows)

failures = [(row["phase"], violation(row, baseline,
    4831838208 if row["phase"] in ("before-activation", "admission") else 1610612736))
    for row in observed]
assert not [item for item in failures if item[1]]
assert trace[0]["kind"] == "start" and trace[-1]["kind"] == "end"
for stats in trace[-1]["buffer_stats"].values():
    fields = dict(line.split(":", 1) for line in stats.splitlines())
    assert all(int(fields[key]) == 0 for key in
               ("overrun", "commit overrun", "dropped events"))

identities = {}
callers = Counter()
target = []
for row in trace:
    if row.get("identity"):
        identities[row["identity"]["tid"]] = row["identity"]
    match = re.search(r"-(\d+)\s+\[.*?\s(\d+\.\d+): psi_memstall_enter <-(\S+)",
                      row.get("line", ""))
    if not match:
        continue
    tid, stamp, caller = match.groups()
    wall = trace[0]["time"] + float(stamp) - trace[0]["monotonic"]
    if not baseline["time"] <= wall <= observed[-1]["time"]:
        continue
    callers[caller] += 1
    identity = identities.get(int(tid), {})
    if summary["candidate"]["container_id"] in identity.get("cgroup", ""):
        target.append({"time": wall, "caller": caller, "identity": identity})

last = observed[-1]
latencies = {name: [row[name] for row in rows] for name in
             ("source_get_seconds", "put_seconds", "dest_get_seconds")}
analysis = {
    "status": "PASS_NEGATIVE_CONTROL",
    "formal_guard_failures": [],
    "operations": {"objects": 256, "batches": 16, "bytes_each_direction": 2737516,
        "source_prefix": "t09a/bounds-20260928-dd/",
        "destination_prefix": "t09a/object-probe-20260928-df/",
        "latency_seconds": {name: {"minimum": min(values),
            "median": statistics.median(values), "maximum": max(values)}
            for name, values in latencies.items()}},
    "samples": len(observed),
    "maximum_object_bytes": max(row["levels"][0]["current"] for row in observed),
    "minimum_vm_available": min(row["vm"]["available"] for row in observed),
    "object_full_psi_delta_us": full(last["levels"][0]["pressure"])["total"]
        - full(baseline["levels"][0]["pressure"])["total"],
    "object_local_event_deltas": {key: last["levels"][0]["events_local"][key] - value
        for key, value in baseline["levels"][0]["events_local"].items()},
    "vm_counter_deltas": {key: last["vm"]["stat"][key] - value
        for key, value in baseline["vm"]["stat"].items()},
    "vm_callers": dict(callers),
    "target_object_calls": target,
    "trace_loss": 0,
    "interpretation": "DD many-small-key copy/readback did not reproduce object PSI",
}
assert analysis["object_full_psi_delta_us"] == 0
assert not target
assert all(analysis["object_local_event_deltas"][key] == 0
           for key in ("max", "oom", "oom_kill"))
(root / "analysis.json").write_text(json.dumps(analysis, indent=2) + "\n")
print(json.dumps(analysis, indent=2))
