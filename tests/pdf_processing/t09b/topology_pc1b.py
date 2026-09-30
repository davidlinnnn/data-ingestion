from pathlib import Path
source = Path(__file__).with_name('topology.py').read_text()
for old,new in {'A6':'PC1B','a6':'pc1b','pod_workload.py':'pod_workload_pc1b.py','pod_preflight.py':'pod_preflight_pc1b.py','pod_remote_evidence.py':'pod_remote_evidence_pc1b.py','RUNTIME-INTEGRATION-MANIFEST.json':'PC1B-RUNTIME-INTEGRATION-MANIFEST.json'}.items(): source=source.replace(old,new)
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
for name in ('pod_workload.py','pod_preflight.py','pod_remote_evidence.py'): base.HARNESS_FILES[f'tests/pdf_processing/t09b/{name}']=HERE/name

base.HARNESS_FILES['tests/pdf_processing/t09b/cold_window.py'] = HERE/'cold_window.py'
