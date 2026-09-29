"""Failure-aware A8 evidence export with the required storage ledger."""
from pathlib import Path

source = Path(__file__).with_name('pod_remote_evidence_a7.py').read_text().replace('A7', 'A8').replace('a7', 'a8')
exec(compile(source, __file__, 'exec'), globals())
