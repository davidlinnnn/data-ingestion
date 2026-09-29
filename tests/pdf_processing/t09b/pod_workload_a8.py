"""T09b A8 supervisor using retained deadlines and cleanup."""
from pathlib import Path

source = Path(__file__).with_name('pod_workload_a7.py').read_text().replace('A7', 'A8').replace('a7', 'a8')
exec(compile(source, __file__, 'exec'), globals())
