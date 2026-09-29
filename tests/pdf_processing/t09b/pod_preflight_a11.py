from pathlib import Path
source=Path(__file__).with_name('pod_preflight.py').read_text().replace('A6','A11').replace('a6','a11').replace('tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json','tests/pdf_processing/t09b/A11-RUNTIME-INTEGRATION-MANIFEST.json')
exec(compile(source,__file__,'exec'),globals())
