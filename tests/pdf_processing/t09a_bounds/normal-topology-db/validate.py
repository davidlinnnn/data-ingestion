"""Necessary offline checks for the new full-window identity; no cluster changes."""
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
Q04 = ROOT / 'tests/pdf_processing/q04'
sys.path.insert(0, str(Q04))
from sentinel import run_warm_pod_cgroup_db as run
from prepare import verify_bundle
from candidate.warm_v3_reference_db import verify_v3_bundle
import pod_workload_db as workload

assert run.offline_check()['status'] == 'PASS_OFFLINE_ONLY'
assert run.base.parser().parse_args(shlex.split(run.exact_command())[2:]).execute
verify_bundle(run.BUNDLE)
verify_v3_bundle(run.BUNDLE)
old = json.loads(Path('/private/tmp/q44-inputs-warm-20260927-cd/inputs.json').read_text())
new = json.loads((run.BUNDLE/'inputs.json').read_text())
assert new['producer']['ocr.py'] != old['producer']['ocr.py']
new['producer']['ocr.py'] = old['producer']['ocr.py']
assert new == old
assert 'sitecustomize' not in ''.join(run.topology.base.HARNESS_FILES)
# Replay existing pressure regression cases against the actual DB guard.
import test_object_psi_diagnostic_cs as guards
guards.run = run
result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromModule(guards))
assert result.wasSuccessful()
with tempfile.TemporaryDirectory() as temp:
    state = Path(temp); root = state/workload.PHASE
    root.mkdir(); (root/'worker-1.log').write_text('worker log')
    worker = root/'worker-1'; worker.mkdir()
    assert not workload.cleanup_markers(state)['worker_absent']
    (worker/'stopped.json').write_text(json.dumps({'parser_absent':True,'scratch_absent':True}))
    assert workload.cleanup_markers(state)['worker_absent']
print('PASS: exact argv, OCR-only bundle delta, unchanged oracle, actual guards, cleanup with log')
