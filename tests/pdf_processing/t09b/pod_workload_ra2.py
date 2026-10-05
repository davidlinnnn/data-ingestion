from pathlib import Path
source = Path(__file__).with_name('pod_workload.py').read_text()
for old, new in {'A6': 'RA2', 'a6': 'ra2', 'baseline_window.py': 'recovery_window.py', 'tests/pdf_processing/t09b/RUNTIME-INTEGRATION-MANIFEST.json': 'tests/pdf_processing/t09b/RA2-RUNTIME-INTEGRATION-MANIFEST.json'}.items(): source = source.replace(old, new)
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
