"""Approved deployment transaction: retain only after complete qualification."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import object_policy


class Kube:
    def __init__(self):
        self.value = {
            'metadata': {'uid': 'object-deployment', 'resourceVersion': '1'},
            'spec': {
                'strategy': {'type': 'RollingUpdate', 'rollingUpdate': {
                    'maxSurge': '25%', 'maxUnavailable': '25%'}},
                'template': {'spec': {'containers': [{'name': 'minio', 'resources': {
                    'requests': {'cpu': '100m', 'memory': '128Mi'},
                    'limits': {'memory': '512Mi'}}}]}}}}
        self.patches = []

    def json(self, *args):
        return copy.deepcopy(self.value)

    def run(self, args, **kwargs):
        operations = json.loads(args[-1])
        self.patches.append(operations)
        for operation in operations:
            target = self.value
            parts = operation['path'].split('/')[1:]
            for key in parts[:-1]:
                target = target[int(key)] if isinstance(target, list) else target[key]
            key = parts[-1]
            if operation['op'] == 'test':
                assert target[key] == operation['value']
            else:
                target[key] = operation['value']


class ObjectPolicyTest(unittest.TestCase):
    def test_failure_restores_exact_resources_and_strategy(self):
        kube = Kube()
        before = copy.deepcopy(kube.value['spec'])
        snapshot = object_policy.capture(kube)
        object_policy.apply(kube, snapshot)
        self.assertEqual(kube.value['spec']['strategy'], {'type': 'Recreate'})
        with patch.object(object_policy, 'await_ready', return_value={'pod_uid': 'restored'}):
            result = object_policy.finish(kube, snapshot, qualified=False)
        self.assertEqual(kube.value['spec'], before)
        self.assertEqual(result['decision'], 'restored')

    def test_success_retains_candidate_without_second_patch(self):
        kube = Kube()
        snapshot = object_policy.capture(kube)
        object_policy.apply(kube, snapshot)
        with patch.object(object_policy, 'await_ready', return_value={'pod_uid': 'candidate'}):
            result = object_policy.finish(kube, snapshot, qualified=True)
        self.assertEqual(result['decision'], 'retained')
        self.assertEqual(len(kube.patches), 1)
        resources = kube.value['spec']['template']['spec']['containers'][0]['resources']
        self.assertEqual(resources['requests']['memory'], '768Mi')
        self.assertEqual(resources['limits']['memory'], '1Gi')

    def test_concurrent_deployment_change_is_not_overwritten(self):
        kube = Kube()
        snapshot = object_policy.capture(kube)
        object_policy.apply(kube, snapshot)
        kube.value['spec']['strategy'] = {'type': 'ExternalChange'}
        with self.assertRaisesRegex(ValueError, 'outside'):
            object_policy.finish(kube, snapshot, qualified=False)
        self.assertEqual(len(kube.patches), 1)


if __name__ == '__main__':
    unittest.main()
