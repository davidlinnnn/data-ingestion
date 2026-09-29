"""Prepare or execute one guarded T09b A8 group-5 baseline."""
from pathlib import Path

source = Path(__file__).with_name('runner_a7.py').read_text().replace('A7', 'A8').replace('a7', 'a8')
exec(compile(source, __file__, 'exec'), globals())
