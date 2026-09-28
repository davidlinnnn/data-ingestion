"""One #44 mixed-warm window with object-stall attribution."""

import importlib.util
import inspect
import json
from pathlib import Path
import shlex
import sys
import time

Q04 = Path(__file__).resolve().parent.parent
if str(Q04) not in sys.path:
    sys.path.insert(0, str(Q04))

import pod_topology_dg as topology
from pod_remote_evidence_dg import FINAL_REQUIRED, IncrementalEvidenceMirror, pull_once
from sentinel import object_limit_trial_bh as object_trial
from sentinel import object_monitor_bh
from sentinel import object_cgroup_probe_db


object_monitor_bh.probe = object_cgroup_probe_db


spec = importlib.util.spec_from_file_location(
    "q44_previous_warm_adapter", Path(__file__).with_name("run_warm_pod_cgroup_ah.py")
)
previous = sys.modules.get("pod_topology_ah")
sys.modules["pod_topology_ah"] = topology
ah = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ah
try:
    spec.loader.exec_module(ah)
finally:
    if previous is None:
        sys.modules.pop("pod_topology_ah", None)
    else:
        sys.modules["pod_topology_ah"] = previous

base = ah.base
PHASE = "bounds-pod-cgroup-dg"
RUN_IDENTITY = "t09a-bounds-20260928-dg"
PREFIX = "t09a/bounds-20260928-dg/"
OUT = Path("/private/tmp/t09a-bounds-20260928-dg")
OBJECT_OUT = Path("/private/tmp/t09a-bounds-object-20260928-dg")
BUNDLE = Path("/private/tmp/q44-inputs-warm-20260928-db")
RECORD = Q04.parent / "t09a_bounds/normal-topology-dg"
EVIDENCE = "/q04-evidence/" + topology.EVIDENCE_DIRECTORY_NAME

ah.PHASE = base.PHASE = PHASE
ah.RUN_IDENTITY = base.RUN_IDENTITY = RUN_IDENTITY
ah.PREFIX = base.PREFIX = PREFIX
ah.OUT = base.OUT = OUT
ah.EVIDENCE_DIRECTORY_NAME = base.EVIDENCE_DIRECTORY_NAME = topology.EVIDENCE_DIRECTORY_NAME
ah.EVIDENCE = base.EVIDENCE = EVIDENCE
ah.BUNDLE = base.BUNDLE = BUNDLE
ah.WORKER_YAML = base.WORKER_YAML = RECORD / "WORKER.yaml"
ah.OFFLINE_MANIFEST = base.OFFLINE_MANIFEST = RECORD / "RUNNER-MANIFEST.json"
base.DEPLOYMENT = topology.DEPLOYMENT
base.RUN_LABEL = topology.RUN_LABEL
base.pod_topology = topology
object_monitor_bh.RUN_ID = RUN_IDENTITY


def verify_active_held_deployments(kube, *, deadline=None):
    timeout = 30 if deadline is None else base.remaining_timeout(
        deadline, 30, "active Deployments"
    )
    deployments = kube.json("get", "deployments", "-A", timeout=timeout)["items"]
    observed = {
        (item["metadata"]["namespace"], item["metadata"]["name"]): item
        for item in deployments
    }
    for expected in base.lifecycle.CANDIDATES:
        item = observed[(expected["namespace"], expected["name"])]
        if item["metadata"]["uid"] != expected["uid"]:
            raise ValueError("held Deployment UID changed")
        if item["spec"].get("replicas", 1) != 1 or item["status"].get("readyReplicas", 0) != 1:
            raise ValueError("normal-topology Deployment is not ready")


base.verify_held_deployments = verify_active_held_deployments


def verify_outer_identity_db(kube, *, deadline=None):
    timeout = 30 if deadline is None else base.remaining_timeout(
        deadline, 30, "node identity"
    )
    node = kube.json("get", "node", topology.NODE, timeout=timeout)
    if node["metadata"]["uid"] != "bfdeceea-67a2-4d7f-ac32-8b97efda6d71":
        raise ValueError("node UID changed")
    if node["status"]["nodeInfo"]["bootID"] != "c01b81ac-b0fd-4ce6-8cda-f0da74b9bbd3":
        raise ValueError("node boot identity changed")
    timeout = 30 if deadline is None else base.remaining_timeout(
        deadline, 30, "Pod absence"
    )
    if kube.json("get", "pods", "-l", "q04-run=" + base.RUN_LABEL,
                 timeout=timeout)["items"]:
        raise ValueError("owned worker Pod already exists")
    base.verify_held_deployments(kube, deadline=deadline)


