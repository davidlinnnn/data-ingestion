"""Evidence paths for the corrected Q04 warm sequence."""

import importlib.util
from pathlib import Path
import sys


_spec = importlib.util.spec_from_file_location(
    "q04_pod_remote_evidence_ab_engine",
    Path(__file__).with_name("pod_remote_evidence_p.py"),
)
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base
_spec.loader.exec_module(base)


PHASE = "warm-pod-cgroup-ab"
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
    f"state/{PHASE}/warm-output-index.json",
    f"state/{PHASE}/warm-proof.json",
    *{
        f"state/{PHASE}/{label}/{name}"
        for label in (
            "warm-0-06", "warm-1-07", "warm-2-08", "warm-3-native", "warm-4-06",
        )
        for name in ("accepted.json", "document.json")
    },
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

