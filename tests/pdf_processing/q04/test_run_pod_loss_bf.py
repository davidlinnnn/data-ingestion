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

    def test_deleted_pod_psi_sample_rejects_qualification(self):
        row = {'attribution_complete': True,
               'process_coverage': {'status': 'complete'},
               'memory_current': 1024,
               'memory_events': {'oom': 0, 'oom_kill': 0, 'oom_group_kill': 0},
               'memory_pressure_raw': 'full avg10=0.00 avg60=0.00 total=0\n'}
        bf.validate_old_resource_rows([row])
        with self.assertRaisesRegex(ValueError, 'all-sample resource gate'):
            bf.validate_old_resource_rows([
                row, {**row, 'memory_pressure_raw':
                      'full avg10=0.01 avg60=0.00 total=1\n'}])

    def test_object_readback_program_is_valid_and_scoped(self):
        test = self
        class Kube:
            def exec_python(self, pod, program, **kwargs):
                compile(program, '<object-readback>', 'exec')
                test.assertEqual(pod, 'coordinator')
                test.assertIn(bf.PREFIX, program)
                return json.dumps({'bucket': 't09a', 'prefix': bf.PREFIX,
                    'objects': [{'key': bf.PREFIX + 'registered/one',
                        'bytes': 3, 'sha256': 'a' * 64, 'etag': 'etag'}]})
        with tempfile.TemporaryDirectory() as tmp, patch.object(bf, 'OUT', Path(tmp)):
            self.assertEqual(bf.readback_objects(Kube(),
                {'pod_name': 'coordinator'})['objects'], 1)
            self.assertTrue((Path(tmp) / 'object-readback.json').exists())

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
