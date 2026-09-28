"""Render the inactive T09b group-10 B1 candidate topology."""
from pathlib import Path

import topology as baseline

base = baseline.base
base.PHASE = 't09b-calibration-b1'
base.DEPLOYMENT = base.PHASE + '-activities'
base.RUN_LABEL = base.PHASE
base.WORKFLOW_QUEUE = base.PHASE + '-workflows'
base.ACTIVITY_QUEUE = base.PHASE + '-08'
base.OBJECT_PREFIX = 't09b/calibration-20260929-b1/'
base.EVIDENCE_PVC = 't09b-calibration-b1-evidence-20260929'
base.EVIDENCE_DIRECTORY_NAME = 't09b-calibration-20260929-b1'
HERE = Path(__file__).resolve().parent
for name in ('candidate_window.py', 'candidate_pod_workload.py',
             'candidate_pod_preflight.py', 'candidate_pod_remote_evidence.py',
             'candidate_runner.py', 'candidate_contract.py', 'storage_cost.py',
             'CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json'):
    base.HARNESS_FILES[f'tests/pdf_processing/t09b/{name}'] = HERE / name
