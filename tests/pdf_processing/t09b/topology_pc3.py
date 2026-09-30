from pathlib import Path
source = Path(__file__).with_name('topology.py').read_text()
for old,new in {'A6':'PC3','a6':'pc3','pod_workload.py':'pod_workload_pc3.py','pod_preflight.py':'pod_preflight_pc3.py','pod_remote_evidence.py':'pod_remote_evidence_pc3.py','RUNTIME-INTEGRATION-MANIFEST.json':'PC3-RUNTIME-INTEGRATION-MANIFEST.json'}.items(): source=source.replace(old,new)
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
for name in ('pod_workload.py','pod_preflight.py','pod_remote_evidence.py'): base.HARNESS_FILES[f'tests/pdf_processing/t09b/{name}']=HERE/name

base.HARNESS_FILES['tests/pdf_processing/t09b/cold_window_pc3.py'] = HERE/'cold_window_pc3.py'

base.HARNESS_FILES['tests/pdf_processing/t09b/cold_window.py'] = HERE/'cold_window.py'
