"""T09b B4 supervisor using retained deadlines and cleanup."""
from pathlib import Path

source = Path(__file__).with_name('candidate_pod_workload.py').read_text()
for old, new in {
    'B2': 'B4', 'b2': 'b4',
    'candidate_window.py': 'candidate_window_b4.py',
    'CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json': 'CANDIDATE-B4-RUNTIME-INTEGRATION-MANIFEST.json',
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
