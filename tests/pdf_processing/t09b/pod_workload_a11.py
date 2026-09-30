from pathlib import Path
source=Path(__file__).with_name('pod_workload.py').read_text().replace('A6','A11').replace('a6','a11')
old="MANIFEST = 'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json'"
if source.count(old)!=1: raise RuntimeError('A11 manifest seam changed')
source=source.replace(old,"MANIFEST = 'tests/pdf_processing/t09b/A11-RUNTIME-INTEGRATION-MANIFEST.json'")
exec(compile(source,__file__,'exec'),globals())
