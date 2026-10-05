"""Inspect actual guarded-runner bindings in an isolated interpreter."""
from pathlib import Path
import subprocess
import sys
import unittest


class RuntimeWiringTest(unittest.TestCase):
    def test_actual_runner_targets_fresh_workload_and_evidence(self):
        here = Path(__file__).resolve().parent
        script = f'''
from pathlib import Path
import sys
sys.path.insert(0, {str(here)!r})
here = Path({str(here)!r})
from runtime_wiring import configure
r = configure()
for command, filename in ((r.preflight_argv(), 'pod_preflight.py'), (r.workload_argv(), 'pod_workload.py')):
    assert command[1] == '/workspace/tests/pdf_processing/t09b/' + filename
    assert command[command.index('--prefix') + 1] == 't09b/calibration-20260929-a6/'
    assert not any('bounds-dh' in part or 'bounds-20260928-dh' in part for part in command)
scope = r.authorization_scope()
assert scope['phase'] == 't09b-calibration-a6'
assert scope['automatic_retry'] is False
assert scope['workload_seconds'] == 825
assert scope['container_hard_limit_bytes'] == 5368709120
assert scope['expected_parser_generations'] == 2
assert 'state/t09b-calibration-a6/worker-1/storage.jsonl' in r.base.FINAL_REQUIRED
g = r.adapted_window.__globals__
assert g['IncrementalEvidenceMirror'] is r.base.IncrementalEvidenceMirror
assert g['workload_argv']()[1].endswith('/t09b/pod_workload.py')
assert g['OUT'] == r.OUT
assert g['verify_runtime_sample'] is r.base.verify_runtime_sample
assert 'supervisor_start_confirmed' in r.adapted_window.__code__.co_varnames
assert set(('startup_identity', 'base_runtime_guard')) <= set(r.adapted_window.__code__.co_names)
import subprocess, tarfile, tempfile
with tempfile.TemporaryDirectory() as temp:
    with tarfile.open(here / 'a2-evidence/retained-pvc.tar.gz') as archive:
        archive.extractall(temp, filter='data')
    evidence = str(Path(temp) / 't09b-calibration-20260928-a2')
    class LocalChannel:
        def run(self, program):
            result = subprocess.run([sys.executable, '-B', '-c', program],
                                    capture_output=True, text=True, check=True)
            return result.stdout.strip()
    owner = g['startup_identity'](LocalChannel(), evidence)
    assert owner['pid'] is not None and owner['start_ticks'] is not None
    assert owner['config_sha256'] is not None
    (Path(evidence) / 'ownership.json').unlink()
    owner = g['startup_identity'](LocalChannel(), evidence)
    assert owner['pid'] is not None and owner['start_ticks'] is not None
    assert owner['config_sha256'] is None
    status, detail = r.base.workload_evidence_classification(
        supervisor_identity_published=True, evidence_captured=False)
    assert status == 'INCOMPLETE' and detail['supervisor'] == 'START_CONFIRMED'
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

    def test_actual_entrypoint_keeps_race_fix_and_a4_policy(self):
        here = Path(__file__).resolve().parent
        script = f'''
import importlib.util
from pathlib import Path
from types import SimpleNamespace
spec = importlib.util.spec_from_file_location('t09b_test_runner', Path({str(here)!r}) / 'runner.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
r = module.runner
assert 'supervisor_start_confirmed' in r.adapted_window.__code__.co_varnames
assert r.verify_object_monitor is module.verify_object_monitor_a4
assert r.OBJECT_PSI_POLICY['memory_events_max'] == 'recorded_boundary_event_not_immediate_stop'
assert r.OBJECT_PSI_POLICY['node_full_psi_avg10'] == 'runtime_telemetry_not_immediate_stop'
assert r.OBJECT_PSI_POLICY['diagnostic_only'] is True
assert r.authorization_scope()['automatic_retry'] is False
events = dict(max=10, oom=0, oom_kill=0, oom_group_kill=0)
ancestor = dict(memory_max=str(r.object_trial.TRIAL_BYTES), events_local=events)
first = dict(object_full_avg10=0, memory_events=events,
             ancestors=[ancestor, ancestor])
later_events = {{**events, 'max': 11}}
later = dict(object_full_avg10=0, memory_events=later_events,
             ancestors=[dict(memory_max=str(r.object_trial.TRIAL_BYTES),
                             events_local=later_events), ancestor])
r.monitor = SimpleNamespace(samples=[first, later], error=None)
r.checked_samples = 0
r.verify_object_monitor()
assert r.checked_samples == 2
r.monitor = SimpleNamespace(samples=[first, {{**later, 'object_full_avg10': 0.1}}], error=None)
r.checked_samples = 0
try:
    r.verify_object_monitor()
except ValueError as error:
    assert 'PSI' in str(error)
else:
    raise AssertionError('positive object full PSI did not stop A4')
row = dict(available=r.base.VM_RUNTIME_FLOOR_BYTES, psi_full_avg10=0.2,
           vm_oom_kill=0, memory_events={{'oom': 0, 'oom_kill': 0, 'oom_group_kill': 0}},
           memory_current=r.base.CGROUP_GUARD_BYTES,
           evidence_used_bytes=0, evidence_free_bytes=134217728,
           evidence_filesystem_free_bytes=134217728)
module.verify_runtime_sample_a4(row, 0)
try:
    module.verify_runtime_sample_a4({{**row, 'vm_oom_kill': 1}}, 0)
except ValueError as error:
    assert 'OOM' in str(error)
else:
    raise AssertionError('VM OOM did not stop A4')
print('PASS: A4 retains hard guards while node full PSI is telemetry')
'''
        result = subprocess.run([sys.executable, '-B', '-c', script], cwd='/',
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
