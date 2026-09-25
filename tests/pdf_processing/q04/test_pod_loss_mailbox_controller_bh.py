"""Mailbox stop must win over a pending start/drain and clean the Activity Pod."""

from pathlib import Path
import json
import tempfile
import time
import unittest
from unittest.mock import patch

from sentinel.pod_loss_mailbox_controller_bh import MailboxController


class MailboxControllerTest(unittest.TestCase):
    def test_finished_worker_with_failed_gate_reports_gate_failure(self):
        class Kube:
            def exec_python(self, _pod, program, **_kwargs):
                compile(program, '<remote-check>', 'exec')
                return 'gate_failed'
        with tempfile.TemporaryDirectory() as raw:
            controller = MailboxController(Kube(), {'pod_name': 'coordinator'},
                {}, {}, Path(raw), deadline=time.time() + .3)
            with self.assertRaisesRegex(ValueError, 'resource gate failed'):
                controller._stop_current_worker(2)

    def test_replacement_emptydir_inputs_staged_before_worker(self):
        class Kube:
            base = ['kubectl']
            def __init__(self):
                self.writes = []
            def run(self, args, **kwargs):
                self.writes.append((args, kwargs['input']))
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            bundle = root / 'bundle'
            bundle.mkdir()
            capacity = root / 'capacity.json'
            capacity.write_text(json.dumps({'ends_at': 100}))
            kube = Kube()
            controller = MailboxController(kube, {'pod_name': 'coordinator'},
                {'metadata': {'uid': 'deployment'}}, {'pod_name': 'old'}, root,
                deadline=10**11, bundle=bundle, capacity_path=capacity)
            pod = {'pod_name': 'new', 'pod_uid': 'new-uid'}
            with patch.object(controller, '_verify_worker_pod') as verify, \
                 patch('sentinel.pod_loss_mailbox_controller_bh.subprocess.run') as cp:
                controller.prepare_replacement(pod)
            cp.assert_called_once()
            self.assertEqual(len(kube.writes), 2)
            self.assertEqual(json.loads(kube.writes[0][1]), {'ends_at': 100})
            self.assertEqual(json.loads(kube.writes[1][1]), pod)
            self.assertEqual(verify.call_count, 2)

    def test_stop_before_adoption_still_cleans_owned_activity_pod(self):
        with tempfile.TemporaryDirectory() as raw:
            controller = MailboxController(object(), {'pod_name': 'coordinator'},
                {'metadata': {'uid': 'deployment'}},
                {'pod_name': 'worker', 'pod_uid': 'old'}, Path(raw),
                deadline=10**11)
            seen = []
            def request(kind, generation):
                return {'run_id': 'q04-pod-loss-pod-cgroup-20260926-bh',
                        'kind': kind, 'generation': generation,
                        'requested_at': 1} if kind in ('stop', 'start') else None
            def reply(kind, generation, details):
                seen.append((kind, generation, details))
            controller.request = request
            controller.reply = reply
            with patch.object(controller, '_stop_current_worker',
                              side_effect=FileNotFoundError), \
                 patch('sentinel.pod_loss_mailbox_controller_bh.reviewed.cleanup_deployment_and_pod') as cleanup:
                self.assertEqual(controller.process_once(), 'stop')
            self.assertEqual(cleanup.call_count, 1)
            self.assertEqual(seen[0][0], 'stop')
            self.assertTrue(seen[0][2]['activity_pods_absent'])
            self.assertIsNone(controller.worker_pod)