base.verify_outer_identity = verify_outer_identity_db


def exact_command():
    return shlex.join([
        str(base.LOCAL_PYTHON), str(Path(__file__).resolve()), "--execute",
        "--owner", "main-session",
        "--approval-reference", "User approved DG revised object PSI qualification",
        "--authorization-scope-sha256", ah.authorization_scope_sha256(),
    ])


_ah_scope = ah.authorization_scope
def authorization_scope():
    return {
        **_ah_scope(),
        "object_limit_bytes": object_trial.TRIAL_BYTES,
        "object_memory_request_bytes": 805306368,
        "host_memory_low_override": False,
        "object_psi_policy": OBJECT_PSI_POLICY,
        "held_deployments_restored": True,
        "held_deployment_count": 32,
    }


ah.authorization_scope = base.authorization_scope = authorization_scope
ah.exact_command = base.exact_command = exact_command
_ah_preflight_argv = ah.preflight_argv
_ah_workload_argv = ah.workload_argv


def preflight_argv():
    return [part.replace("pod_preflight_ah.py", "pod_preflight_dg.py")
            for part in _ah_preflight_argv()]


def workload_argv():
    return [part.replace("pod_workload_ah.py", "pod_workload_dg.py")
            for part in _ah_workload_argv()]


base.preflight_argv = preflight_argv
base.workload_argv = workload_argv
base.FINAL_REQUIRED = FINAL_REQUIRED
base.IncrementalEvidenceMirror = IncrementalEvidenceMirror
base.pull_once = pull_once
def failure_export_boundary(terminal, stop_proven):
    if terminal["supervisor_absent"] is not True:
        raise ValueError("failure supervisor remains")
    return stop_proven or terminal["cleanup_complete"] is True


def adapt_failure_export_window():
    source = inspect.getsource(ah._execute_window)
    old = ('if not (terminal["supervisor_absent"] and terminal["cleanup_complete"]):\n'
           '                    raise ValueError("failure cleanup markers are incomplete")\n'
           '                terminal_stop_proven = True')
    new = ('terminal_stop_proven = failure_export_boundary(\n'
           '                    terminal, terminal_stop_proven\n'
           '                )')
    if source.count(ah.P_EVIDENCE) != 1 or source.count(old) != 1:
        raise RuntimeError("failure export engine contract changed")
    source = source.replace(ah.P_EVIDENCE, EVIDENCE).replace(old, new)
    namespace = dict(vars(base))
    namespace["failure_export_boundary"] = failure_export_boundary
    exec(compile(source, str(base.__file__) + ":cb", "exec"), namespace)
    return namespace["execute_window"]


adapted_window = adapt_failure_export_window()


def build_offline_manifest():
    value = ah.build_offline_manifest()
    paths = {
        "bounds_runner": Path(__file__),
        "bounds_topology": Q04 / "pod_topology_dg.py",
        "bounds_preflight": Q04 / "pod_preflight_dg.py",
        "bounds_workload": Q04 / "pod_workload_dg.py",
        "bounds_remote_evidence": Q04 / "pod_remote_evidence_dg.py",
        "bounds_candidate": Q04.parent / "t09a_bounds/normal-topology-db/DB-MANIFEST.json",
        "bounds_runtime": RECORD / "RUNTIME-INTEGRATION-MANIFEST.json",
        "bounds_source": RECORD / "SOURCE-MANIFEST.json",
        "bounds_worker": RECORD / "WORKER.yaml",
        "object_trial": Path(object_trial.__file__),
        "object_monitor": Path(object_monitor_bh.__file__),
        "object_probe": Path(object_cgroup_probe_db.__file__),
    }
    value["sources"].update({key: base.sha256(path.read_bytes())
                             for key, path in paths.items()})
    value["authorization_scope"] = authorization_scope()
    value["authorization_scope_sha256"] = ah.authorization_scope_sha256()
    value["exact_single_run_command"] = exact_command()
    value["bundle_inputs_sha256"] = base.sha256((BUNDLE / "inputs.json").read_bytes())
    return value


