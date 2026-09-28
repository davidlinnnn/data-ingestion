import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ProjectionTest(unittest.TestCase):
    def test_real_render_contains_measured_worker_and_inactive_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'render'
            subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('topology.py')),
                            '--out', str(output)], check=True, capture_output=True, timeout=30)
            topology = json.loads((output/'inactive-topology.json').read_text())
            maps = {item['metadata']['name']: item['data'] for item in topology['items']
                    if item['kind'] == 'ConfigMap'}
            deployment = topology['items'][3]
            self.assertEqual(deployment['spec']['replicas'], 0)
            pod = deployment['spec']['template']['spec']
            paths = {}
            workspace = next(v for v in pod['volumes'] if v['name'] == 'workspace')
            for source in workspace['projected']['sources']:
                ref = source['configMap']
                for item in ref['items']:
                    paths[item['path']] = maps[ref['name']][item['key']]
            for name in ('worker.py', 't09b_host.py', 'worker_measurement.py',
                         'storage_measurement.py', 'storage_ledger.py'):
                self.assertEqual(paths[f'tests/pdf_processing/t09b/{name}'],
                                 Path(__file__).with_name(name).read_text())
            env = {item['name']: item.get('value') for item in pod['containers'][0]['env']}
            self.assertEqual(env['OBJECT_PREFIX'], 't09b/calibration-20260928-a1/')
