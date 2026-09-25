"""Q evidence paths over P's identity-fenced transport implementation."""

import pod_remote_evidence_p as base


PHASE = "aima-pod-cgroup-q"
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
    f"state/{PHASE}/fresh-index.json",
    *{
        f"state/{PHASE}/{mode}-08/{name}"
        for mode in ("fresh", "restored", "replay")
        for name in ("accepted.json", "document.json", "source-image-supplement.json")
    },
    f"state/{MEASUREMENT}/resource-attribution.jsonl",
    f"state/{MEASUREMENT}/resource-attribution-summary.json",
    f"state/{MEASUREMENT}/measurement-contract.json",
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
