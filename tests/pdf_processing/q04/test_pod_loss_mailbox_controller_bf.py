"""Mailbox stop must win over a pending start/drain and clean the Activity Pod."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sentinel.pod_loss_mailbox_controller_bf import MailboxController


class MailboxControllerTest(unittest.TestCase):
    def test_stop_before_adoption_still_cleans_owned_activity_pod(self):
        with tempfile.TemporaryDirectory() as raw:
            controller = MailboxController(object(), {'pod_name': 'coordinator'},
                {'metadata': {'uid': 'deployment'}},
                {'pod_name': 'worker', 'pod_uid': 'old'}, Path(raw),
                deadline=10**11)
            seen = []
            def request(kind, generation):
                return {'run_id': 'q04-pod-loss-pod-cgroup-20260925-bf',
                        'kind': kind, 'generation': generation,
                        'requested_at': 1} if kind in ('stop', 'start') else None
            def reply(kind, generation, details):
                seen.append((kind, generation, details))
            controller.request = request
            controller.reply = reply
            with patch.object(controller, '_stop_current_worker',
                              side_effect=FileNotFoundError), \
                 patch('sentinel.pod_loss_mailbox_controller_bf.reviewed.cleanup_deployment_and_pod') as cleanup:
                self.assertEqual(controller.process_once(), 'stop')
            self.assertEqual(cleanup.call_count, 1)
            self.assertEqual(seen[0][0], 'stop')
            self.assertTrue(seen[0][2]['activity_pods_absent'])
            self.assertIsNone(controller.worker_pod)
