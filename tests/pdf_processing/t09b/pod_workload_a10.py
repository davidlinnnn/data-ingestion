"""T09b A10 supervisor using retained deadlines and cleanup."""
from pathlib import Path

source = Path(__file__).with_name('pod_workload.py').read_text()
source = source.replace('A6', 'A10').replace('a6', 'a10')
old = "MANIFEST = 'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json'"
if source.count(old) != 1:
    raise RuntimeError('A10 manifest seam changed')
source = source.replace(old, "MANIFEST = 'tests/pdf_processing/t09b/A10-RUNTIME-INTEGRATION-MANIFEST.json'")
exec(compile(source, __file__, 'exec'), globals())
