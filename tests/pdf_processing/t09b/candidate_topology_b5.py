from pathlib import Path
source=Path(__file__).with_name('candidate_topology.py').read_text()
for old,new in {'B2':'B5','b2':'b5','candidate_pod_workload.py':'candidate_pod_workload_b5.py','candidate_pod_preflight.py':'candidate_pod_preflight_b5.py','candidate_pod_remote_evidence.py':'candidate_pod_remote_evidence_b5.py','candidate_window.py':'candidate_window_b5.py','candidate_runner.py':'candidate_runner_b5.py','candidate_contract.py':'candidate_contract_b5.py','CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json':'CANDIDATE-B5-RUNTIME-INTEGRATION-MANIFEST.json'}.items(): source=source.replace(old,new)
exec(compile(source,__file__,'exec'),globals())
for name in ('candidate_pod_workload.py','candidate_pod_preflight.py','candidate_pod_remote_evidence.py','candidate_window.py'): base.HARNESS_FILES[f'tests/pdf_processing/t09b/{name}']=HERE/name
