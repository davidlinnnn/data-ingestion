from pathlib import Path
source=Path(__file__).with_name('candidate_pod_remote_evidence.py').read_text().replace('B2','B5').replace('b2','b5')
exec(compile(source,__file__,'exec'),globals())
