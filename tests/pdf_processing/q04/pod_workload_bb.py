"""Pod-local supervisor for the owned-lifecycle synchronized Q04 warm sequence."""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path
import sys


_spec = importlib.util.spec_from_file_location(
    "q04_pod_workload_bb_engine", Path(__file__).with_name("pod_workload_p.py")
)
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base
_spec.loader.exec_module(base)


PHASE = "process-drain-pod-cgroup-bb"
RUN_ID = "q04-process-drain-pod-cgroup-20260925-bb"
WORKFLOW_QUEUE = "q04-pod-cgroup-bb-workflows"
ACTIVITY_QUEUE = "q04-pod-cgroup-bb-08"
EVIDENCE_ROOT = Path("/q04-evidence/q04-process-drain-pod-cgroup-20260925-bb")


def build_measurement_argv(args, run_id: str, authorization_sha256: str) -> list[str]:
    return [
        args.python,
        "-m", "candidate.process_drain_window_bb",
        "--bundle", str(args.bundle),
        "--state", str(args.state),
        "--capacity", str(args.capacity),
        "--name", PHASE,
        "--expected-run-id", run_id,
        "--expected-prefix", args.prefix,
        "--integration-manifest",
        str(args.workspace / "tests/pdf_processing/q04/pod-topology-v53/RUNTIME-INTEGRATION-MANIFEST.json"),
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


def adapt_run():
    source = inspect.getsource(base.run)
    old = "pod-topology-v15/RUNTIME-INTEGRATION-MANIFEST.json"
    if source.count(old) != 1:
        raise RuntimeError("P supervisor integration-manifest contract changed")
    namespace = dict(vars(base))
    source = source.replace(
        old, "pod-topology-v53/RUNTIME-INTEGRATION-MANIFEST.json"
    )
    exec(compile(source, str(base.__file__) + ":u", "exec"), namespace)
    return namespace["run"]


base.PHASE = PHASE
base.RUN_ID = RUN_ID
base.WORKFLOW_QUEUE = WORKFLOW_QUEUE
base.ACTIVITY_QUEUE = ACTIVITY_QUEUE
base.EVIDENCE_ROOT = EVIDENCE_ROOT
base.build_measurement_argv = build_measurement_argv
base.cleanup_markers = cleanup_markers
base.run = adapt_run()
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
