"""Run one authorized corrected Q04 warm sequence in the reviewed Pod cgroup."""

from __future__ import annotations

import importlib.util
import inspect
import shlex
from pathlib import Path
import sys

Q04 = Path(__file__).resolve().parent.parent
if str(Q04) not in sys.path:
    sys.path.insert(0, str(Q04))

import pod_topology_u as pod_topology
from pod_remote_evidence_u import (
    FINAL_REQUIRED,
    IncrementalEvidenceMirror,
    PodEvidenceIdentity,
    pull_once,
)


def _load_engine():
    """Load P with U topology present before Python binds function defaults."""
    spec = importlib.util.spec_from_file_location(
        "q04_warm_u_pod_engine", Path(__file__).with_name("run_yolo_pod_cgroup_p.py")
    )
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get("pod_topology_p")
    sys.modules["pod_topology_p"] = pod_topology
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop("pod_topology_p", None)
        else:
            sys.modules["pod_topology_p"] = previous
    return module


base = _load_engine()

PHASE = "warm-pod-cgroup-u"
RUN_IDENTITY = "q04-warm-pod-cgroup-20260921-u"
PREFIX = "q04/warm-pod-cgroup-20260921-u/"
OUT = Path("/private/tmp/q04-warm-pod-cgroup-20260921-u")
EVIDENCE_DIRECTORY_NAME = pod_topology.EVIDENCE_DIRECTORY_NAME
EVIDENCE = "/q04-evidence/" + EVIDENCE_DIRECTORY_NAME
BUNDLE = Path("/private/tmp/q04-inputs-warm-lifecycle-q-final4")
WORKER_YAML = base.Q04 / "pod-topology-v20/WORKER.yaml"
OFFLINE_MANIFEST = base.Q04 / "pod-topology-v20/RUNNER-MANIFEST.json"
P_EVIDENCE = "/q04-evidence/q04-aima-pod-cgroup-20260920-p"
P_PHASE = "aima-pod-cgroup-p"


def authorization_scope() -> dict:
    return {
        "phase": PHASE,
        "run_identity": RUN_IDENTITY,
        "sequence": ["06", "07", "08", "native", "06"],
        "group_requests": 29,
        "max_requests": 20,
        "expected_parser_generations": 2,
        "automatic_retry": False,
        "window_seconds": base.WINDOW_SECONDS,
        "outer_observation_seconds": base.OUTER_OBSERVATION_SECONDS,
        "outer_continuous_seconds": base.CONTINUOUS_SECONDS,
        "outer_available_bytes": base.OUTER_AVAILABLE_BYTES,
        "per_case_available_bytes": base.PER_CASE_AVAILABLE_BYTES,
        "workload_seconds": base.WORKLOAD_SECONDS,
        "cleanup_seconds": base.CLEANUP_SECONDS,
        "sample_interval_seconds": base.SAMPLE_INTERVAL_SECONDS,
        "transport_interval_seconds": base.TRANSPORT_INTERVAL_SECONDS,
        "cgroup_guard_bytes": base.CGROUP_GUARD_BYTES,
        "container_hard_limit_bytes": base.HARD_LIMIT_BYTES,
        "vm_runtime_floor_bytes": base.VM_RUNTIME_FLOOR_BYTES,
        "deployment": pod_topology.DEPLOYMENT,
        "evidence_pvc": pod_topology.EVIDENCE_PVC,
        "evidence_directory_name": EVIDENCE_DIRECTORY_NAME,
        "evidence_pvc_bytes": 1024**3,
        "evidence_pvc_automatic_delete": False,
        "deployment_initial_replicas": 0,
        "held_deployments_restored": False,
    }


def authorization_scope_sha256() -> str:
    return base.sha256(base.canonical(authorization_scope()))


def workload_argv() -> list[str]:
    return [
        "/experiment/.venv/bin/python",
        "/workspace/tests/pdf_processing/q04/pod_workload_u.py",
        "--prefix", PREFIX,
        "--authorization-scope-sha256", authorization_scope_sha256(),
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
        "/workspace/tests/pdf_processing/q04/pod_preflight_u.py",
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
        "--authorization-scope-sha256", authorization_scope_sha256(),
        "--expected-bundle-sha256", base.sha256((BUNDLE / "inputs.json").read_bytes()),
        "--temporal", "temporal:7233",
        "--endpoint", "http://objects:9000",
        "--bucket", "t09a",
        "--prefix", PREFIX,
    ]


def exact_command() -> str:
    return shlex.join([
        str(base.LOCAL_PYTHON),
        str(Path(__file__).resolve()),
        "--execute",
        "--owner", "main-session",
        "--approval-reference", "User authorized any Q04 acceptance execution on 2026-09-21",
        "--authorization-scope-sha256", authorization_scope_sha256(),
    ])


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
_execute_window = base.execute_window


def adapt_execute_window():
    source = inspect.getsource(_execute_window)
    if source.count(P_EVIDENCE) != 1:
        raise RuntimeError("P engine inline evidence path contract changed")
    namespace = dict(vars(base))
    source = source.replace(P_EVIDENCE, EVIDENCE)
    exec(compile(source, str(base.__file__) + ":u", "exec"), namespace)
    return namespace["execute_window"]


def build_offline_manifest() -> dict:
    value = _build_offline_manifest()
    paths = {
        "runner": Path(__file__),
        "pod_engine": Path(base.__file__),
        "pod_workload": base.Q04 / "pod_workload_u.py",
        "remote_evidence": base.Q04 / "pod_remote_evidence_u.py",
        "pre_inference": base.Q04 / "pod_preflight_u.py",
        "topology_builder": base.Q04 / "pod_topology_u.py",
        "warm_window": base.Q04 / "candidate/warm_pod_window_r.py",
        "source_manifest": base.Q04 / "pod-topology-v20/SOURCE-MANIFEST.json",
        "runtime_integration_manifest": base.Q04 / "pod-topology-v20/RUNTIME-INTEGRATION-MANIFEST.json",
    }
    value["sources"].update({
        name: base.sha256(path.read_bytes()) for name, path in paths.items()
    })
    value["runtime_blocker"] = "live admission and complete U warm runtime gates"
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
base.authorization_scope = authorization_scope
base.authorization_scope_sha256 = authorization_scope_sha256
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
base.execute_window = adapt_execute_window()
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
