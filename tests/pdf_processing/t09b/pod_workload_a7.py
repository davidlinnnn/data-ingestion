"""T09b A7 supervisor using retained deadlines and cleanup."""
from pathlib import Path

source = Path(__file__).with_name('pod_workload.py').read_text()
source = source.replace('A6', 'A7').replace('a6', 'a7')
old = "MANIFEST = 'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json'"
if source.count(old) != 1:
    raise RuntimeError('A7 manifest seam changed')
source = source.replace(old, "MANIFEST = 'tests/pdf_processing/t09b/A7-RUNTIME-INTEGRATION-MANIFEST.json'")
exec(compile(source, __file__, 'exec'), globals())
