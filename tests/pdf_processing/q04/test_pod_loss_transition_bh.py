"""A Pod-loss transition must fence the old UID before any scale/delete."""

from pathlib import Path
import json
import tempfile
import time
import unittest
from unittest.mock import patch

from sentinel import pod_loss_transition_bh as transition


class FakeKube:
    def __init__(self):
        self.calls = []

    def json(self, *args):
        self.calls.append(('json', args))
        if args[1] == 'pod':
            return {'metadata': {'uid': 'old'}}
        return {'metadata': {'uid': 'deployment', 'resourceVersion': '2'},
                'spec': {'replicas': 0}}

    def run(self, args, **kwargs):
        self.calls.append(('run', args))


class TransitionTest(unittest.TestCase):
    def test_parser_hold_uses_coordinator_mailbox_only(self):
        class Kube:
            def __init__(self):
                self.calls = []
                self.request = None
            def run(self, args, **kwargs):
                self.calls.append(('run', args))
                self.request = json.loads(kwargs['input'])
            def exec_python(self, pod, program, **kwargs):
                self.calls.append(('exec_python', pod))
                return json.dumps({**self.request, 'parser_pid': 99,
                    'parser_stopped': True, 'held_at': time.time()})
        kube = Kube()
        proof = transition.hold_owned_parser(kube, 'coordinator',
            {'pod_uid': 'old-uid', 'pod_name': 'measured-worker'}, 99,
            deadline=time.time() + 10)
        self.assertTrue(proof['parser_stopped'])
        self.assertEqual(kube.calls[0][1][2], 'coordinator')
        self.assertEqual(kube.calls[1], ('exec_python', 'coordinator'))

    def test_wrong_old_uid_rejected_before_kubernetes_operation(self):
        kube = FakeKube()
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                transition.drain_worker(kube, {'metadata': {'uid': 'deployment'}},
                    {'pod_uid': 'old', 'pod_name': 'old-pod', 'container_id': 'cri'},
                    'coordinator', {'run_id': 'q04-pod-loss-pod-cgroup-20260926-bh',
                        'kind': 'drain', 'generation': 2, 'old_pod_uid': 'wrong',
                        'child_pid': 99, 'requested_at': 1},
                    Path(raw) / 'new', deadline=100)
        self.assertEqual(kube.calls, [])

    def test_exact_old_uid_scales_zero_then_replacement_one(self):
        kube = FakeKube()
        old = {'pod_uid': 'old', 'pod_name': 'old-pod', 'container_id': 'cri'}
        request = {'run_id': 'q04-pod-loss-pod-cgroup-20260926-bh',
                   'kind': 'drain', 'generation': 2, 'old_pod_uid': 'old',
                   'child_pid': 99, 'requested_at': 1}
        with tempfile.TemporaryDirectory() as raw, \
             patch.object(transition.reviewed, 'validate_pod', return_value=old), \
             patch.object(transition, 'wait_old_sample', return_value={'time': 2}), \
             patch.object(transition, 'hold_owned_parser',
                return_value={'parser_pid': 99, 'parser_stopped': True}) as hold, \
             patch.object(transition.reviewed, 'cleanup_deployment_and_pod',
                return_value={'old_runtime_absent': True, 'emptydirs_absent': True}) as clean, \
             patch.object(transition.reviewed, 'await_worker_pod',
                return_value=({'pod_uid': 'new'}, {})):
            new, proof = transition.drain_worker(kube,
                {'metadata': {'uid': 'deployment'}}, old, 'coordinator', request,
                Path(raw) / 'new', deadline=10**11)
        self.assertEqual(new['pod_uid'], 'new')
        hold.assert_called_once()
        self.assertEqual(proof['old_pod_uid'], 'old')
        self.assertEqual(clean.call_args.kwargs['deployment_name'],
                         transition.topology.DEPLOYMENT)
        self.assertEqual(sum(kind == 'run' for kind, _ in kube.calls), 1)
        self.assertEqual(kube.calls[-1][1][:3],
                         ['patch', 'deployment', transition.topology.DEPLOYMENT])

    def test_guard_abort_after_parser_hold_prevents_pod_deletion(self):
        kube = FakeKube()
        old = {'pod_uid': 'old', 'pod_name': 'old-pod', 'container_id': 'cri'}
        request = {'run_id': 'q04-pod-loss-pod-cgroup-20260926-bh',
                   'kind': 'drain', 'generation': 2, 'old_pod_uid': 'old',
                   'child_pid': 99, 'requested_at': 1}
        checks = iter((None, RuntimeError('PSI guard')))
        def guard():
            result = next(checks)
            if result:
                raise result
        with tempfile.TemporaryDirectory() as raw, \
             patch.object(transition.reviewed, 'validate_pod', return_value=old), \
             patch.object(transition, 'hold_owned_parser',
                return_value={'parser_pid': 99, 'parser_stopped': True}), \
             patch.object(transition.reviewed, 'cleanup_deployment_and_pod') as clean:
            with self.assertRaisesRegex(RuntimeError, 'PSI guard'):
                transition.drain_worker(kube, {'metadata': {'uid': 'deployment'}},
                    old, 'coordinator', request, Path(raw) / 'new',
                    deadline=10**11, check_abort=guard)
        clean.assert_not_called()
