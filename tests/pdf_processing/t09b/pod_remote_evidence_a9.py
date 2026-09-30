"""Failure-aware A9 evidence export with the required storage ledger."""
from pathlib import Path

source = Path(__file__).with_name('pod_remote_evidence.py').read_text()
source = source.replace('A6', 'A9').replace('a6', 'a9')
exec(compile(source, __file__, 'exec'), globals())
