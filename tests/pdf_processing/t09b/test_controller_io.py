from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import controller_io


class ControllerIOTest(unittest.TestCase):
    def test_retained_object_is_read_only_and_trace_failure_closes(self):
        deployment = {'metadata': {'uid': 'deployment'}, 'status': {'availableReplicas': 1},
                      'spec': {'strategy': {'type': 'Recreate'}, 'template': {'spec': {'containers': [
                          {'resources': {'requests': {'cpu': '100m', 'memory': '768Mi'},
                                         'limits': {'memory': '1Gi'}}}]}}}}
        kube = Mock()
        kube.base = ['kubectl', '--context', 'test', '-n', 'test']
        kube.json.return_value = {'metadata': {'uid': 'pvc'}, 'status': {'phase': 'Bound'},
                                  'spec': {'volumeName': 'volume'}}
        runner = SimpleNamespace(object_trial=SimpleNamespace(TRIAL_BYTES=1073741824,
                    deployment=lambda kube: deployment), object_monitor_bh=SimpleNamespace(
                    object_identity=lambda kube, cap: {'pod_name': 'objects', 'pod_uid': 'pod'}))
        result = controller_io.retained_object(runner, kube)
        self.assertEqual(result['pvc_uid'], 'pvc')
        kube.run.assert_not_called()
        deployment['spec']['template']['spec']['containers'][0]['resources']['limits']['memory'] = '512Mi'
        with self.assertRaises(ValueError):
            controller_io.retained_object(runner, kube)
        with patch.object(controller_io, 'NativeTrace') as session, \
             patch.object(controller_io.time, 'sleep'), \
             patch.object(controller_io, 'marker', return_value='marker'):
            session.return_value.ready.side_effect = TimeoutError('not observed')
            with self.assertRaises(TimeoutError):
                controller_io.start_trace(kube, 'objects', 'output', 'prefix/')
            session.return_value.close.assert_called_once()
        trace = Mock()
        with patch.object(controller_io, 'marker', side_effect=TimeoutError('marker failed')):
            with self.assertRaises(TimeoutError):
                controller_io.finish_trace(trace, kube, 'prefix/')
        trace.close.assert_called_once()
