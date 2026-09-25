"""Temporary object-service trial restores the exact original Deployment."""

import json
import unittest
import time

from sentinel import object_limit_trial_bf as trial


class Kube:
    def __init__(self, uid=trial.DEPLOYMENT_UID):
        self.uid = uid
        self.memory = trial.OLD_LIMIT
        self.revision = 1
        self.patches = []
        self.lost_response_on = None
        self.transient_pods = 0

    def json(self, *args):
        if args == ('get', 'pods', '-l', 'app=pdf-objects'):
            pod = {'metadata': {'name': 'objects-' + str(self.revision),
                                'uid': 'pod-' + str(self.revision)},
                   'spec': {'nodeName': 'internal-a2a-vs6-local-worker2',
                            'containers': [{'resources': {'limits':
                                {'memory': self.memory}}}]},
                   'status': {'phase': 'Running', 'containerStatuses': [{
                       'ready': True, 'restartCount': 0,
                       'containerID': 'containerd://abc'}]}}
            if self.transient_pods:
                self.transient_pods -= 1
                return {'items': [pod, pod]}
            return {'items': [pod]}
        assert args == ('get', 'deployment', 'objects')
        return {'metadata': {'uid': self.uid,
                             'resourceVersion': str(self.revision)},
                'spec': {'replicas': 1,
                         'selector': {'matchLabels': {'app': 'pdf-objects'}},
                         'template': {'spec': {'containers': [{
                             'resources': {'limits': {'memory': self.memory}}
                         }]}}}}

    def run(self, args, **kwargs):
        changes = json.loads(args[-1])
        assert changes[0]['value'] == self.uid
        assert changes[1]['value'] == str(self.revision)
        assert changes[2]['value'] == self.memory
        self.memory = changes[3]['value']
        self.revision += 1
        self.patches.append(changes)
        if self.lost_response_on == self.revision:
            raise TimeoutError('patch applied; response lost')


class LimitTrialTest(unittest.TestCase):
    def test_one_exact_trial_then_512mi_restoration(self):
        kube = Kube()
        state = trial.capture(kube)
        trial.enter(kube, state, deadline=time.time() + 5)
        restored = trial.restore(kube, state, deadline=time.time() + 5)
        self.assertEqual([change[3]['value'] for change in kube.patches],
                         ['1Gi', '512Mi'])
        self.assertEqual(restored['restored_limit'], '512Mi')
        self.assertEqual(kube.memory, '512Mi')

    def test_applied_entry_with_lost_response_can_be_restored(self):
        kube = Kube()
        state = trial.capture(kube)
        kube.lost_response_on = 2
        with self.assertRaisesRegex(TimeoutError, 'response lost'):
            trial.enter(kube, state, deadline=time.time() + 5)
        kube.transient_pods = 1
        restored = trial.restore(kube, state, deadline=time.time() + 5)
        self.assertEqual(restored['pod']['pod_uid'], 'pod-3')
        self.assertEqual(kube.memory, '512Mi')

    def test_applied_rollback_with_lost_response_settles_on_retry(self):
        kube = Kube()
        state = trial.capture(kube)
        trial.enter(kube, state, deadline=time.time() + 5)
        kube.lost_response_on = 3
        with self.assertRaisesRegex(TimeoutError, 'response lost'):
            trial.restore(kube, state, deadline=time.time() + 5)
        kube.transient_pods = 1
        restored = trial.restore(kube, state, deadline=time.time() + 5)
        self.assertEqual(restored['pod']['pod_uid'], 'pod-3')
        self.assertEqual(kube.memory, '512Mi')

    def test_unowned_deployment_rejected_before_patch(self):
        kube = Kube(uid='wrong')
        with self.assertRaisesRegex(ValueError, 'Deployment identity changed'):
            trial.capture(kube)
        self.assertEqual(kube.patches, [])


if __name__ == '__main__':
    unittest.main()
