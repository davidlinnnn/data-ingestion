"""Retain DH resource gates while checking the actual T09b entry points."""
import inspect
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'q04'))
sys.path.insert(0, str(HERE))
import pod_preflight_dh as inherited

inherited.PHASE = inherited.TOPOLOGY_PHASE = 't09b-calibration-a5'
inherited.RUN_ID = 't09b-calibration-20260928-a5'
source = inspect.getsource(inherited.verify_workload_imports_ah)
replacements = {
    '"candidate.warm_pod_window_db"': '"baseline_window"',
    '"pod_workload_db"': '"pod_workload"',
    '"pod_remote_evidence_db"': '"pod_remote_evidence", "worker_measurement", "publication_buffers", "storage_ledger"',
    'tests/pdf_processing/t09a_bounds/normal-topology-dh/RUNTIME-INTEGRATION-MANIFEST.json':
        'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json',
}
for old, new in replacements.items():
    if source.count(old) != 1:
        raise RuntimeError('historical preflight import seam changed')
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), vars(inherited))
inherited.base.verify_workload_imports_q = inherited.verify_workload_imports_ah

if __name__ == '__main__':
    raise SystemExit(inherited.main())
