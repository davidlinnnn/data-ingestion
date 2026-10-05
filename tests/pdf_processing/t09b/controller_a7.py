"""Run the retained outer controller with the A7 runner and qualifier."""
from pathlib import Path

source = Path(__file__).with_name('controller.py').read_text()
for old, new in {
    'A6': 'A7', 'a6': 'a7',
    'from qualify_baseline import qualify': 'from qualify_a7 import qualify',
    "RUNNER = HERE / 'runner.py'": "RUNNER = HERE / 'runner_a7.py'",
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
