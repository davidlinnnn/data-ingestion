"""Inspect actual guarded-runner bindings in an isolated interpreter."""
from pathlib import Path
import subprocess
import sys
import unittest


class RuntimeWiringTest(unittest.TestCase):
    def test_actual_runner_targets_fresh_workload_and_evidence(self):
        here = Path(__file__).resolve().parent
        script = f'''
import sys
sys.path.insert(0, {str(here)!r})
from runtime_wiring import configure
r = configure()
for command, filename in ((r.preflight_argv(), 'pod_preflight.py'), (r.workload_argv(), 'pod_workload.py')):
    assert command[1] == '/workspace/tests/pdf_processing/t09b/' + filename
    assert command[command.index('--prefix') + 1] == 't09b/calibration-20260928-a2/'
    assert not any('bounds-dh' in part or 'bounds-20260928-dh' in part for part in command)
scope = r.authorization_scope()
assert scope['phase'] == 't09b-calibration-a2'
assert scope['automatic_retry'] is False
assert scope['workload_seconds'] == 825
assert scope['container_hard_limit_bytes'] == 5368709120
assert scope['expected_parser_generations'] == 2
assert 'state/t09b-calibration-a2/worker-1/storage.jsonl' in r.base.FINAL_REQUIRED
g = r.adapted_window.__globals__
assert g['IncrementalEvidenceMirror'] is r.base.IncrementalEvidenceMirror
assert g['workload_argv']()[1].endswith('/t09b/pod_workload.py')
assert g['OUT'] == r.OUT
assert g['verify_runtime_sample'] is r.base.verify_runtime_sample
deployment = {{'metadata': {{'uid': 'created'}}}}
owned = [{{'kind': 'Deployment', 'name': r.base.DEPLOYMENT, 'uid': 'created'}}]
assert r.base.validate_created_deployment(deployment, owned) is deployment
import inspect
for name in ('validate_pod', 'capture_cleanup_identity', 'await_worker_pod',
             'validate_created_deployment', 'cleanup_deployment_and_pod'):
    assert 't09a-bounds-dh' not in str(inspect.signature(getattr(r.base, name))), name
for entry in (r.offline_check, r.exact_command):
    try:
        entry()
    except RuntimeError as error:
        assert 'not integrated' in str(error)
    else:
        raise AssertionError('historical admission exposed')
print('PASS: guarded runner binding; no runtime executed')
'''
        result = subprocess.run([sys.executable, '-B', '-c', script], cwd='/',
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
