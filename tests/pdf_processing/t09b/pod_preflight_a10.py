"""Retain T09b gates while checking the A10 group-5 entry points."""
from pathlib import Path

source = Path(__file__).with_name('pod_preflight.py').read_text()
source = source.replace('A6', 'A10').replace('a6', 'a10').replace(
    'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json',
    'tests/pdf_processing/t09b/A10-RUNTIME-INTEGRATION-MANIFEST.json')
exec(compile(source, __file__, 'exec'), globals())
