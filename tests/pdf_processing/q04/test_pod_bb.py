"""Local contracts for the BB worker-process drain window."""

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

from candidate import process_drain_window_bb as matrix
import consumer
from host_an import Host
import pod_topology_bb as topology
import pod_workload_bb as workload
from sentinel import run_process_drain_pod_cgroup_bb as runner
from sentinel import run_process_drain_pod_cgroup_bb_guarded as guarded
from sentinel import node_pressure_attribution_bb as pressure

BUNDLE = Path('/private/tmp/q04-inputs-warm-continuation-v3-ah')


class ProcessDrainTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (BUNDLE / 'inputs.json').exists():
            raise unittest.SkipTest('private v3 bundle unavailable')

    def test_scope_identity_and_exact_command(self):
        path = topology.base.Q04 / 'pod-topology-v53/RUNTIME-INTEGRATION-MANIFEST.json'
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
        self.assertEqual(guarded.PROBE_NAME, 'q04-host-pressure-bb-20260925')
        self.assertEqual(guarded.OBJECT_POD, 'objects-6756bf97c6-pkqb7')
        self.assertEqual(guarded.owned_probe_command()[-2:],
                         ['--target-pod-uid', guarded.OBJECT_POD_UID])
        command = shlex.split(runner.exact_command())
        self.assertIn('run_process_drain_pod_cgroup_bb_guarded.py', command[1])
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

    def test_preflight_provenance_exists_in_projected_workspace(self):
        argv = runner.preflight_argv()
        source = Path(argv[argv.index('--provenance') + 1]).relative_to('/workspace')
        self.assertTrue((topology.base.ROOT / source).is_file())
        deployment = next(item for item in topology.kubernetes_list()['items']
                          if item['kind'] == 'Deployment')
        volume = next(item for item in deployment['spec']['template']['spec']['volumes']
                      if item['name'] == 'workspace')
        projected = {item['path'] for entry in volume['projected']['sources']
                     for item in entry['configMap']['items']}
        self.assertIn(source.as_posix(), projected)

    def test_existing_local_process_drain_starts_second_worker(self):
        async def check():
            with tempfile.TemporaryDirectory() as raw:
                host = Host(Path(raw) / 'config.json', Path(raw), {'pod_namespace': None})
                host.generation = 1
                host.process = object()
                async def stop():
                    host.process = None
                async def start():
                    host.generation += 1
                    host.process = object()
                host.stop = stop
                host.start = start
                with patch.object(host, 'signal') as signal, patch('host.asyncio.sleep', new=AsyncMock()):
                    result = await host.drain(101)
                self.assertEqual(result, {'scope': 'owned_worker_process',
                    'old_generation': 1, 'new_generation': 2})
                signal.assert_called_once()
        asyncio.run(check())

    def test_aw_failure_document_uses_reviewed_current_v3_oracle(self):
        raw = Path('/private/tmp/q04-process-drain-pod-cgroup-20260925-aw/failure-evidence/state/process-drain-pod-cgroup-aw/drain-native/document.json')
        if not raw.is_file():
            self.skipTest('retained AW failure export unavailable')
        document = json.loads(raw.read_text())
        reference = json.loads((BUNDLE / 'references/native.json').read_text())
        original = consumer.check_reference

        class Run:
            async def trial(self, sid, mode, label):
                self.assert_args = (sid, mode, label)
                with tempfile.TemporaryDirectory() as out:
                    return consumer.check_reference(document, reference, Path(out))

        run = Run()
        self.assertEqual(asyncio.run(matrix.reviewed_drain_trial(run, BUNDLE)),
                         '9f1b0ef9ed561df0c4a5748d5c49554e8f5ad3bb38764d94a51d3433f4d94972')
        self.assertEqual(run.assert_args, ('native', 'drain', 'drain-native'))
        self.assertIs(consumer.check_reference, original)

    def test_reviewed_oracle_is_restored_after_trial_failure(self):
        original = consumer.check_reference

        class Run:
            async def trial(self, *args):
                raise RuntimeError('injected trial failure')

        with self.assertRaisesRegex(RuntimeError, 'injected trial failure'):
            asyncio.run(matrix.reviewed_drain_trial(Run(), BUNDLE))
        self.assertIs(consumer.check_reference, original)

    def test_exact_object_cgroup_sample(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            name = 'docker/kubelet.slice/kubepods-pod' + guarded.OBJECT_POD_UID.replace('-', '_') + '/cri-containerd-minio.scope'
            group = root / name
            group.mkdir(parents=True)
            for filename, value in {
                'memory.max': '805306368\n', 'memory.current': '123\n',
                'memory.events': 'low 0\nhigh 0\nmax 2\noom 0\noom_kill 0\n',
                'memory.stat': 'anon 20\nfile 30\nkernel 40\n',
            }.items():
                (group / filename).write_text(value)
            with patch.object(pressure, 'CGROUPS', root):
                sample = pressure.target_sample({name: 7}, guarded.OBJECT_POD_UID)
            self.assertEqual((sample['memory_current'], sample['max_events'], sample['full_total_us']),
                             (123, 2, 7))

    def test_object_container_restart_invalidates_sample_series(self):
        identity = {'target': {'pod_uid': guarded.OBJECT_POD_UID,
                               'cgroup': 'cri-containerd-original.scope',
                               'memory_max': 805306368}}
        sample = {'target': dict(identity['target'])}
        self.assertTrue(guarded.same_object_cgroup(sample, identity))
        sample['target']['cgroup'] = 'cri-containerd-restarted.scope'
        self.assertFalse(guarded.same_object_cgroup(sample, identity))

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
                'import pod_preflight_bb; from pathlib import Path; '
                'pod_preflight_bb.verify_workload_imports_at('
                f'workspace=Path({str(root)!r}),'
                f'bundle=Path({str(BUNDLE)!r}),'
                f'prefix={runner.PREFIX!r})'],
                cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
