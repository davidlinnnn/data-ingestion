"""Retain T09b gates while checking the A8 group-5 entry points."""
from pathlib import Path

source = Path(__file__).with_name('pod_preflight_a7.py').read_text().replace('A7', 'A8').replace('a7', 'a8')
exec(compile(source, __file__, 'exec'), globals())
