"""BF launch is pinned to the reviewed source, identity and inactive topology."""

import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
import unittest

from sentinel import run_pod_loss_bf as bf


class BFOfflineTest(unittest.TestCase):
    def test_rejected_node_guard_sample_is_saved(self):
        class Channel:
            def run(self, *_args, **_kwargs):
                return json.dumps({'time': 1, 'psi_full_avg10': 1})

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(bf, 'OUT', Path(tmp)), \
             patch.object(bf.reviewed, 'PersistentPython', return_value=Channel()), \
             patch.object(bf.reviewed, 'verify_runtime_sample', side_effect=ValueError('PSI guard')):
            monitor = bf.RuntimeMonitor(type('Kube', (), {'base': []})(),
                {'pod_name': 'coordinator'}, type('Controller', (), {})(),
                {'expected_vm_oom_kill': 0})
            monitor._run()
            self.assertIsInstance(monitor.error, ValueError)
            self.assertEqual(json.loads((Path(tmp) / 'vm-controller.jsonl').read_text()),
                             {'time': 1, 'psi_full_avg10': 1})

    def test_coordinator_cleanup_attempted_after_worker_cleanup_failure(self):
        class Kube:
            def json(self, *args):
                if args[:3] == ('get', 'deployment', bf.topology.DEPLOYMENT):
                    raise RuntimeError('worker cleanup failed')
                if args[:3] == ('get', 'deployment', bf.topology.COORDINATOR_DEPLOYMENT):
                    return {'metadata': {'uid': 'coordinator-uid'},
                            'spec': {'replicas': 1}}
                if args[:2] == ('get', 'pods'):
                    return {'items': []}
                raise AssertionError(args)

        owned = [{'kind': 'Deployment', 'name': bf.topology.DEPLOYMENT,
                  'uid': 'worker-uid'},
                 {'kind': 'Deployment', 'name': bf.topology.COORDINATOR_DEPLOYMENT,
                  'uid': 'coordinator-uid'}]
        errors = {}
        with patch.object(bf, 'scale') as scale:
            result = bf.cleanup_owned_deployments(Kube(), owned,
                deadline=100, errors=errors)
        scale.assert_called_once()
        self.assertIn(bf.topology.COORDINATOR_DEPLOYMENT, result)
        self.assertIn('run_owned_pods:' + bf.topology.DEPLOYMENT, errors)

    def test_sampler_close_failure_is_terminal(self):
        class Channel:
            def run(self, *_args, **_kwargs):
                monitor.stopping.set()
                return json.dumps({'time': time.time()})

            def close(self):
                raise RuntimeError('sampler transport close failed')

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(bf, 'OUT', Path(tmp)), \
             patch.object(bf.reviewed, 'PersistentPython', return_value=Channel()), \
             patch.object(bf.reviewed, 'verify_runtime_sample'):
            controller = type('Controller', (), {
                'transition_started': time.time(), 'transition_kind': 'start'})()
            monitor = bf.RuntimeMonitor(type('Kube', (), {'base': []})(),
                {'pod_name': 'coordinator'}, controller,
                {'expected_vm_oom_kill': 0})
            monitor._run()
            self.assertRegex(str(monitor.error), 'transport close failed')
            self.assertEqual(len(monitor.rows), 1)

    def test_exact_launch_contract(self):
        self.assertEqual(bf.offline_check()['status'], 'PASS_OFFLINE_ONLY')
        command = bf.workload_argv()
        self.assertIn('--run-id', command)
        self.assertEqual(command[command.index('--run-id') + 1], bf.RUN_ID)
        self.assertEqual(command[command.index('--prefix') + 1], bf.PREFIX)
        self.assertEqual(command[command.index('--state') + 1],
                         bf.EVIDENCE + '/state')
        preflight = bf.preflight_argv({})
        self.assertEqual(preflight[1],
            '/workspace/tests/pdf_processing/q04/pod_preflight_bf.py')
        self.assertEqual(preflight[preflight.index('--authorization-scope-sha256') + 1],
                         bf.authorization_scope_sha256())

    def test_source_drift_rejected_before_cluster_access(self):
        with patch.object(bf.topology, 'source_manifest', return_value={'drift': True}), \
             patch.object(bf.reviewed, 'Kubectl') as kubectl:
            with self.assertRaisesRegex(ValueError, 'source projection changed'):
                bf.execute(type('Args', (), {'authorization_scope_sha256':
                    bf.authorization_scope_sha256(), 'owner': 'test',
                    'approval_reference': 'test'})())
            kubectl.assert_not_called()

    def test_unreviewed_runtime_cannot_create_cluster_objects(self):
        with patch.object(bf.reviewed, 'Kubectl') as kubectl:
            with self.assertRaisesRegex(RuntimeError, 'awaits complete'):
                bf.execute(type('Args', (), {'authorization_scope_sha256':
                    bf.authorization_scope_sha256(), 'owner': 'test',
                    'approval_reference': 'test'})())
            kubectl.assert_not_called()
