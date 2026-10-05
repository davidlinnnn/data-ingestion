from pathlib import Path
source=Path(__file__).with_name('pod_workload.py').read_text().replace('A6','PC2').replace('a6','pc2').replace('baseline_window.py','cold_window_pc2.py')
old="MANIFEST = 'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json'"
if source.count(old)!=1: raise RuntimeError('PC2 manifest seam changed')
source=source.replace(old,"MANIFEST = 'tests/pdf_processing/t09b/PC2-RUNTIME-INTEGRATION-MANIFEST.json'")
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
