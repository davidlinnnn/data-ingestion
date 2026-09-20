"""Run one Q AIMA matrix through P's reviewed Pod execution engine."""

from __future__ import annotations

import inspect
import shlex
from pathlib import Path

import pod_topology_q as pod_topology
from pod_remote_evidence_q import (
    FINAL_REQUIRED,
    IncrementalEvidenceMirror,
    PodEvidenceIdentity,
    pull_once,
)
from sentinel import run_yolo_pod_cgroup_p as base


PHASE = "aima-pod-cgroup-q"
RUN_IDENTITY = "q04-aima-pod-cgroup-20260920-q"
PREFIX = "q04/aima-pod-cgroup-20260920-q/"
OUT = Path("/private/tmp/q04-aima-pod-cgroup-20260920-q")
EVIDENCE_DIRECTORY_NAME = pod_topology.EVIDENCE_DIRECTORY_NAME
EVIDENCE = "/q04-evidence/" + EVIDENCE_DIRECTORY_NAME
BUNDLE = Path("/private/tmp/q04-inputs-warm-lifecycle-q-final4")
WORKER_YAML = base.Q04 / "pod-topology-v16/WORKER.yaml"
OFFLINE_MANIFEST = base.Q04 / "pod-topology-v16/RUNNER-MANIFEST.json"
P_EVIDENCE = "/q04-evidence/q04-aima-pod-cgroup-20260920-p"
P_PHASE = "aima-pod-cgroup-p"


def workload_argv() -> list[str]:
    return [
        "/experiment/.venv/bin/python",
        "/workspace/tests/pdf_processing/q04/pod_workload_q.py",
        "--prefix", PREFIX,
        "--authorization-scope-sha256", base.authorization_scope_sha256(),
        "--workload-seconds", str(base.WORKLOAD_SECONDS),
        "--control", EVIDENCE,
        "--state", EVIDENCE + "/state",
        "--bundle", base.CONTROL + "/inputs",
        "--capacity", base.CONTROL + "/capacity.json",
        "--pod-temporal", "temporal:7233",
        "--pod-objects", "http://objects:9000",
        "--run-id", RUN_IDENTITY,
        "--workflow-queue", pod_topology.WORKFLOW_QUEUE,
        "--activity-queue", pod_topology.ACTIVITY_QUEUE,
    ]


def preflight_argv() -> list[str]:
    return [
        "/experiment/.venv/bin/python",
        "/workspace/tests/pdf_processing/q04/pod_preflight_q.py",
        "--workspace", "/workspace",
        "--mount-root", base.EVIDENCE_MOUNT,
        "--evidence-directory-name", EVIDENCE_DIRECTORY_NAME,
        "--model-cache", "/experiment/PROTOTYPE-wipe-me/hf",
        "--provenance",
        "/workspace/tests/pdf_processing/q04/candidate/yolo-reviewed-b-fail/RETAINED-REPLAY.json",
        "--python", "/experiment/.venv/bin/python",
        "--pod-identity", base.CONTROL + "/pod-identity.json",
        "--capacity", base.CONTROL + "/capacity.json",
        "--source-manifest", base.CONTROL + "/source-manifest.json",
        "--bundle", base.CONTROL + "/inputs",
        "--authorization-scope-sha256", base.authorization_scope_sha256(),
        "--expected-bundle-sha256", base.sha256((BUNDLE / "inputs.json").read_bytes()),
        "--temporal", "temporal:7233",
        "--endpoint", "http://objects:9000",
        "--bucket", "t09a",
        "--prefix", PREFIX,
    ]


def exact_command() -> str:
    return shlex.join(
        [
            str(base.LOCAL_PYTHON),
            str(Path(__file__).resolve()),
            "--execute",
            "--owner", "main-session",
            "--approval-reference", "User confirmed Q04 execution on 2026-09-20",
            "--authorization-scope-sha256", base.authorization_scope_sha256(),
        ]
    )


def _program(function, *args):
    return function(*args).replace(P_EVIDENCE, EVIDENCE).replace(
        "state/" + P_PHASE, "state/" + PHASE
    )


_sample_program = base.sample_program
_stop_owned_supervisor_program = base.stop_owned_supervisor_program
_terminal_cleanup_program = base.terminal_cleanup_program
_force_stop_supervisor_program = base.force_stop_supervisor_program
_archive_fingerprint_program = base.archive_fingerprint_program
_build_offline_manifest = base.build_offline_manifest


def adapt_execute_window():
    source = inspect.getsource(_execute_window)
    if source.count(P_EVIDENCE) != 1:
        raise RuntimeError("P engine inline evidence path contract changed")
    namespace = dict(vars(base))
    exec(compile(source.replace(P_EVIDENCE, EVIDENCE), str(base.__file__) + ":q", "exec"), namespace)
    return namespace["execute_window"]


def build_offline_manifest() -> dict:
    value = _build_offline_manifest()
    paths = {
        "runner": Path(__file__),
        "pod_engine": Path(base.__file__),
        "pod_workload": base.Q04 / "pod_workload_q.py",
        "remote_evidence": base.Q04 / "pod_remote_evidence_q.py",
        "pre_inference": base.Q04 / "pod_preflight_q.py",
        "topology_builder": base.Q04 / "pod_topology_q.py",
        "source_manifest": base.Q04 / "pod-topology-v16/SOURCE-MANIFEST.json",
        "runtime_integration_manifest": base.Q04 / "pod-topology-v16/RUNTIME-INTEGRATION-MANIFEST.json",
    }
    value["sources"].update(
        {name: base.sha256(path.read_bytes()) for name, path in paths.items()}
    )
    value["runtime_blocker"] = "live admission and complete Q runtime gates"
    return value


base.PHASE = PHASE
base.RUN_IDENTITY = RUN_IDENTITY
base.PREFIX = PREFIX
base.OUT = OUT
base.EVIDENCE_DIRECTORY_NAME = EVIDENCE_DIRECTORY_NAME
base.EVIDENCE = EVIDENCE
base.BUNDLE = BUNDLE
base.NAMESPACE = pod_topology.NAMESPACE
base.DEPLOYMENT = pod_topology.DEPLOYMENT
base.RUN_LABEL = pod_topology.RUN_LABEL
base.NODE = pod_topology.NODE
base.WORKER_YAML = WORKER_YAML
base.OFFLINE_MANIFEST = OFFLINE_MANIFEST
base.pod_topology = pod_topology
base.FINAL_REQUIRED = FINAL_REQUIRED
base.IncrementalEvidenceMirror = IncrementalEvidenceMirror
base.PodEvidenceIdentity = PodEvidenceIdentity
base.pull_once = pull_once
base.workload_argv = workload_argv
base.preflight_argv = preflight_argv
base.exact_command = exact_command
base.sample_program = lambda: _program(_sample_program)
base.stop_owned_supervisor_program = lambda seconds: _program(
    _stop_owned_supervisor_program, seconds
)
base.terminal_cleanup_program = lambda: _program(_terminal_cleanup_program)
base.force_stop_supervisor_program = lambda: _program(_force_stop_supervisor_program)
base.archive_fingerprint_program = lambda: _program(_archive_fingerprint_program)
base.build_offline_manifest = build_offline_manifest
_execute_window = base.execute_window
base.execute_window = adapt_execute_window()
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
