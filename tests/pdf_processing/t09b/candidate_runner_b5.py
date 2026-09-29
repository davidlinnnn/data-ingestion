from pathlib import Path
source=Path(__file__).with_name('candidate_runner.py').read_text()
for old,new in {'B2':'B5','b2':'b5',"topology_name='candidate_topology'":"topology_name='candidate_topology_b5'","evidence_name='candidate_pod_remote_evidence'":"evidence_name='candidate_pod_remote_evidence_b5'","preflight_name='candidate_pod_preflight.py'":"preflight_name='candidate_pod_preflight_b5.py'","workload_name='candidate_pod_workload.py'":"workload_name='candidate_pod_workload_b5.py'",'from candidate_contract import':'from candidate_contract_b5 import','CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json':'CANDIDATE-B5-RUNTIME-INTEGRATION-MANIFEST.json'}.items(): source=source.replace(old,new)
exec(compile(source,__file__,'exec'),globals())
