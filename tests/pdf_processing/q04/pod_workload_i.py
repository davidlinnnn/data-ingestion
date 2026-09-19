"""Pod-local supervisor for the fixed fixture-07 reviewed matrix.

This file is inert when imported.  The outer runner invokes it only inside the
reviewed worker Pod after capacity authorization and a no-inference preflight.
It publishes ownership before the matrix, preserves the matrix exit, and emits
cleanup markers without deleting the Pod or its evidence volume.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from pod_durable_evidence import seal, write_once


PHASE = "yolo-pod-cgroup-i"
RUN_ID = "q04-yolo-pod-cgroup-20260920-i"
WORKFLOW_QUEUE = "q04-pod-cgroup-i-workflows"
ACTIVITY_QUEUE = "q04-pod-cgroup-i-07"
EVIDENCE_ROOT = Path("/q04-evidence/q04-yolo-pod-cgroup-20260920-i")
PARSER_BUDGETS = {
    "startup_seconds": 120,
    "no_progress_seconds": 180,
    "terminate_seconds": 5,
    "reap_seconds": 5,
    "max_requests": 1,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def start_ticks(pid: int, proc_root: Path = Path("/proc")) -> int:
    raw = (proc_root / str(pid) / "stat").read_text()
    return int(raw[raw.rfind(")") + 1 :].split()[19])


def adopt_budget(
    state: Path,
    record: Path,
    *,
    evidence_root: Path | None = None,
    run_id: str = RUN_ID,
    workflow_queue: str = WORKFLOW_QUEUE,
    activity_queue: str = ACTIVITY_QUEUE,
) -> dict:
    path = state / "config.json"
    config = json.loads(path.read_text())
    before = config["parser_budgets"]
    expected = {**PARSER_BUDGETS, "max_requests": 20}
    if before != expected:
        raise ValueError("baseline parser budgets changed")
    if not config.get("run_id", "").startswith("q04-"):
        raise ValueError("initialized run identity changed")
    if "07" not in config.get("profiles", {}):
        raise ValueError("fixture-07 profile missing")
    initialized_run_id = config["run_id"]
    config["parser_budgets"] = PARSER_BUDGETS
    config["pod_namespace"] = None
    config["run_id"] = run_id
    config["workflow_queue"] = workflow_queue
    config["profiles"] = {"07": config["profiles"]["07"]}
    config["queues"] = {"07": activity_queue}
    payload = (json.dumps(config, indent=2) + "\n").encode()
    temporary = path.with_suffix(".candidate")
    temporary.write_bytes(payload)
    os.replace(temporary, path)
    value = {
        "before": before,
        "after": PARSER_BUDGETS,
        "initialized_run_id": initialized_run_id,
        "run_id": run_id,
        "workflow_queue": workflow_queue,
        "activity_queue": activity_queue,
        "profile_keys": ["07"],
        "config_sha256": hashlib.sha256(payload).hexdigest(),
        "production_default_changed": False,
        "fixture": "07",
    }
    write_once(record, value, volume_root=evidence_root or record.parent)
    return value


def build_init_argv(args) -> list[str]:
    return [
        args.python,
        str(args.workspace / "tests/pdf_processing/q04/pod_init_i.py"),
        "--bundle", str(args.bundle),
        "--state", str(args.state),
        "--capacity", str(args.capacity),
        "--temporal", args.pod_temporal,
        "--endpoint", args.pod_objects,
        "--bucket", "t09a",
        "--prefix", args.prefix,
        "--model-cache", str(args.model_cache),
        "--run-id", args.run_id,
        "--workflow-queue", args.workflow_queue,
        "--activity-queue", args.activity_queue,
        "--capacity-approved",
    ]


def build_measurement_argv(args, run_id: str, authorization_sha256: str) -> list[str]:
    q04 = args.workspace / "tests/pdf_processing/q04"
    return [
        args.python,
        "-m", "candidate.yolo_reviewed_window",
        "--bundle", str(args.bundle),
        "--state", str(args.state),
        "--capacity", str(args.capacity),
        "--name", PHASE,
        "--fixture", "07",
        "--modes", "fresh", "restored", "replay",
        "--expected-run-id", run_id,
        "--expected-prefix", args.prefix,
        "--integration-manifest", str(
            q04 / "pod-topology-v8/RUNTIME-INTEGRATION-MANIFEST.json"
        ),
        "--main-review", str(q04 / "candidate/yolo-reviewed-v1/MAIN-REVIEW.json"),
        "--equivalence-bundle", str(q04 / "candidate/yolo-equivalence-v1/BUNDLE.json"),
        "--resource-bundle", str(q04 / "candidate/yolo-resource-v1/BUNDLE.json"),
        "--parser-budgets", str(q04 / "candidate/yolo-resource-v1/PARSER-BUDGETS.json"),
        "--resource-analysis", str(q04 / "diagnosis/yolo-lifecycle-a/evidence/resource-peak.json"),
        "--historical-methods", str(q04 / "../t09a_r3/evidence/20260914-0b537d0-c/actual-methods.json"),
        "--authorization-scope-sha256", authorization_sha256,
        "--attribution-interval-seconds", "0.25",
        "--attribution-gap-seconds", "1",
        "--capacity-approved",
    ]


def stop_group(process: subprocess.Popen, graceful_seconds: float = 180) -> bool:
    if process.poll() is not None:
        return False
    os.killpg(process.pid, signal.SIGINT)
    try:
        process.wait(timeout=graceful_seconds)
        return False
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
        return True


def cleanup_markers(state: Path) -> dict:
    roots = sorted(root for root in state.glob("yolo-pod-cgroup-i/worker-*") if root.is_dir())
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


def seal_terminal(control: Path, *, returncode: int) -> dict:
    cleanup = json.loads((control / "cleanup-complete.json").read_text())
    volume_identity = json.loads(
        (control / "evidence-volume-identity.json").read_text()
    )
    cleanup_complete = all(
        cleanup.get(name) is True
        for name in ("worker_absent", "owned_children_absent", "scratch_absent")
    )
    return seal(
        control,
        volume_identity=volume_identity,
        workload_succeeded=returncode == 0,
        cleanup_complete=cleanup_complete,
    )


def require_pre_inference_gates(control: Path) -> dict:
    value = json.loads((control / "pre-inference-gates.json").read_text())
    if (
        value.get("status") != "PASS_PRE_INFERENCE"
        or value.get("inference_started") is not False
        or value.get("workflow_started") is not False
        or value.get("object_written") is not False
    ):
        raise ValueError("pre-inference gate record changed")
    expected = {
        "image_identity",
        "mount_and_path",
        "python_executable",
        "packages_imports",
        "models",
        "cgroup",
        "configuration",
        "source_hashes",
        "workload_imports",
        "temporal",
        "object_storage",
    }
    if set(value.get("gates", {})) != expected:
        raise ValueError("pre-inference gate set incomplete")
    if any(gate.get("status") != "PASS" for gate in value["gates"].values()):
        raise ValueError("pre-inference gate did not pass")
    return value


def run(args) -> int:
    workload_started = time.monotonic()
    workload_deadline = workload_started + args.workload_seconds
    control = args.control
    require_pre_inference_gates(control)
    write_once(control / "supervisor-ownership.json", {
        "pid": os.getpid(),
        "start_ticks": start_ticks(os.getpid()),
        "capacity_sha256": sha256(args.capacity),
        "phase": PHASE,
        "started_at": time.time(),
    }, volume_root=control)
    env = os.environ.copy()
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONSAFEPATH="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        OMP_NUM_THREADS="4",
        PYTHONPATH=":".join(
            [
                str(args.workspace / "src"),
                str(args.workspace / "tests/pdf_processing/q04"),
                str(args.workspace / "tests/pdf_processing/q02"),
                str(args.workspace / "tests/pdf_processing/q03"),
            ]
        ),
    )
    try:
        init = subprocess.run(
            build_init_argv(args), env=env, capture_output=True, text=True, timeout=180
        )
    except subprocess.TimeoutExpired as error:
        write_once(control / "init-exit.json", {
            "returncode": 124,
            "timed_out": True,
            "stdout": error.stdout,
            "stderr": error.stderr,
        }, volume_root=control)
        write_once(control / "workload-exit.json", {
            "returncode": 124,
            "stage": "init",
            "timed_out": True,
            "forced": True,
            "finished_at": time.time(),
            "automatic_retry": False,
        }, volume_root=control)
        write_once(control / "cleanup-complete.json", {
            "worker_absent": True,
            "owned_children_absent": True,
            "scratch_absent": True,
            "worker_generations": 0,
            "stopped": [],
        }, volume_root=control)
        seal_terminal(control, returncode=124)
        return 124
    write_once(control / "init-exit.json", {
        "returncode": init.returncode,
        "stdout": init.stdout,
        "stderr": init.stderr,
    }, volume_root=control)
    if init.returncode:
        write_once(control / "workload-exit.json", {
            "returncode": init.returncode,
            "stage": "init",
            "timed_out": False,
            "forced": False,
            "finished_at": time.time(),
            "automatic_retry": False,
        }, volume_root=control)
        write_once(control / "cleanup-complete.json", {
            "worker_absent": True,
            "owned_children_absent": True,
            "scratch_absent": True,
            "worker_generations": 0,
            "stopped": [],
        }, volume_root=control)
        seal_terminal(control, returncode=init.returncode)
        return init.returncode
    adopted = adopt_budget(
        args.state,
        control / "budget-adoption.json",
        evidence_root=control,
        run_id=args.run_id,
        workflow_queue=args.workflow_queue,
        activity_queue=args.activity_queue,
    )
    config = json.loads((args.state / "config.json").read_text())
    integration_manifest = (
        args.workspace
        / "tests/pdf_processing/q04/pod-topology-v8/RUNTIME-INTEGRATION-MANIFEST.json"
    )
    reviewed_scope_sha256 = json.loads(integration_manifest.read_text())[
        "authorization_scope_sha256"
    ]
    command = build_measurement_argv(
        args, config["run_id"], reviewed_scope_sha256
    )
    started = time.time()
    workload_log = (control / "workload.log").open("x")
    process = subprocess.Popen(
        command, env=env, stdout=workload_log, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    write_once(control / "ownership.json", {
        "pid": process.pid,
        "start_ticks": start_ticks(process.pid),
        "started_at": started,
        "command": command,
        "config_sha256": adopted["config_sha256"],
        "window_authorization_scope_sha256": args.authorization_scope_sha256,
        "reviewed_candidate_scope_sha256": reviewed_scope_sha256,
    }, volume_root=control)
    forced = False
    timed_out = False
    # The 825 seconds includes the candidate's cooperative drain. Begin that
    # drain inside the same deadline instead of granting a second grace window.
    graceful_reserve = min(180.0, max(0.0, args.workload_seconds / 4))
    remaining = max(0.001, workload_deadline - time.monotonic() - graceful_reserve)
    try:
        returncode = process.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        timed_out = True
        forced = stop_group(
            process,
            graceful_seconds=max(0.001, workload_deadline - time.monotonic()),
        )
        returncode = process.returncode
    except BaseException as error:
        try:
            write_once(control / "supervisor-interruption.json", {
                "time": time.time(), "type": type(error).__name__,
                "reason": str(error), "matrix_pid": process.pid,
            }, volume_root=control)
        finally:
            forced = stop_group(process)
        raise
    finally:
        workload_log.close()
        write_once(control / "workload-exit.json", {
            "returncode": process.returncode,
            "timed_out": timed_out,
            "forced": forced,
            "finished_at": time.time(),
            "automatic_retry": False,
        }, volume_root=control)
        write_once(
            control / "cleanup-complete.json",
            cleanup_markers(args.state),
            volume_root=control,
        )
        seal_terminal(control, returncode=process.returncode)
    return returncode


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--workspace", type=Path, default=Path("/workspace"))
    value.add_argument("--control", type=Path, default=EVIDENCE_ROOT)
    value.add_argument("--bundle", type=Path, default=Path("/q04-control/inputs"))
    value.add_argument("--state", type=Path, default=EVIDENCE_ROOT / "state")
    value.add_argument("--capacity", type=Path, default=Path("/q04-control/capacity.json"))
    value.add_argument("--model-cache", type=Path, default=Path("/experiment/PROTOTYPE-wipe-me/hf"))
    value.add_argument("--python", default="/experiment/.venv/bin/python")
    value.add_argument("--prefix", required=True)
    value.add_argument("--pod-temporal", default="temporal:7233")
    value.add_argument("--pod-objects", default="http://objects:9000")
    value.add_argument("--authorization-scope-sha256", required=True)
    value.add_argument("--run-id", default=RUN_ID)
    value.add_argument("--workflow-queue", default=WORKFLOW_QUEUE)
    value.add_argument("--activity-queue", default=ACTIVITY_QUEUE)
    value.add_argument("--workload-seconds", type=int, default=825, choices=[825])
    return value


def main(argv=None) -> int:
    return run(parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
