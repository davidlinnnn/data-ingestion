"""Recompute the AQ stop attribution and bounded AN comparison from raw evidence."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / "PRESSURE-DIAGNOSIS-VERIFICATION.json").read_text())
AQ = Path(EXPECTED["sources"]["aq_raw_root"])
AN = Path(EXPECTED["sources"]["an_raw_root"])


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def overlap(root, pattern):
    samples = rows(next(root.glob(pattern)))
    return max((warm + child, sample["memory_current"])
               for sample in samples
               for warm in [max((p["pss_bytes"] for p in sample["processes"]
                                 if p["command_class"] == "warm_parser"), default=0)]
               for child in [max((p["pss_bytes"] for p in sample["processes"]
                                  if p["command_class"] == "fresh_owned_child"), default=0)]
               if child)


def verify():
    stop = json.loads((AQ / "controller-stop.json").read_text())["time"]
    samples = [r for r in rows(Path(str(AQ) + "-node-pressure.jsonl"))
               if r["kind"] == "sample" and stop - 10 <= r["ended_at"] <= stop + 1]
    pod = "pod" + EXPECTED["sources"]["aq_pod_uid"].replace("-", "_") + ".slice"
    container = "cri-containerd-" + EXPECTED["sources"]["aq_container_id"] + ".scope"
    dominant = sorted(samples, key=lambda r: r["node_full_delta_us"], reverse=True)[:2]
    for row, expected in zip(sorted(dominant, key=lambda r: r["ended_at"]),
                             EXPECTED["dominant_host_samples"]):
        assert row["node_full_delta_us"] == expected["node_full_delta_us"]
        assert next(v for k, v in row["cgroup_full_delta_us"].items()
                    if k.endswith(pod)) == expected["aq_pod_full_delta_us"]
        assert next(v for k, v in row["cgroup_full_delta_us"].items()
                    if k.endswith("/" + container)) == expected["aq_container_full_delta_us"]

    observer = json.loads(Path(str(AQ) + "-node-pressure-cleanup.json").read_text())[
        "remote_stop"]["value"]["container_id"]
    nearby = [r for r in rows(Path(str(AQ) + "-node-pressure.jsonl"))
              if r["kind"] == "sample" and stop - 2.2 < r["ended_at"] < stop + .2]
    assert sum(r["cgroup_full_delta_us"].get("docker/" + observer, 0)
               for r in nearby) == EXPECTED["reclaim_window"]["observer_cgroup_full_delta_us"]

    controller = rows(AQ / "vm-controller.jsonl")
    before = max((r for r in controller if r["time"] <= stop - 2.2),
                 key=lambda r: r["time"])
    after = min((r for r in controller if r["time"] >= stop - 1.3),
                key=lambda r: r["time"])
    expected = EXPECTED["reclaim_window"]
    for key in ("allocstall_movable", "pgscan_direct", "compact_stall",
                "thp_fault_alloc", "thp_fault_fallback"):
        assert after["node_vmstat"][key] - before["node_vmstat"][key] == expected["vm_" + key + "_delta"]
    assert after["memory_stat"]["anon"] - before["memory_stat"]["anon"] == expected["pod_anon_delta_bytes"]
    assert all(after["memory_events"][key] == 0 for key in ("high", "max", "oom", "oom_kill"))

    aq_pair = overlap(AQ, "failure-evidence/state/*-measurement/resource-attribution.jsonl")
    an_pair = overlap(AN, "evidence/state/*-measurement/resource-attribution.jsonl")
    expected = EXPECTED["bounded_comparison"]
    assert aq_pair == (expected["aq_max_warm_parser_plus_fresh_child_pss_bytes"],
                       expected["aq_pod_memory_at_that_sample_bytes"])
    assert an_pair == (expected["an_max_warm_parser_plus_fresh_child_pss_bytes"],
                       expected["an_pod_memory_at_that_sample_bytes"])
    assert max(r["psi_full_avg10"] for r in controller) == expected["aq_max_controller_full_avg10"]
    assert max(r["psi_full_avg10"] for r in rows(AN / "vm-controller.jsonl")) == expected["an_max_controller_full_avg10"]
    child = EXPECTED["classification"]
    command = child["growing_child_command"].split()
    digest = hashlib.sha256(("\0".join(command) + "\0").encode()).hexdigest()
    assert digest == child["growing_child_command_sha256"]
    assert any(p["pid"] == child["growing_child_pid"] and p["command_sha256"] == digest
               for sample in rows(next(AQ.glob("failure-evidence/state/*-measurement/resource-attribution.jsonl")))
               for p in sample["processes"])
    print("PASS: AQ Pod stall, reclaim timing and bounded AN comparison")


if __name__ == "__main__":
    verify()
