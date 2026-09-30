"""Prepare or execute one guarded T09b group-10 B3 candidate."""
from pathlib import Path

source = Path(__file__).with_name('candidate_runner.py').read_text()
for old, new in {
    'B2': 'B3', 'b2': 'b3',
    "topology_name='candidate_topology'": "topology_name='candidate_topology_b3'",
    "evidence_name='candidate_pod_remote_evidence'": "evidence_name='candidate_pod_remote_evidence_b3'",
    "preflight_name='candidate_pod_preflight.py'": "preflight_name='candidate_pod_preflight_b3.py'",
    "workload_name='candidate_pod_workload.py'": "workload_name='candidate_pod_workload_b3.py'",
    'from candidate_contract import': 'from candidate_contract_b3 import',
    'CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json': 'CANDIDATE-B3-RUNTIME-INTEGRATION-MANIFEST.json',
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
