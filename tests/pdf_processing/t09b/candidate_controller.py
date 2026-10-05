"""Run the retained outer controller with the B2 runner and qualifier."""
from pathlib import Path

source = Path(__file__).with_name('controller.py').read_text()
changes = {
    "from qualify_baseline import qualify": "from qualify_candidate import qualify",
    "RUNNER = HERE / 'runner.py'": "RUNNER = HERE / 'candidate_runner.py'",
    "OUT = Path('/private/tmp/t09b-controller-20260929-a6')":
        "OUT = Path('/private/tmp/t09b-controller-20260929-b2')",
    "TRACE_CONTAINER = 't09b-a6-object-stall'": "TRACE_CONTAINER = 't09b-b2-object-stall'",
}
for old, new in changes.items():
    if source.count(old) != 1:
        raise RuntimeError('retained outer controller seam changed')
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
