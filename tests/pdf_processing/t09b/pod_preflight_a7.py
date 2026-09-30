"""Retain T09b gates while checking the A7 group-5 entry points."""
from pathlib import Path

source = Path(__file__).with_name('pod_preflight.py').read_text()
source = source.replace('A6', 'A7').replace('a6', 'a7').replace(
    'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json',
    'tests/pdf_processing/t09b/A7-RUNTIME-INTEGRATION-MANIFEST.json')
exec(compile(source, __file__, 'exec'), globals())
