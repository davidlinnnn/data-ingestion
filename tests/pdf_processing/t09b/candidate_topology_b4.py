"""Render the inactive T09b group-10 B4 candidate topology."""
from pathlib import Path

source = Path(__file__).with_name('candidate_topology.py').read_text()
for old, new in {
    'B2': 'B4', 'b2': 'b4',
    'candidate_pod_workload.py': 'candidate_pod_workload_b4.py',
    'candidate_pod_preflight.py': 'candidate_pod_preflight_b4.py',
    'candidate_pod_remote_evidence.py': 'candidate_pod_remote_evidence_b4.py',
    'candidate_window.py': 'candidate_window_b4.py',
    'candidate_runner.py': 'candidate_runner_b4.py',
    'candidate_contract.py': 'candidate_contract_b4.py',
    'CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json': 'CANDIDATE-B4-RUNTIME-INTEGRATION-MANIFEST.json',
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())

for name in ('candidate_pod_workload.py', 'candidate_pod_preflight.py',
             'candidate_pod_remote_evidence.py', 'candidate_window.py'):
    base.HARNESS_FILES[f'tests/pdf_processing/t09b/{name}'] = HERE / name
