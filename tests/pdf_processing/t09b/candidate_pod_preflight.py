"""Retain T09b gates while checking the B2 candidate entry points."""
import inspect
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'q04'))
sys.path.insert(0, str(HERE))
import pod_preflight_dh as inherited

inherited.PHASE = inherited.TOPOLOGY_PHASE = 't09b-calibration-b2'
inherited.RUN_ID = 't09b-calibration-20260929-b2'
source = inspect.getsource(inherited.verify_workload_imports_ah)
replacements = {
    '"candidate.warm_pod_window_db"': '"candidate_window"',
    '"pod_workload_db"': '"candidate_pod_workload"',
    '"pod_remote_evidence_db"': '"candidate_pod_remote_evidence", "worker_measurement", "publication_buffers", "storage_ledger", "storage_cost"',
    'tests/pdf_processing/t09a_bounds/normal-topology-dh/RUNTIME-INTEGRATION-MANIFEST.json':
        'tests/pdf_processing/t09b/CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json',
    'from candidate.warm_pod_window_r import validate_contract, validate_scope':
        'from candidate_window import configure_candidate, validate_contract, validate_scope',
    '        "profiles": profiles(inputs, {':
        '        "producer": inputs["producer"],\n        "profiles": profiles(inputs, {',
    '    validate_contract(config, inputs)':
        '    configure_candidate(config, inputs)\n    validate_contract(config, inputs)',
    '            "group_requests": 29,': '            "group_requests": 16,',
}
for old, new in replacements.items():
    if source.count(old) != 1:
        raise RuntimeError('historical preflight import seam changed')
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), vars(inherited))
inherited.base.verify_workload_imports_q = inherited.verify_workload_imports_ah

if __name__ == '__main__':
    raise SystemExit(inherited.main())
