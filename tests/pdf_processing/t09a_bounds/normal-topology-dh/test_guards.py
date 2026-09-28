"""Approved object PSI policy against retained real pressure samples."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'q04'))
from sentinel import run_warm_pod_cgroup_dh as run
from terminal_vm_guard import runtime_psi_is_telemetry, terminal_proofs

EVIDENCE = Path(__file__).parent.parent / 'normal-topology-cr/first-window-evidence'


class GuardTest(unittest.TestCase):
    def setUp(self):
        evidence = json.loads((EVIDENCE / 'pressure-attribution.json').read_text())
        self.first = deepcopy(evidence['first_sample'])
        self.trigger = deepcopy(evidence['first_object_psi']['first'])
        self.vm = deepcopy(evidence['vm_sample_at_stop'])
        for row in (self.first, self.trigger):
            for level in row['ancestors'][:2]:
                level['memory_max'] = '1073741824'
        run.checked_samples = 0
        run.monitor = SimpleNamespace(error=None, samples=[self.first, self.trigger])

    def test_retained_89us_is_telemetry_when_avg10_stays_zero(self):
        run.monitor.samples.append(deepcopy(self.first))
        run.verify_sample(self.vm, 0)
        self.assertEqual(run.monitor.samples[1]['object_full_total_us'], 89)
        self.assertEqual(run.checked_samples, 3)

    def test_sustained_object_pressure_stops_even_after_recovery(self):
        self.trigger['object_full_avg10'] = .01
        run.monitor.samples.append(deepcopy(self.first))
        with self.assertRaisesRegex(ValueError, 'sustained-full-PSI'):
            run.verify_sample(self.vm, 0)

    def test_object_and_vm_failures_still_stop(self):
        for key in ('max', 'oom', 'oom_kill', 'oom_group_kill'):
            with self.subTest(event=key):
                run.checked_samples = 0
                self.trigger['memory_events'] = deepcopy(self.first['memory_events'])
                self.trigger['memory_events'][key] += 1
                with self.assertRaises(ValueError):
                    run.verify_sample(self.vm, 0)
        self.trigger['memory_events'] = deepcopy(self.first['memory_events'])
        for key, value in (('available', run.base.VM_RUNTIME_FLOOR_BYTES - 1),
                           ('psi_full_avg10', .01), ('vm_oom_kill', 1)):
            bad = deepcopy(self.vm); bad[key] = value
            with self.assertRaises(ValueError):
                run.verify_sample(bad, 0)
        run.monitor.error = TimeoutError('object observer lost')
        with self.assertRaises(TimeoutError):
            run.verify_sample(self.vm, 0)

    def test_truncated_object_ancestor_telemetry_stops(self):
        self.trigger['ancestors'] = self.trigger['ancestors'][:1]
        with self.assertRaisesRegex(ValueError, 'telemetry missing'):
            run.verify_sample(self.vm, 0)

    def test_terminal_vm_boundary_requires_all_success_proofs(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            evidence = output / 'evidence'; evidence.mkdir()
            workload = {'returncode': 0, 'timed_out': False, 'forced': False}
            sample = {'available': 10, 'vm_oom_kill': 0, 'memory_current': 5,
                      'psi_full_avg10': 0, 'memory_events': {
                          'max': 0, 'oom': 0, 'oom_kill': 0, 'oom_group_kill': 0}}
            cleanup = {'worker_absent': True, 'owned_children_absent': True,
                       'scratch_absent': True, 'missing_stopped_markers': []}
            (evidence / 'workload-exit.json').write_text(json.dumps(workload))
            (output / 'terminal-cgroup-sample.json').write_text(json.dumps(sample))
            self.assertIsNone(terminal_proofs(output, 0, 10, 5))
            (evidence / 'cleanup-complete.json').write_text(json.dumps(cleanup))
            self.assertIsNotNone(terminal_proofs(output, 0, 10, 5))
            sample['psi_full_avg10'] = .01
            (output / 'terminal-cgroup-sample.json').write_text(json.dumps(sample))
            self.assertIsNone(terminal_proofs(output, 0, 10, 5))

    def test_only_post_terminal_psi_becomes_telemetry(self):
        row = {'available': 10, 'vm_oom_kill': 0, 'psi_full_avg10': .18}
        with self.assertRaisesRegex(ValueError, 'PSI'):
            runtime_psi_is_telemetry(row, 0, 10, None)
        self.assertTrue(runtime_psi_is_telemetry(row, 0, 10, {'complete': True}))
        for changed in ({'available': 9}, {'vm_oom_kill': 1}):
            with self.subTest(changed=changed):
                bad = {**row, **changed}
                with self.assertRaisesRegex(ValueError, 'memory/OOM'):
                    runtime_psi_is_telemetry(bad, 0, 10, {'complete': True})

    def test_inner_final_cleanup_keeps_oom_and_floor_fatal(self):
        row = {'available': run.base.VM_RUNTIME_FLOOR_BYTES,
               'vm_oom_kill': 0, 'psi_full_avg10': .18}
        self.assertEqual(run.post_cleanup_vm_guard(row, 0), {
            'full_psi_avg10': .18, 'mode': 'telemetry'})
        for changed in ({'available': row['available'] - 1}, {'vm_oom_kill': 1}):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(ValueError, 'OOM/floor'):
                    run.post_cleanup_vm_guard({**row, **changed}, 0)


if __name__ == '__main__':
    unittest.main()
