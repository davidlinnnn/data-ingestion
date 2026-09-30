from pathlib import Path
source = Path(__file__).with_name('topology.py').read_text()
for old, new in {'A6': 'RA1', 'a6': 'ra1', 'pod_workload.py': 'pod_workload_ra1.py', 'pod_preflight.py': 'pod_preflight_ra1.py', 'pod_remote_evidence.py': 'pod_remote_evidence_ra1.py', 'RUNTIME-INTEGRATION-MANIFEST.json': 'RA1-RUNTIME-INTEGRATION-MANIFEST.json'}.items(): source = source.replace(old, new)
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
for name in ('pod_workload.py', 'pod_preflight.py', 'pod_remote_evidence.py', 'recovery_window.py', 'recovery_trial.py'):
    base.HARNESS_FILES[f'tests/pdf_processing/t09b/{name}'] = HERE/name
base.HARNESS_FILES['tests/pdf_processing/q04/candidate/process_drain_window_be.py'] = HERE.parent/'q04/candidate/process_drain_window_be.py'
base.HARNESS_FILES['tests/pdf_processing/q04/pod_remote_evidence_be.py'] = HERE.parent/'q04/pod_remote_evidence_be.py'
