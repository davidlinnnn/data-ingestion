"""Reuse failure-aware export with explicit T09b baseline ledger requirements."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'q04'))
sys.path.insert(0, str(HERE))
import pod_remote_evidence_dh as inherited

old_phase = inherited.PHASE
PHASE = 't09b-calibration-a2'
MEASUREMENT = PHASE + '-measurement'
inherited.PHASE = PHASE
inherited.MEASUREMENT = MEASUREMENT
base = inherited.base
base.STREAM_FILES = {name.replace(old_phase, PHASE) for name in inherited.STREAM_FILES}
base.FINAL_REQUIRED = {name.replace(old_phase, PHASE) for name in inherited.FINAL_REQUIRED}
base.ALLOWED_PREFIXES = (f'state/{PHASE}/', f'state/{MEASUREMENT}/')
# The coordinator starts one worker; its parser recycles inside that worker.
ledger = f'state/{PHASE}/worker-1/storage.jsonl'
base.STREAM_FILES.add(ledger)
base.FINAL_REQUIRED.update((ledger, f'state/{PHASE}/worker-1/storage-summary.json'))

PodEvidenceIdentity = inherited.PodEvidenceIdentity
IncrementalEvidenceMirror = inherited.IncrementalEvidenceMirror
IncrementalEvidenceMirror.finalize = inherited._failure_aware_finalize()
pull_once = inherited.pull_once
