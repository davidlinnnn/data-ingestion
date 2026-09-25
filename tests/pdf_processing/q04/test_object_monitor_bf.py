"""Object observer preserves rejected cgroup evidence and binds one Pod."""

import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sentinel.object_monitor_bf import ObjectMonitor, RUN_ID


class ObjectMonitorTest(unittest.TestCase):
    def test_stalled_reader_sets_live_error_without_next_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            monitor = ObjectMonitor(None, Path(tmp) / 'object.jsonl', 536870912)
            monitor.started.set()
            monitor.last_received = time.monotonic() - 2
            monitor.process = SimpleNamespace(poll=lambda: None)
            monitor._watch()
            self.assertIsInstance(monitor.error, TimeoutError)

    def test_failed_remote_stop_still_settles_transport_and_records_error(self):
        class Process:
            returncode = None
            def poll(self):
                return self.returncode
            def wait(self, timeout):
                self.returncode = 0
                return 0
        class Thread:
            def join(self, timeout):
                pass
            def is_alive(self):
                return False
        class Stream:
            closed = False
            def close(self):
                self.closed = True
        with tempfile.TemporaryDirectory() as tmp:
            monitor = ObjectMonitor(None, Path(tmp) / 'object.jsonl', 536870912)
            monitor.identity = {'pod_uid': 'uid', 'container_id': 'cid',
                                'memory_max': 536870912}
            monitor.start_row = {'pid': 1, 'start_ticks': 2}
            monitor.process = Process()
            monitor.thread = Thread()
            monitor.stderr = Stream()
            with patch('sentinel.object_monitor_bf.subprocess.run',
                       side_effect=[TimeoutError('remote stop timeout'), None]) as remote, \
                 patch('sentinel.object_monitor_bf.verify_remote_absence'):
                with self.assertRaisesRegex(RuntimeError, 'cleanup incomplete'):
                    monitor.stop()
            self.assertEqual(remote.call_count, 2)
            self.assertEqual(monitor.process.returncode, 0)
            self.assertTrue(monitor.stderr.closed)
            self.assertFalse(json.loads((Path(tmp) / 'object.cleanup.json')
                                        .read_text())['complete'])

    def test_exited_transport_still_stops_surviving_remote_observer(self):
        class Process:
            returncode = 0
            def poll(self):
                return 0
            def wait(self, timeout):
                return 0
        class Thread:
            def join(self, timeout):
                pass
            def is_alive(self):
                return False
        with tempfile.TemporaryDirectory() as tmp:
            monitor = ObjectMonitor(None, Path(tmp) / 'object.jsonl', 536870912)
            monitor.identity = {'pod_uid': 'uid', 'container_id': 'cid',
                                'memory_max': 536870912}
            monitor.start_row = {'pid': 1, 'start_ticks': 2, 'time': 1}
            monitor.samples = [{'time': 1.25, 'memory_current': 100,
                'memory_events': {'max': 0}, 'object_full_total_us': 0}]
            monitor.end_row = {'run_id': RUN_ID, 'time': 1.5}
            monitor.process = Process()
            monitor.thread = Thread()
            with patch('sentinel.object_monitor_bf.verify_remote_absence',
                       side_effect=[RuntimeError('still running'), None]) as absence, \
                 patch('sentinel.object_monitor_bf.subprocess.run') as remote, \
                 patch('sentinel.object_monitor_bf.object_identity',
                       return_value=monitor.identity):
                result = monitor.stop()
            self.assertEqual(absence.call_count, 2)
            self.assertEqual(remote.call_count, 1)
            self.assertTrue(monitor.cleaned)
            self.assertEqual(result['samples'], 1)

    def test_oom_trigger_sample_is_persisted_before_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            monitor = ObjectMonitor(None, Path(tmp) / 'object.jsonl', 536870912)
            monitor.identity = {'pod_uid': 'uid', 'container_id': 'cid',
                                'memory_max': 536870912}
            start = {'kind': 'start', 'run_id': RUN_ID, 'pid': 1,
                     'start_ticks': 2, 'pod_uid': 'uid', 'container_id': 'cid',
                     'memory_max': 536870912, 'cgroup': '/exact', 'time': 1}
            failed = {'kind': 'sample', 'time': 1.25, 'pod_uid': 'uid',
                      'container_id': 'cid', 'memory_max': 536870912,
                      'cgroup': '/exact', 'memory_current': 100,
                      'memory_events': {'oom': 1, 'oom_kill': 0,
                                        'oom_group_kill': 0},
                      'object_full_total_us': 0, 'node_full_total_us': 0}
            monitor.process = SimpleNamespace(stdout=iter(
                json.dumps(row) + '\n' for row in (start, failed)))
            monitor._read()
            self.assertRegex(str(monitor.error), 'OOM event')
            self.assertEqual(json.loads(monitor.output.read_text().splitlines()[1]), failed)


if __name__ == '__main__':
    unittest.main()
