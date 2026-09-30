from pathlib import Path
source=Path(__file__).with_name('pod_remote_evidence.py').read_text().replace('A6','A11').replace('a6','a11')
exec(compile(source,__file__,'exec'),globals())
