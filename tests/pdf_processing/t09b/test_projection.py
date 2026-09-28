import json
import os
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
            for name in ('worker.py', 't09b_host.py', 'baseline_window.py', 'worker_measurement.py',
                         'storage_measurement.py', 'storage_ledger.py', 'publication_buffers.py',
                         'runtime_policy.py',
                         'pod_workload.py', 'pod_preflight.py', 'pod_remote_evidence.py', 'RUNTIME-INTEGRATION-MANIFEST.json'):
                self.assertEqual(paths[f'tests/pdf_processing/t09b/{name}'],
                                 Path(__file__).with_name(name).read_text())
            env = {item['name']: item.get('value') for item in pod['containers'][0]['env']}
            self.assertEqual(env['OBJECT_PREFIX'], 't09b/calibration-20260928-a4/')
            projected = Path(directory) / 'workspace'
            for path, contents in paths.items():
                target = projected / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(contents)
            child_env = dict(os.environ, PYTHONSAFEPATH='1', PYTHONDONTWRITEBYTECODE='1',
                             PYTHONPATH=os.pathsep.join(str(projected / path) for path in (
                                 'src', 'tests/pdf_processing/q04', 'tests/pdf_processing/q02',
                                 'tests/pdf_processing/q03')))
            for name in ('worker.py', 'baseline_window.py', 'pod_workload.py', 'pod_preflight.py'):
                result = subprocess.run([sys.executable, '-B', str(projected / 'tests/pdf_processing/t09b' / name),
                                         '--help'], env=child_env, cwd='/', capture_output=True,
                                        text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
            script = (
                'import sys; from pathlib import Path; '
                f'sys.path.insert(0, {str(projected / "tests/pdf_processing/t09b")!r}); '
                'import pod_preflight, baseline_window, pod_workload, pod_remote_evidence; '
                f'assert Path(pod_workload.__file__).resolve() == Path({str(projected / "tests/pdf_processing/t09b/pod_workload.py")!r}).resolve(); '
                f'assert Path(pod_remote_evidence.__file__).resolve() == Path({str(projected / "tests/pdf_processing/t09b/pod_remote_evidence.py")!r}).resolve()'
            )
            subprocess.run([sys.executable, '-B', '-c', script], env=child_env,
                           cwd='/', check=True, capture_output=True, text=True, timeout=20)
