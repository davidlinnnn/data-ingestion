from pathlib import Path
source=Path(__file__).with_name('candidate_pod_preflight.py').read_text()
for old,new in {'B2':'B5','b2':'b5','candidate_window':'candidate_window_b5','candidate_pod_workload"':'candidate_pod_workload_b5"','candidate_pod_remote_evidence"':'candidate_pod_remote_evidence_b5"','CANDIDATE-RUNTIME-INTEGRATION-MANIFEST.json':'CANDIDATE-B5-RUNTIME-INTEGRATION-MANIFEST.json'}.items(): source=source.replace(old,new)
exec(compile(source,__file__,'exec'),globals())
