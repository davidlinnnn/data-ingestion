"""Actual retained PSI trigger and qualification observer-loss behavior."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import subprocess
import time
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'q04'))
from sentinel import run_warm_pod_cgroup_dc as run
from observer_guard import verify_observer, stop_program

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

    def test_retained_89us_trigger_stops_even_after_recovery(self):
        run.monitor.samples.append(deepcopy(self.first))
        with self.assertRaisesRegex(ValueError, 'new-full-PSI'):
            run.verify_sample(self.vm, 0)
        self.assertEqual(run.monitor.samples[1]['object_full_total_us'], 89)

    def test_zero_delta_passes_with_actual_unprotected_cgroups(self):
        self.trigger['object_full_total_us'] = self.first['object_full_total_us']
        for row in run.monitor.samples:
            for level in row['ancestors']:
                level['memory_low'] = '0'
        run.verify_sample(self.vm, 0)

    def test_object_and_vm_failures_still_stop(self):
        self.trigger['object_full_total_us'] = self.first['object_full_total_us']
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

    def test_auxiliary_exit_or_stall_stops_qualification(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'samples.jsonl'
            path.write_text('{"kind":"sample","ended_at":10}\n')
            process = SimpleNamespace(poll=lambda: None)
            verify_observer(process, path, now=11)
            with self.assertRaises(TimeoutError):
                verify_observer(process, path, now=16)
            process.poll = lambda: 1
            with self.assertRaises(RuntimeError):
                verify_observer(process, path, now=11)

    @unittest.skipUnless(Path('/proc').exists(), 'remote cleanup needs Linux procfs')
    def test_auxiliary_cleanup_without_start_identity(self):
        identity = 'dc-observer-cleanup-regression'
        child = subprocess.Popen([sys.executable, '-u', '-', '--run-id', identity],
                                 stdin=subprocess.PIPE, text=True)
        try:
            child.stdin.write('import time; time.sleep(30)\n')
            child.stdin.close()
            time.sleep(.1)
            subprocess.run([sys.executable, '-c', stop_program(identity, None)],
                           check=True, timeout=10)
            self.assertEqual(child.wait(timeout=2), -15)
        finally:
            if child.poll() is None:
                child.kill(); child.wait()


if __name__ == '__main__':
    unittest.main()
