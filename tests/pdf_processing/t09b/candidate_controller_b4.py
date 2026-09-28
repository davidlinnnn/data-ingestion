"""Run the retained outer controller with the B4 runner and qualifier."""
from pathlib import Path

source = Path(__file__).with_name('candidate_controller.py').read_text()
for old, new in {
    'B2': 'B4', 'b2': 'b4',
    "from qualify_candidate import qualify": "from qualify_candidate_b4 import qualify",
    "RUNNER = HERE / 'candidate_runner.py'": "RUNNER = HERE / 'candidate_runner_b4.py'",
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
