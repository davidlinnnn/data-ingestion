"""Retain T09b gates while checking the B3 candidate entry points."""
from pathlib import Path

source = Path(__file__).with_name('candidate_pod_preflight.py').read_text()
for old, new in {
    'B2': 'B3', 'b2': 'b3',
    'candidate_pod_workload"': 'candidate_pod_workload_b3"',
    'candidate_pod_remote_evidence"': 'candidate_pod_remote_evidence_b3"',
    'CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json': 'CANDIDATE-B3-RUNTIME-INTEGRATION-MANIFEST.json',
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
