"""BH launch is pinned to the reviewed source, identity and inactive topology."""

import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
import unittest

from sentinel import run_pod_loss_bh as bh


class BHOfflineTest(unittest.TestCase):
    def test_rejected_node_guard_sample_is_saved(self):
        class Channel:
            def run(self, *_args, **_kwargs):
                return json.dumps({'time': 1, 'psi_full_avg10': 1})

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(bh, 'OUT', Path(tmp)), \
             patch.object(bh.reviewed, 'PersistentPython', return_value=Channel()), \
             patch.object(bh.reviewed, 'verify_runtime_sample', side_effect=ValueError('PSI guard')):
            monitor = bh.RuntimeMonitor(type('Kube', (), {'base': []})(),
                {'pod_name': 'coordinator'}, type('Controller', (), {})(),
                {'expected_vm_oom_kill': 0})
            monitor._run()
            self.assertIsInstance(monitor.error, ValueError)
            self.assertEqual(json.loads((Path(tmp) / 'vm-controller.jsonl').read_text()),
                             {'time': 1, 'psi_full_avg10': 1})

    def test_coordinator_cleanup_attempted_after_worker_cleanup_failure(self):
        class Kube:
            def json(self, *args):
                if args[:3] == ('get', 'deployment', bh.topology.DEPLOYMENT):
                    raise RuntimeError('worker cleanup failed')
                if args[:3] == ('get', 'deployment', bh.topology.COORDINATOR_DEPLOYMENT):
                    return {'metadata': {'uid': 'coordinator-uid'},
                            'spec': {'replicas': 1}}
                if args[:2] == ('get', 'pods'):
                    return {'items': []}
                raise AssertionError(args)

        owned = [{'kind': 'Deployment', 'name': bh.topology.DEPLOYMENT,
                  'uid': 'worker-uid'},
                 {'kind': 'Deployment', 'name': bh.topology.COORDINATOR_DEPLOYMENT,
                  'uid': 'coordinator-uid'}]
        errors = {}
        with patch.object(bh, 'scale') as scale:
            result = bh.cleanup_owned_deployments(Kube(), owned,
                deadline=100, errors=errors)
        scale.assert_called_once()
        self.assertIn(bh.topology.COORDINATOR_DEPLOYMENT, result)
        self.assertIn('run_owned_pods:' + bh.topology.DEPLOYMENT, errors)

    def test_sampler_close_failure_is_terminal(self):
        class Channel:
            def run(self, *_args, **_kwargs):
                monitor.stopping.set()
                return json.dumps({'time': time.time()})

            def close(self):
                raise RuntimeError('sampler transport close failed')

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(bh, 'OUT', Path(tmp)), \
             patch.object(bh.reviewed, 'PersistentPython', return_value=Channel()), \
             patch.object(bh.reviewed, 'verify_runtime_sample'):
            controller = type('Controller', (), {
                'transition_started': time.time(), 'transition_kind': 'start'})()
            monitor = bh.RuntimeMonitor(type('Kube', (), {'base': []})(),
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
        bh.validate_old_resource_rows([row])
        with self.assertRaisesRegex(ValueError, 'all-sample resource gate'):
            bh.validate_old_resource_rows([
                row, {**row, 'memory_pressure_raw':
                      'full avg10=0.01 avg60=0.00 total=1\n'}])

    def test_object_readback_program_is_valid_and_scoped(self):
        test = self
        class Kube:
            def exec_python(self, pod, program, **kwargs):
                compile(program, '<object-readback>', 'exec')
                test.assertEqual(pod, 'coordinator')
                test.assertIn(bh.PREFIX, program)
                return json.dumps({'bucket': 't09a', 'prefix': bh.PREFIX,
                    'objects': [{'key': bh.PREFIX + 'registered/one',
                        'bytes': 3, 'sha256': 'a' * 64, 'etag': 'etag'}]})
        with tempfile.TemporaryDirectory() as tmp, patch.object(bh, 'OUT', Path(tmp)):
            self.assertEqual(bh.readback_objects(Kube(),
                {'pod_name': 'coordinator'})['objects'], 1)
            self.assertTrue((Path(tmp) / 'object-readback.json').exists())

    def test_exact_launch_contract(self):
        self.assertEqual(bh.offline_check()['status'], 'PASS_OFFLINE_ONLY')
        command = bh.workload_argv()
        self.assertIn('--run-id', command)
        self.assertEqual(command[command.index('--run-id') + 1], bh.RUN_ID)
        self.assertEqual(command[command.index('--prefix') + 1], bh.PREFIX)
        self.assertEqual(command[command.index('--state') + 1],
                         bh.EVIDENCE + '/state')
        preflight = bh.preflight_argv({})
        self.assertEqual(preflight[1],
            '/workspace/tests/pdf_processing/q04/pod_preflight_bh.py')
        self.assertEqual(preflight[preflight.index('--authorization-scope-sha256') + 1],
                         bh.authorization_scope_sha256())

    def test_source_drift_rejected_before_cluster_access(self):
        with patch.object(bh.topology, 'source_manifest', return_value={'drift': True}), \
             patch.object(bh.reviewed, 'Kubectl') as kubectl:
            with self.assertRaisesRegex(ValueError, 'source projection changed'):
                bh.execute(type('Args', (), {'authorization_scope_sha256':
                    bh.authorization_scope_sha256(), 'owner': 'test',
                    'approval_reference': 'test'})())
            kubectl.assert_not_called()

    def test_wrong_scope_cannot_create_cluster_objects(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'manifest.json'
            manifest.write_text('{"runtime_authorized": true}')
            with patch.object(bh, 'RUNNER_MANIFEST', manifest), \
                 patch.object(bh, 'offline_check'), \
                 patch.object(bh.reviewed, 'Kubectl') as kubectl:
                with self.assertRaisesRegex(ValueError, 'scope digest changed'):
                    bh.execute(type('Args', (), {'authorization_scope_sha256':
                        'wrong', 'owner': 'test',
                        'approval_reference': 'test'})())
                kubectl.assert_not_called()

    def test_completed_bh_identity_cannot_run_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'manifest.json'
            manifest.write_text('{"runtime_authorized": false}')
            with patch.object(bh, 'RUNNER_MANIFEST', manifest), \
                 patch.object(bh, 'offline_check'), \
                 patch.object(bh.reviewed, 'Kubectl') as kubectl:
                with self.assertRaisesRegex(RuntimeError, 'awaits complete'):
                    bh.execute(type('Args', (), {'authorization_scope_sha256':
                        bh.authorization_scope_sha256(), 'owner': 'test',
                        'approval_reference': 'test'})())
                kubectl.assert_not_called()

    def test_failed_setup_restores_authorized_object_trial(self):
        names = ('PHASE', 'RUN_IDENTITY', 'PREFIX', 'OUT', 'EVIDENCE',
                 'EVIDENCE_DIRECTORY_NAME', 'NAMESPACE', 'NODE', 'DEPLOYMENT',
                 'RUN_LABEL', 'pod_topology', 'authorization_scope_sha256')
        previous = {name: getattr(bh.reviewed, name) for name in names}
        self.addCleanup(lambda: [setattr(bh.reviewed, name, value)
                                 for name, value in previous.items()])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'bh'
            manifest = Path(tmp) / 'manifest.json'
            manifest.write_text('{"runtime_authorized": true}')
            state = {'old_pod': {'pod_uid': 'old'}, 'trial_pod': None}
            args = type('Args', (), {'authorization_scope_sha256':
                bh.authorization_scope_sha256(), 'owner': 'test',
                'approval_reference': 'test'})()
            with patch.object(bh, 'OUT', out), \
                 patch.object(bh, 'RUNNER_MANIFEST', manifest), \
                 patch.object(bh, 'offline_check'), \
                 patch.object(bh.reviewed, 'Kubectl', return_value=object()), \
                 patch.object(bh.reviewed, 'build_capacity', return_value={
                     'ends_at': time.time() + 1500}), \
                 patch.object(bh.reviewed, 'verify_held_deployments'), \
                 patch.object(bh.reviewed, 't09a_health'), \
                 patch.object(bh.object_trial, 'capture', return_value=state), \
                 patch.object(bh.object_trial, 'enter', side_effect=TimeoutError(
                     'trial rollout timeout')) as enter, \
                 patch.object(bh.object_trial, 'restore', return_value={
                     'restored_limit': '512Mi'}) as restore, \
                 patch.object(bh, 'setup') as setup:
                with self.assertRaisesRegex(TimeoutError, 'trial rollout timeout'):
                    bh.execute(args)
            enter.assert_called_once()
            setup.assert_not_called()
            restore.assert_called_once()
            self.assertEqual(json.loads((out / 'outer-cleanup.json').read_text())
                             ['object_trial_restoration']['restored_limit'], '512Mi')

    def test_failure_export_follows_worker_cleanup(self):
        names = ('PHASE', 'RUN_IDENTITY', 'PREFIX', 'OUT', 'EVIDENCE',
                 'EVIDENCE_DIRECTORY_NAME', 'NAMESPACE', 'NODE', 'DEPLOYMENT',
                 'RUN_LABEL', 'pod_topology', 'authorization_scope_sha256')
        previous = {name: getattr(bh.reviewed, name) for name in names}
        self.addCleanup(lambda: [setattr(bh.reviewed, name, value)
                                 for name, value in previous.items()])
        events = []
        def cleanup(_kube, _owned, *, names=None, **_kwargs):
            events.append(names)
            return {}
        def export(*_args, **_kwargs):
            events.append('export')
        class BrokenObserver:
            process = None
            def start(self, **_kwargs):
                raise ValueError('synthetic observer failure')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'bh'
            manifest = Path(tmp) / 'manifest.json'
            manifest.write_text('{"runtime_authorized": true}')
            args = type('Args', (), {'authorization_scope_sha256':
                bh.authorization_scope_sha256(), 'owner': 'test',
                'approval_reference': 'test'})()
            with patch.object(bh, 'OUT', out), \
                 patch.object(bh, 'RUNNER_MANIFEST', manifest), \
                 patch.object(bh, 'offline_check'), \
                 patch.object(bh.reviewed, 'Kubectl', return_value=object()), \
                 patch.object(bh.reviewed, 'build_capacity', return_value={
                     'ends_at': time.time() + 1500}), \
                 patch.object(bh.reviewed, 'verify_held_deployments'), \
                 patch.object(bh.reviewed, 't09a_health'), \
                 patch.object(bh.object_trial, 'capture', return_value={
                     'old_pod': {'pod_uid': 'old'}, 'trial_pod': None}), \
                 patch.object(bh.object_trial, 'enter'), \
                 patch.object(bh.object_trial, 'restore', return_value={
                     'restored_limit': '512Mi'}), \
                 patch.object(bh, 'setup', return_value=({}, {}, {},
                     {'pod_name': 'coordinator'}, {})), \
                 patch.object(bh, 'MailboxController'), \
                 patch.object(bh, 'RuntimeMonitor') as monitor, \
                 patch.object(bh, 'ObjectMonitor', return_value=BrokenObserver()), \
                 patch.object(bh, 'cleanup_owned_deployments', side_effect=cleanup), \
                 patch.object(bh, 'export_evidence', side_effect=export):
                monitor.return_value.stop.return_value = None
                with self.assertRaisesRegex(ValueError, 'synthetic observer failure'):
                    bh.execute(args)
        self.assertEqual(events, [(bh.topology.DEPLOYMENT,), 'export',
                                  (bh.topology.COORDINATOR_DEPLOYMENT,)])
