"""Run the retained outer controller with the B3 runner and qualifier."""
from pathlib import Path

source = Path(__file__).with_name('candidate_controller.py').read_text()
for old, new in {
    'B2': 'B3', 'b2': 'b3',
    "from qualify_candidate import qualify": "from qualify_candidate_b3 import qualify",
    "RUNNER = HERE / 'candidate_runner.py'": "RUNNER = HERE / 'candidate_runner_b3.py'",
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
