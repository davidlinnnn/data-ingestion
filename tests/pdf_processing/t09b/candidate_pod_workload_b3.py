"""T09b B3 supervisor using retained deadlines and cleanup."""
from pathlib import Path

source = Path(__file__).with_name('candidate_pod_workload.py').read_text()
for old, new in {
    'B2': 'B3', 'b2': 'b3',
    'candidate_window.py': 'candidate_window_b3.py',
    'CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json': 'CANDIDATE-B3-RUNTIME-INTEGRATION-MANIFEST.json',
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
