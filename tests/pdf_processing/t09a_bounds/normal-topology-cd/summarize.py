"""Reconcile CD guard onset, business results and retained cleanup evidence."""
import base64
from collections import Counter
import gzip
import json
from pathlib import Path
import shutil

RAW = Path("/private/tmp/t09a-bounds-20260927-cd")
OUTER = Path("/private/tmp/t09a-normal-topology-20260927-cd")
OBJECT = Path("/private/tmp/t09a-bounds-object-20260927-cd")
DEST = Path(__file__).parent / "first-window-evidence"
DEST.mkdir(exist_ok=True)

def read(path):
    return json.loads(path.read_text())

def write(name, value):
    (DEST / name).write_text(json.dumps(value, indent=2) + "\n")

stop = read(RAW / "controller-stop.json")
rows = [json.loads(line) for line in (OUTER / "object-stall-trace.jsonl").read_text().splitlines()]
samples = [r for r in rows if r["kind"] == "sample" and r.get("object") and "full_total_us" in r["object"]]
first = next(i for i, row in enumerate(samples) if row["object"]["full_total_us"] > 0)
a, b = samples[first-1:first+1]
assert b["time"] < stop["time"] and b["object"]["full_total_us"] == 417
assert b["object"]["swap_current"] == 0 and b["object"]["events"]["oom_kill"] == 0
end = rows[-1]
assert end["kind"] == "end"
assert all("overrun: 0" in text and "dropped events: 0" in text for text in end["buffer_stats"].values())
write("object-psi-onset.json", {"before": a, "first": b, "stop": stop,
      "after_one_second": samples[first+5], "trace_end": end,
      "thread_attribution_limit": "CD sched filter included every minio comm; child thread cgroups were not captured, so individual stack-to-object attribution is unproven."})
state = RAW / "failure-evidence/state/bounds-pod-cgroup-cd"
results = []
for directory in sorted(state.glob("warm-*")):
    history_file = directory / ("history.json" if (directory / "history.json").exists() else "failure-history.json")
    events = read(history_file)["events"]
    completed = next(e for e in reversed(events) if e["eventType"] == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED")
    payload = completed["workflowExecutionCompletedEventAttributes"]["result"]["payloads"][0]["data"]
    result = json.loads(base64.b64decode(payload))
    accepted = directory / "accepted.json"
    results.append({"fixture": directory.name, "events": dict(Counter(e["eventType"] for e in events)),
                    "business": {k: result.get(k) for k in ("status", "processing_complete", "canonical_accepted", "registered_pages", "registered_components", "selected_components", "error")},
                    "local_verified": read(accepted)["verified"] if accepted.exists() else False,
                    "terminal_time": completed["eventTime"],
                    "cancellation_time": next((e["eventTime"] for e in events if e["eventType"] == "EVENT_TYPE_WORKFLOW_EXECUTION_CANCEL_REQUESTED"), None)})
assert all(r["local_verified"] and r["business"]["processing_complete"] for r in results[:4])
assert results[4]["business"]["status"] == "failed" and not results[4]["local_verified"]
write("temporal-reconciliation.json", results)
for source, name in [(RAW/"pod-pre-inference-gates.json", "pre-inference-gates.json"),
                     (RAW/"outer-cleanup.json", "outer-cleanup.json"),
                     (OBJECT/"trial-cleanup.json", "object-trial-cleanup.json"),
                     (OUTER/"held-topology-controller.json", "held-topology-controller.json"),
                     (OUTER/"trace-adjustment.json", "trace-adjustment.json"),
                     (RAW/"failure-evidence/cleanup-complete.json", "cleanup-complete.json"),
                     (RAW/"failure-evidence/durable-terminal-manifest.json", "durable-terminal-manifest.json")]:
    shutil.copyfile(source, DEST/name)
with (OUTER/"object-stall-trace.jsonl").open("rb") as source, gzip.open(DEST/"object-stall-trace.jsonl.gz", "wb") as target:
    shutil.copyfileobj(source, target)
print("CD reproduced: object full PSI +417us; four verified complete results, final06 failed; cleanup retained")
