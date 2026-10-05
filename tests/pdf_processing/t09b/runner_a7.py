"""Prepare or execute one guarded T09b A7 group-5 baseline."""
from pathlib import Path

source = Path(__file__).with_name('runner.py').read_text()
for old, new in {
    'A6': 'A7', 'a6': 'a7',
    'runner = configure()': "runner = configure(topology_name='topology_a7', evidence_name='pod_remote_evidence_a7', identity='t09b-calibration-20260929-a7', record_name='runtime-a7', preflight_name='pod_preflight_a7.py', workload_name='pod_workload_a7.py')",
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
