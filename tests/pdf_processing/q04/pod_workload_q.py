"""Q supervisor: P's fixed Pod lifecycle with the repaired producer."""

from __future__ import annotations

import json
from pathlib import Path

import pod_workload_p as base


PHASE = "aima-pod-cgroup-q"
RUN_ID = "q04-aima-pod-cgroup-20260920-q"
WORKFLOW_QUEUE = "q04-pod-cgroup-q-workflows"
ACTIVITY_QUEUE = "q04-pod-cgroup-q-08"
EVIDENCE_ROOT = Path("/q04-evidence/q04-aima-pod-cgroup-20260920-q")


def build_measurement_argv(args, run_id: str, authorization_sha256: str) -> list[str]:
    return [
        args.python,
        "-m",
        "candidate.aima_pod_window_q",
        "--bundle", str(args.bundle),
        "--state", str(args.state),
        "--capacity", str(args.capacity),
        "--name", PHASE,
        "--expected-run-id", run_id,
        "--expected-prefix", args.prefix,
        "--integration-manifest",
        str(args.workspace / "tests/pdf_processing/q04/pod-topology-v16/RUNTIME-INTEGRATION-MANIFEST.json"),
        "--authorization-scope-sha256", authorization_sha256,
        "--attribution-interval-seconds", "0.25",
        "--attribution-gap-seconds", "1",
        "--capacity-approved",
    ]


def cleanup_markers(state: Path) -> dict:
    roots = sorted(
        root for root in (state / PHASE).glob("worker-*") if root.is_dir()
    )
    stopped = [json.loads((root / "stopped.json").read_text()) for root in roots]
    complete = bool(stopped) and all(
        row.get("parser_absent") and row.get("scratch_absent") for row in stopped
    )
    return {
        "worker_absent": complete,
        "owned_children_absent": complete,
        "scratch_absent": complete,
        "worker_generations": len(stopped),
        "stopped": stopped,
    }


base.PHASE = PHASE
base.RUN_ID = RUN_ID
base.WORKFLOW_QUEUE = WORKFLOW_QUEUE
base.ACTIVITY_QUEUE = ACTIVITY_QUEUE
base.EVIDENCE_ROOT = EVIDENCE_ROOT
base.build_measurement_argv = build_measurement_argv
base.cleanup_markers = cleanup_markers
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
