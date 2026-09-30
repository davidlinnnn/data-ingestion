"""Prepare or execute one guarded T09b A8 group-5 baseline."""
from pathlib import Path

source = Path(__file__).with_name('runner.py').read_text()
for old, new in {
    'A6': 'A8', 'a6': 'a8',
    'runner = configure()': "runner = configure(topology_name='topology_a8', evidence_name='pod_remote_evidence_a8', identity='t09b-calibration-20260929-a8', record_name='runtime-a8', preflight_name='pod_preflight_a8.py', workload_name='pod_workload_a8.py')",
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
