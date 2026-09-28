"""The measured Activity Pod publishes control proof without new execs."""

import hashlib
import asyncio
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from unittest.mock import Mock

import pod_activity_supervisor_bh as bh


class ActivityControlTest(unittest.TestCase):
    def test_cleanup_observation_requires_worker_stop_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            collector = Mock()
            with self.assertRaises(Exception):
                bh.record_owned_cleanup(collector, root, 2)
            stopped = root / 'worker-2/stopped.json'
            stopped.parent.mkdir()
            stopped.write_text(json.dumps({'generation': 2,
                'parser_absent': True, 'scratch_absent': True}))
            bh.record_owned_cleanup(collector, root, 2)
            collector.observe.assert_called_once_with('owned_cleanup_finished',
                source='pod_activity_supervisor_bh',
                meaning='worker_returned_after_owned_cleanup')

    def test_activity_exec_disables_thp_before_worker_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'evidence/state/pod-loss-pod-cgroup-bh'
            root.mkdir(parents=True)
            config = root / 'config.json'
            config.write_text(json.dumps({
                'run_id': 'q04-pod-loss-pod-cgroup-20260926-bh',
                'pod_namespace': 'pdf-t09a-validation',
                'python': '/experiment/.venv/bin/python'}))
            marker = root.parent / 'pod-loss-pod-cgroup-bh-measurement/worker-1/activity-memory-policy.json'
            def spawn(*_args, **_kwargs):
                self.assertEqual(json.loads(marker.read_text())['thp_disabled'], 1)
                raise RuntimeError('stop before worker spawn')
            read_text = Path.read_text
            def read(path, *args, **kwargs):
                if str(path) == '/proc/self/stat':
                    return '1 (python) S ' + '0 ' * 22
                return read_text(path, *args, **kwargs)
            with patch.object(bh, 'disable_thp', create=True,
                              return_value={'thp_disabled': 1,
                                            'inherited_by_children': True}) as policy, \
                 patch.object(bh, 'StrictAttributionCollector') as collector, \
                 patch.object(Path, 'read_text', new=read), \
                 patch.object(bh.subprocess, 'Popen', side_effect=spawn):
                with self.assertRaisesRegex(RuntimeError, 'stop before worker spawn'):
                    asyncio.run(bh.run(config, root, 1))
            policy.assert_called_once()
            collector.return_value.start.assert_called_once()

    def test_worker_proof_and_parser_hold_are_published_in_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'evidence/state/pod-loss-pod-cgroup-bh'
            worker_root = root / 'worker-1'
            measurement = root.parent / 'pod-loss-pod-cgroup-bh-measurement/worker-1'
            worker_root.mkdir(parents=True)
            measurement.mkdir(parents=True)
            config = b'{"run_id":"bh"}'
            (root / 'config.json').write_bytes(config)
            ready = {'generation': 1, 'pid': 123, 'created': 4.0,
                     'time': time.time(), 'config_sha256': hashlib.sha256(config).hexdigest()}
            ready_raw = json.dumps(ready).encode()
            (worker_root / 'ready.json').write_bytes(ready_raw)
            first = (json.dumps({'generation': 1, 'time': ready['time'] - .1}) + '\n').encode()
            (worker_root / 'samples.jsonl').write_bytes(first)
            parent = SimpleNamespace(pid=123, create_time=lambda: 4.0,
                cmdline=lambda: ['/workspace/tests/pdf_processing/q04/worker_bc.py'])
            child = SimpleNamespace(pid=456, parents=lambda: [parent],
                cmdline=lambda: ['python', 'pdf_processing.warm_child'],
                status=lambda: bh.psutil.STATUS_STOPPED)
            def process(pid):
                return {123: parent, 456: child}[pid]
            with patch.object(bh.psutil, 'Process', side_effect=process):
                self.assertTrue(bh.publish_worker_proof(root, measurement, 1,
                    SimpleNamespace(pid=123)))
            proof = json.loads((measurement / 'worker-proof.json').read_text())
            self.assertEqual(proof['first_sample_sha256'], hashlib.sha256(first).hexdigest())
            self.assertEqual(proof['ready_sha256'], hashlib.sha256(ready_raw).hexdigest())
            (measurement / 'hold-request.json').write_text(json.dumps({
                'run_id': 'q04-pod-loss-pod-cgroup-20260926-bh',
                'generation': 1, 'child_pid': 456,
                'old_pod_uid': 'old-uid', 'requested_at': time.time()}))
            with patch.object(bh.psutil, 'Process', side_effect=process), \
                 patch.object(bh.os, 'kill') as kill:
                bh.hold_requested_parser(root, measurement, 1,
                    SimpleNamespace(pid=123))
            kill.assert_called_once_with(456, bh.signal.SIGSTOP)
            held = json.loads((measurement / 'held-parser.json').read_text())
            self.assertEqual(held['old_pod_uid'], 'old-uid')
            self.assertTrue(held['parser_stopped'])


if __name__ == '__main__':
    unittest.main()
