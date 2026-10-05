"""Prepare or execute one guarded T09b A10 group-5 diagnostic."""
from pathlib import Path

source = Path(__file__).with_name('runner.py').read_text()
for old, new in {
    'A6': 'A10', 'a6': 'a10',
    'runner = configure()': "runner = configure(topology_name='topology_a10', evidence_name='pod_remote_evidence_a10', identity='t09b-calibration-20260929-a10', record_name='runtime-a10', preflight_name='pod_preflight_a10.py', workload_name='pod_workload_a10.py')",
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
