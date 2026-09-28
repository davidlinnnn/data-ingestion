"""Failure-aware B4 evidence export with the required storage ledger."""
from pathlib import Path

source = Path(__file__).with_name('candidate_pod_remote_evidence.py').read_text()
source = source.replace('B2', 'B4').replace('b2', 'b4')
exec(compile(source, __file__, 'exec'), globals())
