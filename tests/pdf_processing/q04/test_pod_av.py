"""Local contracts for the AV worker-process drain window."""

import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from candidate import process_drain_window_av as matrix
from host_av import Host
import pod_topology_av as topology
import pod_workload_av as workload
from sentinel import run_process_drain_pod_cgroup_av as runner
from sentinel import run_process_drain_pod_cgroup_av_guarded as guarded

BUNDLE = Path('/private/tmp/q04-inputs-warm-continuation-v3-ah')


class ProcessDrainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (BUNDLE / 'inputs.json').exists():
            raise unittest.SkipTest('private v3 bundle unavailable')

    def test_scope_identity_and_exact_command(self):
        path = topology.base.Q04 / 'pod-topology-v47/RUNTIME-INTEGRATION-MANIFEST.json'
        manifest = json.loads(path.read_text())
        args = type('Args', (), {'integration_manifest': path,
            'authorization_scope_sha256': manifest['authorization_scope_sha256'],
            'name': workload.PHASE, 'expected_run_id': runner.RUN_IDENTITY,
            'expected_prefix': runner.PREFIX})()
        self.assertEqual(matrix.validate_scope(args), manifest)
        self.assertEqual(topology.source_manifest()['producer'],
                         json.loads((BUNDLE / 'inputs.json').read_text())['producer'])
        self.assertEqual(runner.authorization_scope()['modes'], ['drain'])
        self.assertEqual(runner.authorization_scope()['expected_worker_generations'], 2)
        self.assertFalse(runner.authorization_scope()['automatic_retry'])
        self.assertEqual(topology.kubernetes_list()['items'][3]['spec']['replicas'], 0)
        self.assertEqual(guarded.PROBE_NAME, 'q04-host-pressure-av-20260925')
        command = shlex.split(runner.exact_command())
        self.assertIn('run_process_drain_pod_cgroup_av_guarded.py', command[1])
        parsed = runner.base.parser().parse_args(command[2:])
        self.assertTrue(parsed.execute)
        self.assertEqual(parsed.authorization_scope_sha256,
                         runner.authorization_scope_sha256())
        self.assertEqual(runner.base.offline_check()['status'], 'PASS_OFFLINE_ONLY')

    def test_measurement_argv_parses_at_real_entrypoint(self):
        args = type('Args', (), {'python': 'python', 'bundle': Path('/bundle'),
            'state': Path('/state'), 'capacity': Path('/capacity'),
            'prefix': runner.PREFIX, 'workspace': Path('/workspace')})()
        argv = workload.build_measurement_argv(args, runner.RUN_IDENTITY, 'inner-sha')
        async def no_runtime(_args):
            return None
        with patch.object(matrix, 'run_window', no_runtime):
            self.assertEqual(matrix.main(argv[3:]), 0)

    def test_drain_keeps_pod_and_starts_second_worker(self):
        async def check():
            with tempfile.TemporaryDirectory() as raw:
                host = Host(Path(raw) / 'config.json', Path(raw), {'pod_namespace': 'pdf-t09a-validation'})
                pod = {'metadata': {'uid': 'owned-pod'}}
                host.pod = pod
                host.generation = 1
                host.process = object()
                async def transition(_label, operation):
                    return await operation()
                host.collector = type('Collector', (), {})()
                host.collector.started = True
                host.collector.process_transition = transition
                async def stop():
                    host.process = None
                async def prepare():
                    host.pod = pod
                async def launch():
                    host.generation += 1
                    host.process = object()
                host.stop = stop
                host.prepare_start = prepare
                host.launch_start = launch
                host.await_ready = AsyncMock()
                with patch.object(host, 'signal') as signal, patch('host_av.asyncio.sleep', new=AsyncMock()):
                    result = await host.drain(101)
                self.assertEqual(result, {'scope': 'owned_worker_process',
                    'pod_uid': 'owned-pod', 'old_generation': 1, 'new_generation': 2})
                signal.assert_called_once()
        asyncio.run(check())

    @unittest.skipUnless(importlib.util.find_spec('pypdfium2'), 'pinned image required')
    def test_exact_projected_workspace_imports(self):
        rendered = topology.kubernetes_list()
        maps = {item['metadata']['name']: item['data'] for item in rendered['items']
                if item['kind'] == 'ConfigMap'}
        deployment = next(item for item in rendered['items'] if item['kind'] == 'Deployment')
        volume = next(item for item in deployment['spec']['template']['spec']['volumes']
                      if item['name'] == 'workspace')
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for source in volume['projected']['sources']:
                projection = source['configMap']
                for item in projection['items']:
                    path = root / item['path']
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(maps[projection['name']][item['key']])
            env = os.environ.copy()
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            env['PYTHONPATH'] = os.pathsep.join((str(root / 'src'),
                str(root / 'tests/pdf_processing/q04'),
                str(root / 'tests/pdf_processing/q02'),
                str(root / 'tests/pdf_processing/q03')))
            result = subprocess.run([sys.executable, '-c',
                'import pod_preflight_av; from pathlib import Path; '
                'pod_preflight_av.verify_workload_imports_at('
                f'workspace=Path({str(root)!r}),'
                f'bundle=Path({str(BUNDLE)!r}),'
                f'prefix={runner.PREFIX!r})'],
                cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
