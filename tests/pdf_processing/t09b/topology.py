"""Render inactive T09b A1 source projection using the accepted resource layout.

Run in its own process: the historical topology builders use module globals.
This does not authorize or implement the coordinator's runtime launch.
"""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'q04'))
import pod_topology_db

base = pod_topology_db.base
base.PHASE = 't09b-calibration-a1'
base.DEPLOYMENT = base.PHASE + '-activities'
base.RUN_LABEL = base.PHASE
base.WORKFLOW_QUEUE = base.PHASE + '-workflows'
base.ACTIVITY_QUEUE = base.PHASE + '-08'
base.OBJECT_PREFIX = 't09b/calibration-20260928-a1/'
base.EVIDENCE_PVC = 't09b-calibration-a1-evidence-20260928'
base.EVIDENCE_DIRECTORY_NAME = 't09b-calibration-20260928-a1'
FILES = ('worker.py', 't09b_host.py', 'baseline_window.py', 'worker_measurement.py',
         'storage_measurement.py', 'storage_ledger.py', 'publication_buffers.py', 'topology.py',
         'pod_workload.py', 'pod_preflight.py', 'pod_remote_evidence.py', 'RUNTIME-INTEGRATION-MANIFEST.json')
base.HARNESS_FILES.update({f'tests/pdf_processing/t09b/{name}': HERE/name
                           for name in FILES})
for name in ('pod_preflight_dh.py', 'pod_remote_evidence_dh.py', 'host_be.py', 'host_bc.py'):
    base.HARNESS_FILES[f'tests/pdf_processing/q04/{name}'] = HERE.parent / 'q04' / name


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    base.render(args.out/'inactive-topology.json', args.out/'source-manifest.json')
    print('PASS: inactive topology; runtime coordinator not yet wired')
