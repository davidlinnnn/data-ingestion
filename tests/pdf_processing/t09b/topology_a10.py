"""Render the inactive T09b A10 group-5 baseline topology."""
from pathlib import Path

source = Path(__file__).with_name('topology.py').read_text()
for old, new in {
    'A6': 'A10', 'a6': 'a10',
    'pod_workload.py': 'pod_workload_a10.py',
    'pod_preflight.py': 'pod_preflight_a10.py',
    'pod_remote_evidence.py': 'pod_remote_evidence_a10.py',
    'RUNTIME-INTEGRATION-MANIFEST.json': 'A10-RUNTIME-INTEGRATION-MANIFEST.json',
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
for name in ('pod_workload.py', 'pod_preflight.py', 'pod_remote_evidence.py'):
    base.HARNESS_FILES[f'tests/pdf_processing/t09b/{name}'] = HERE / name
