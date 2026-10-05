"""B3 group-10 window bound to the B3 identity contract."""
from pathlib import Path

source = Path(__file__).with_name('candidate_window.py').read_text()
if source.count('from candidate_contract import IDENTITY, SCOPE') != 1:
    raise RuntimeError('candidate window contract seam changed')
source = source.replace('from candidate_contract import IDENTITY, SCOPE',
                        'from candidate_contract_b3 import IDENTITY, SCOPE')
exec(compile(source, __file__, 'exec'), globals())
