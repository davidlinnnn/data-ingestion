"""Move VM pressure to telemetry only after successful terminal proofs exist."""

import json
from pathlib import Path


def terminal_proofs(output: Path, baseline_oom: int, vm_floor: int, cgroup_limit: int):
    try:
        workload = json.loads((output / "evidence/workload-exit.json").read_text())
        sample = json.loads((output / "terminal-cgroup-sample.json").read_text())
        cleanup = json.loads((output / "evidence/cleanup-complete.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not (
        workload.get("returncode") == 0
        and workload.get("timed_out") is False
        and workload.get("forced") is False
        and sample.get("available", 0) >= vm_floor
        and sample.get("vm_oom_kill") == baseline_oom
        and sample.get("memory_current", cgroup_limit + 1) <= cgroup_limit
        and sample.get("psi_full_avg10") == 0
        and all(sample.get("memory_events", {}).get(key) == 0
                for key in ("max", "oom", "oom_kill", "oom_group_kill"))
        and all(cleanup.get(key) is True
                for key in ("worker_absent", "owned_children_absent", "scratch_absent"))
        and cleanup.get("missing_stopped_markers") == []
    ):
        return None
    return {"workload": workload, "terminal_sample": sample, "cleanup": cleanup}


def runtime_psi_is_telemetry(row: dict, baseline_oom: int, vm_floor: int, proofs) -> bool:
    if row["available"] < vm_floor or row["vm_oom_kill"] != baseline_oom:
        raise ValueError("outer VM runtime memory/OOM guard breached")
    if row["psi_full_avg10"] != 0 and proofs is None:
        raise ValueError("outer VM runtime PSI guard breached")
    return row["psi_full_avg10"] != 0
