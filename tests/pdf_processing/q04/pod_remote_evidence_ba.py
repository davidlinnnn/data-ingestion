"""Durable evidence paths for the worker-process drain gate."""

import importlib.util
from pathlib import Path
import sys


_spec = importlib.util.spec_from_file_location(
    "q04_pod_remote_evidence_ba_engine",
    Path(__file__).with_name("pod_remote_evidence_p.py"),
)
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base
_spec.loader.exec_module(base)


PHASE = "process-drain-pod-cgroup-ba"
MEASUREMENT = PHASE + "-measurement"
STREAM_FILES = {
    f"state/{MEASUREMENT}/resource-attribution.jsonl",
    "vm-controller.jsonl",
    "workload.log",
}
FINAL_REQUIRED = {
    "workload-memory-policy.json",
    f"state/{PHASE}/phase-complete.json",
    f"state/{PHASE}/reviewed-window-contract.json",
    *{
        f"state/{PHASE}/drain-native/{name}"
        for name in ("admission.json", "accepted.json", "before-drain.json",
                     "drain.json", "drain-proof.json", "history.json", "progress.jsonl")
    },
    f"state/{PHASE}/worker-1/stopped.json",
    f"state/{PHASE}/worker-1/samples.jsonl",
    f"state/{PHASE}/worker-1/host.json",
    f"state/{PHASE}/worker-2/stopped.json",
    f"state/{PHASE}/worker-2/samples.jsonl",
    f"state/{PHASE}/worker-2/host.json",
    f"state/{MEASUREMENT}/resource-attribution.jsonl",
    f"state/{MEASUREMENT}/resource-attribution-summary.json",
    f"state/{MEASUREMENT}/measurement-contract.json",
    f"state/{MEASUREMENT}/all-sample-resource-gate.json",
    "workload-exit.json",
    "cleanup-complete.json",
    "durable-terminal-manifest.json",
    "workload.log",
    "init-exit.json",
    "evidence-volume-identity.json",
    "pre-inference-gates.json",
    "state/config.json",
    "state/pod-init.json",
}
ALLOWED_PREFIXES = (f"state/{PHASE}/", f"state/{MEASUREMENT}/")

base.STREAM_FILES = STREAM_FILES
base.FINAL_REQUIRED = FINAL_REQUIRED
base.ALLOWED_PREFIXES = ALLOWED_PREFIXES
PodEvidenceIdentity = base.PodEvidenceIdentity
pull_once = base.pull_once


class IncrementalEvidenceMirror(base.IncrementalEvidenceMirror):
    def _path(self, relative: str):
        if relative == "state/aima-pod-cgroup-p-measurement/measurement-contract.json":
            relative = f"state/{MEASUREMENT}/measurement-contract.json"
        return super()._path(relative)
