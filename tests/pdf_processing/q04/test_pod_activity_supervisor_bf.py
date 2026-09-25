"""The measured Activity Pod publishes control proof without new execs."""

import hashlib
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pod_activity_supervisor_bf as bf


class ActivityControlTest(unittest.TestCase):
    def test_worker_proof_and_parser_hold_are_published_in_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'evidence/state/pod-loss-pod-cgroup-bf'
            worker_root = root / 'worker-1'
            measurement = root.parent / 'pod-loss-pod-cgroup-bf-measurement/worker-1'
            worker_root.mkdir(parents=True)
            measurement.mkdir(parents=True)
            config = b'{"run_id":"bf"}'
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
                status=lambda: bf.psutil.STATUS_STOPPED)
            def process(pid):
                return {123: parent, 456: child}[pid]
            with patch.object(bf.psutil, 'Process', side_effect=process):
                self.assertTrue(bf.publish_worker_proof(root, measurement, 1,
                    SimpleNamespace(pid=123)))
            proof = json.loads((measurement / 'worker-proof.json').read_text())
            self.assertEqual(proof['first_sample_sha256'], hashlib.sha256(first).hexdigest())
            self.assertEqual(proof['ready_sha256'], hashlib.sha256(ready_raw).hexdigest())
            (measurement / 'hold-request.json').write_text(json.dumps({
                'run_id': 'q04-pod-loss-pod-cgroup-20260925-bf',
                'generation': 1, 'child_pid': 456,
                'old_pod_uid': 'old-uid', 'requested_at': time.time()}))
            with patch.object(bf.psutil, 'Process', side_effect=process), \
                 patch.object(bf.os, 'kill') as kill:
                bf.hold_requested_parser(root, measurement, 1,
                    SimpleNamespace(pid=123))
            kill.assert_called_once_with(456, bf.signal.SIGSTOP)
            held = json.loads((measurement / 'held-parser.json').read_text())
            self.assertEqual(held['old_pod_uid'], 'old-uid')
            self.assertTrue(held['parser_stopped'])


if __name__ == '__main__':
    unittest.main()
