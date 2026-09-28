"""Render the inactive T09b group-10 B3 candidate topology."""
from pathlib import Path

source = Path(__file__).with_name('candidate_topology.py').read_text()
for old, new in {
    'B2': 'B3', 'b2': 'b3',
    'candidate_pod_workload.py': 'candidate_pod_workload_b3.py',
    'candidate_pod_preflight.py': 'candidate_pod_preflight_b3.py',
    'candidate_pod_remote_evidence.py': 'candidate_pod_remote_evidence_b3.py',
    'candidate_runner.py': 'candidate_runner_b3.py',
    'candidate_contract.py': 'candidate_contract_b3.py',
    'CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json': 'CANDIDATE-B3-RUNTIME-INTEGRATION-MANIFEST.json',
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())

# The B3 entry points are thin source-transform wrappers. Their immutable B2
# templates must be projected beside them; they are not executable entry points.
for name in ('candidate_pod_workload.py', 'candidate_pod_preflight.py',
             'candidate_pod_remote_evidence.py'):
    base.HARNESS_FILES[f'tests/pdf_processing/t09b/{name}'] = HERE / name
