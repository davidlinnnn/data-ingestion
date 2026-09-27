"""Replay BU process/reclaim attribution from retained evidence; no runtime calls."""
import hashlib
import json
from pathlib import Path
import sys


def diagnose(root):
    def rows(path):
        return [json.loads(line) for line in path.read_text().splitlines()]

    stop = json.loads((root / "controller-stop.json").read_text())["time"]
    state = root / "failure-evidence/state"
    samples = rows(state / "bounds-pod-cgroup-bu-measurement/resource-attribution.jsonl")
    window = [r for r in samples if stop - 1.6 < r["time"] < stop]
    command = "/experiment/.venv/bin/python -m pdf_processing.lifecycle_child pdf_processing.ocr"
    digest = hashlib.sha256(("\0".join(command.split()) + "\0").encode()).hexdigest()
    timeline = []
    for row in window:
        warm = next(p for p in row["processes"] if p["pid"] == 131)
        ocr = next(p for p in row["processes"] if p["pid"] == 219)
        assert ocr["command_sha256"] == digest, "growing process is not the recorded OCR command"
        timeline.append({"seconds_before_stop": stop - row["time"],
                         "warm_anon_bytes": warm["rss_anon_bytes"],
                         "warm_cpu_ticks": warm["user_cpu_ticks"] + warm["system_cpu_ticks"],
                         "ocr_anon_bytes": ocr["rss_anon_bytes"],
                         "ocr_minor_faults": ocr["minor_faults"],
                         "ocr_major_faults": ocr["major_faults"]})
    assert len(timeline) >= 2
    assert len({r["warm_anon_bytes"] for r in timeline}) == 1
    assert len({r["warm_cpu_ticks"] for r in timeline}) == 1
    assert max(r["ocr_anon_bytes"] for r in timeline) > timeline[0]["ocr_anon_bytes"]
    vm = [r for r in rows(root / "vm-controller.jsonl") if stop - 1.6 < r["time"] < stop]
    first, last = vm[0], vm[-1]
    deltas = {scope: {key: last[scope][key] - first[scope][key]
                     for key in ("pgscan_direct", "pgsteal_direct", "pgscan_kswapd")}
              for scope in ("node_vmstat", "memory_stat")}
    assert deltas["node_vmstat"]["pgscan_direct"] > 0
    assert all(value == 0 for value in deltas["memory_stat"].values())
    return {"source": str(root), "ocr_pid": 219, "warm_pid": 131,
            "timeline": timeline, "reclaim_deltas": deltas,
            "conclusion": "OCR allocation overlaps VM reclaim while warm parser is idle",
            "not_proven": "which process initiated reclaim or caused object PSI"}


if __name__ == "__main__":
    print(json.dumps(diagnose(Path(sys.argv[1])), indent=2))