base.build_offline_manifest = build_offline_manifest
base_offline_check = base.offline_check


def offline_check():
    if json.loads((RECORD / "SOURCE-MANIFEST.json").read_text()) != topology.source_manifest():
        raise ValueError("#44 source projection changed")
    return base_offline_check()


OBJECT_PSI_POLICY = {
    "mode": "approved_sustained_pressure_qualification",
    "stop_full_avg10_above": 0,
    "cumulative_full_total_stop": False,
}
checked_samples = 0
monitor = None
base_verify_sample = base.verify_runtime_sample


def verify_object_monitor():
    global checked_samples
    if monitor is None or not monitor.samples:
        raise ValueError("object-service telemetry missing")
    if monitor.error is not None:
        raise monitor.error
    first = monitor.samples[0]
    for row in monitor.samples[checked_samples:]:
        if (row["object_full_avg10"] > 0
                or row["memory_events"]["max"] != first["memory_events"]["max"]
                or any(row["memory_events"][key] != 0
                       for key in ("oom", "oom_kill", "oom_group_kill"))):
            raise ValueError("object-service max/OOM/sustained-full-PSI qualification failure")
        # The Pod and container both enforce the approved cap. Record actual
        # low/min values; Kubernetes requests do not guarantee memory.low.
        for before, level in zip(first["ancestors"][:2], row["ancestors"][:2]):
            if (level["memory_max"] != str(object_trial.TRIAL_BYTES)
                    or any(level["events_local"][key] != before["events_local"][key]
                           for key in ("max", "oom", "oom_kill", "oom_group_kill"))):
                raise ValueError("object-service Pod/container memory contract changed")
        checked_samples += 1


def verify_sample(row, baseline):
    base_verify_sample(row, baseline)
    verify_object_monitor()


def execute_window(args):
    global monitor, checked_samples
    checked_samples = 0
    offline_check()
    kube = base.Kubectl()
    OBJECT_OUT.mkdir(exist_ok=False)
    value = object_trial.deployment(kube)
    if (value["spec"]["template"]["spec"]["containers"][0]["resources"] != {
            "requests": {"cpu": "100m", "memory": "768Mi"},
            "limits": {"memory": "1Gi"}}
            or value["spec"]["strategy"] != {"type": "Recreate"}):
        raise ValueError("approved native object candidate is not installed")
    primary = None
    try:
        monitor = object_monitor_bh.ObjectMonitor(
            kube, OBJECT_OUT / "object-pressure.jsonl", object_trial.TRIAL_BYTES
        )
        monitor.start(seconds=2500)
        deadline = time.monotonic() + 20
        while not monitor.samples:
            if monitor.error is not None:
                raise monitor.error
            if time.monotonic() >= deadline:
                raise TimeoutError("object-service first sample missing")
            time.sleep(.1)
        verify_object_monitor()
        adapted_window.__globals__["verify_runtime_sample"] = verify_sample
        return adapted_window(args, kube)
    except BaseException as error:
        primary = error
        raise
    finally:
        adapted_window.__globals__["verify_runtime_sample"] = base_verify_sample
        checks = {"primary_error": repr(primary) if primary else None,
                  "object_psi_policy": OBJECT_PSI_POLICY,
                  "host_memory_low_override": False}
        if monitor is not None and monitor.process is not None:
            try:
                checks["object_observer"] = monitor.stop()
                verify_object_monitor()
                checks["maximum_object_full_avg10"] = max(
                    row["object_full_avg10"] for row in monitor.samples
                )
            except BaseException as error:
                checks["object_observer_error"] = repr(error)
        (OBJECT_OUT / "trial-cleanup.json").write_text(json.dumps(checks, indent=2) + "\n")
        if primary is None and checks.get("object_observer_error"):
            raise RuntimeError("#44 object observer/qualification failed")


base.execute_window = execute_window
base.offline_check = offline_check
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
