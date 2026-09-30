from pathlib import Path
source=Path(__file__).with_name('pod_workload.py').read_text().replace('A6','PC1B').replace('a6','pc1b').replace('baseline_window.py','cold_window.py')
old="MANIFEST = 'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json'"
if source.count(old)!=1: raise RuntimeError('PC1B manifest seam changed')
source=source.replace(old,"MANIFEST = 'tests/pdf_processing/t09b/PC1B-RUNTIME-INTEGRATION-MANIFEST.json'")
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
