from pathlib import Path
source=Path(__file__).with_name('pod_remote_evidence.py').read_text().replace('A6','A12').replace('a6','a12')
source = source.replace('20260929', '20260930')
exec(compile(source,__file__,'exec'),globals())
