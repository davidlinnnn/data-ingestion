from pathlib import Path
source=Path(__file__).with_name('candidate_window.py').read_text()
old='from candidate_contract import IDENTITY, SCOPE'
if source.count(old)!=1: raise RuntimeError('candidate window contract seam changed')
source=source.replace(old,'from candidate_contract_b5 import IDENTITY, SCOPE')
exec(compile(source,__file__,'exec'),globals())
