"""A split Q04 topology stays inactive and keeps both Pods on one evidence PVC."""

import copy
import unittest

import pod_topology_bg as bg


class SplitPodTopologyTest(unittest.TestCase):
    def test_exact_inactive_topology(self):
        value = bg.kubernetes_list()
        self.assertEqual(bg.validate(value)['status'], 'PASS_OFFLINE_ONLY')
        self.assertEqual([item['kind'] for item in value['items']],
                         ['ConfigMap', 'ConfigMap', 'PersistentVolumeClaim',
                          'Deployment', 'Deployment'])
        worker, coordinator = value['items'][3:]
        self.assertEqual(worker['spec']['replicas'], 0)
        self.assertEqual(coordinator['spec']['replicas'], 0)
        self.assertNotEqual(worker['spec']['selector'], coordinator['spec']['selector'])
        for deployment in (worker, coordinator):
            pod = deployment['spec']['template']['spec']
            self.assertFalse(pod['automountServiceAccountToken'])
            self.assertEqual(pod['nodeSelector']['kubernetes.io/hostname'], bg.NODE)
            self.assertEqual(next(volume for volume in pod['volumes']
                if volume['name'] == 'evidence')['persistentVolumeClaim']['claimName'],
                bg.EVIDENCE_PVC)
        changed = copy.deepcopy(value)
        changed['items'][4]['spec']['replicas'] = 1
        with self.assertRaises(ValueError):
            bg.validate(changed)
