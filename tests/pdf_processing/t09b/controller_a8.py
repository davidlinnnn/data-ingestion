"""Run the retained outer controller with the A8 runner and qualifier."""
from pathlib import Path

source = Path(__file__).with_name('controller_a7.py').read_text().replace('A7', 'A8').replace('a7', 'a8')
exec(compile(source, __file__, 'exec'), globals())
