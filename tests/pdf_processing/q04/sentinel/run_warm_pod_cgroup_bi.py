"""One #44 mixed-warm window with a reversible, observed 1 GiB object limit."""

import importlib.util
import json
from pathlib import Path
import shlex
import sys
import time

Q04 = Path(__file__).resolve().parent.parent
if str(Q04) not in sys.path:
    sys.path.insert(0, str(Q04))

import pod_topology_bi as topology
from pod_remote_evidence_bi import FINAL_REQUIRED, IncrementalEvidenceMirror, pull_once
from sentinel import object_limit_trial_bh as object_trial
from sentinel import object_monitor_bh


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
PHASE = "bounds-pod-cgroup-bk"
RUN_IDENTITY = "t09a-bounds-20260926-bk"
PREFIX = "t09a/bounds-20260926-bk/"
OUT = Path("/private/tmp/t09a-bounds-20260926-bk")
OBJECT_OUT = Path("/private/tmp/t09a-bounds-object-20260926-bk")
BUNDLE = Path("/private/tmp/q44-inputs-warm-20260926-bk")
RECORD = Q04.parent / "t09a_bounds"
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


def exact_command():
    return shlex.join([
        str(base.LOCAL_PYTHON), str(Path(__file__).resolve()), "--execute",
        "--owner", "main-session",
        "--approval-reference", "User authorized next #44 acceptance step",
        "--authorization-scope-sha256", ah.authorization_scope_sha256(),
    ])


_ah_scope = ah.authorization_scope
def authorization_scope():
    return {**_ah_scope(), "object_limit_bytes": object_trial.TRIAL_BYTES}


ah.authorization_scope = base.authorization_scope = authorization_scope
ah.exact_command = base.exact_command = exact_command
_ah_preflight_argv = ah.preflight_argv
_ah_workload_argv = ah.workload_argv


def preflight_argv():
    return [part.replace("pod_preflight_ah.py", "pod_preflight_bi.py")
            for part in _ah_preflight_argv()]


def workload_argv():
    return [part.replace("pod_workload_ah.py", "pod_workload_bi.py")
            for part in _ah_workload_argv()]


base.preflight_argv = preflight_argv
base.workload_argv = workload_argv
base.FINAL_REQUIRED = FINAL_REQUIRED
base.IncrementalEvidenceMirror = IncrementalEvidenceMirror
base.pull_once = pull_once
adapted_window = ah.adapt_execute_window()


def build_offline_manifest():
    value = ah.build_offline_manifest()
    paths = {
        "bounds_runner": Path(__file__),
        "bounds_topology": Q04 / "pod_topology_bi.py",
        "bounds_preflight": Q04 / "pod_preflight_bi.py",
        "bounds_workload": Q04 / "pod_workload_bi.py",
        "bounds_remote_evidence": Q04 / "pod_remote_evidence_bi.py",
        "bounds_candidate": RECORD / "BI-MANIFEST.json",
        "bounds_runtime": RECORD / "RUNTIME-INTEGRATION-MANIFEST.json",
        "bounds_source": RECORD / "SOURCE-MANIFEST.json",
        "bounds_worker": RECORD / "WORKER.yaml",
        "object_trial": Path(object_trial.__file__),
        "object_monitor": Path(object_monitor_bh.__file__),
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


def verify_sample(row, baseline):
    base_verify_sample(row, baseline)
    if monitor is not None and monitor.error is not None:
        raise monitor.error
    if monitor is not None and len(monitor.samples) > 1:
        first, latest = monitor.samples[0], monitor.samples[-1]
        if (latest["memory_events"]["max"] > first["memory_events"]["max"]
                or latest["object_full_total_us"] > first["object_full_total_us"]):
            raise ValueError("object-service max/full-PSI event during mixed warm run")


base_verify_sample = base.verify_runtime_sample
monitor = None


def execute_window(args):
    global monitor
    offline_check()
    kube = base.Kubectl()
    OBJECT_OUT.mkdir(exist_ok=False)
    trial = object_trial.capture(kube)
    primary = None
    try:
        object_trial.enter(kube, trial, deadline=time.time() + 120)
        monitor = object_monitor_bh.ObjectMonitor(
            kube, OBJECT_OUT / "object-pressure.jsonl", object_trial.TRIAL_BYTES
        )
        monitor.start(seconds=1500)
        adapted_window.__globals__["verify_runtime_sample"] = verify_sample
        result = adapted_window(args, kube)
        return result
    except BaseException as error:
        primary = error
        raise
    finally:
        adapted_window.__globals__["verify_runtime_sample"] = base_verify_sample
        checks = {"primary_error": repr(primary) if primary else None}
        if monitor is not None and monitor.process is not None:
            try:
                summary = monitor.stop()
                checks["object_observer"] = summary
                if summary["max_events_delta"] or summary["full_psi_delta_us"]:
                    raise ValueError("object-service max/full-PSI event during mixed warm run")
            except BaseException as error:
                checks["object_observer_error"] = repr(error)
        try:
            checks["object_restoration"] = object_trial.restore(
                kube, trial, deadline=time.time() + 120
            )
            checks["final_health"] = base.t09a_health(
                kube, OBJECT_OUT / "post-restore-health.json", require_idle=True,
                deadline=time.time() + 30,
            )
        except BaseException as error:
            checks["object_restoration_error"] = repr(error)
        (OBJECT_OUT / "trial-cleanup.json").write_text(json.dumps(checks, indent=2) + "\n")
        if primary is None and (checks.get("object_observer_error")
                                or checks.get("object_restoration_error")):
            raise RuntimeError("#44 object observer/restoration failed")


base.execute_window = execute_window
base.offline_check = offline_check
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
