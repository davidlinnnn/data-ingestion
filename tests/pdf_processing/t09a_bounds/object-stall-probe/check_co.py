"""Necessary local checks: effective ancestor caps and persisted failing sample."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import normal_topology_co as run
from ancestor_probe_co import violation

root = Path(__file__).resolve().parent
cm = json.loads(gzip.decompress((root/'cm-effective-limit/summary.json.gz').read_bytes()))
baseline = copy.deepcopy(cm['raised'])
baseline['vm'] = {'available': 8*1024**3, 'pressure': 'full avg10=0.00 total=0\n',
                  'stat': {'oom_kill': 0}}
assert violation(baseline, baseline, run.base.VM_RUNTIME_FLOOR_BYTES) is None
row = copy.deepcopy(baseline)
row['levels'][1]['max'] = '536870912'  # Actual CL effective-capacity mistake.
assert violation(row, baseline, run.base.VM_RUNTIME_FLOOR_BYTES) == 'effective object budget changed'
row = copy.deepcopy(baseline)
row['levels'][0]['pressure'] = 'full avg10=0.00 total=999999\n'
assert violation(row, baseline, run.base.VM_RUNTIME_FLOOR_BYTES) == 'object full PSI increased'
with tempfile.TemporaryDirectory() as directory:
    with patch.object(run, 'OUT', Path(directory)), \
         patch.object(run, 'identity', {'pod_uid': 'pod', 'container_id': 'container'}, create=True), \
         patch.object(run.subprocess, 'check_output', return_value=json.dumps(row)):
        run.record['baseline'] = baseline
        try:
            run.checked('test-trigger')
        except ValueError as error:
            assert str(error) == 'object full PSI increased'
        else:
            raise AssertionError('trigger accepted')
        saved = json.loads((Path(directory)/'samples.jsonl').read_text())
        assert saved == run.record['trigger'] and saved['phase'] == 'test-trigger'
print('PASS: effective Pod cap; formal PSI stop; triggering sample persisted before stop')
