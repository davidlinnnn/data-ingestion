"""Prepare or execute one guarded T09b A9 group-5 baseline."""
from pathlib import Path

source = Path(__file__).with_name('runner.py').read_text()
for old, new in {
    'A6': 'A9', 'a6': 'a9',
    'runner = configure()': "runner = configure(topology_name='topology_a9', evidence_name='pod_remote_evidence_a9', identity='t09b-calibration-20260929-a9', record_name='runtime-a9', preflight_name='pod_preflight_a9.py', workload_name='pod_workload_a9.py')",
}.items():
    source = source.replace(old, new)
exec(compile(source, __file__, 'exec'), globals())
