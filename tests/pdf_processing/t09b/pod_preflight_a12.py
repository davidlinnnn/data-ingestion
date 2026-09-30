from pathlib import Path
source=Path(__file__).with_name('pod_preflight.py').read_text().replace('A6','A12').replace('a6','a12').replace('tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json','tests/pdf_processing/t09b/A12-RUNTIME-INTEGRATION-MANIFEST.json')
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
