from pathlib import Path
source = Path(__file__).with_name('topology.py').read_text()
for old,new in {'A6':'A12','a6':'a12','pod_workload.py':'pod_workload_a12.py','pod_preflight.py':'pod_preflight_a12.py','pod_remote_evidence.py':'pod_remote_evidence_a12.py','RUNTIME-INTEGRATION-MANIFEST.json':'A12-RUNTIME-INTEGRATION-MANIFEST.json'}.items(): source=source.replace(old,new)
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
for name in ('pod_workload.py','pod_preflight.py','pod_remote_evidence.py'): base.HARNESS_FILES[f'tests/pdf_processing/t09b/{name}']=HERE/name
