"""A replacement Activity Pod is accepted only with exact, durable identity proof."""

import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest

from pod_loss_bridge_bg import Host


class PodLossBridgeTest(unittest.TestCase):
    def test_start_and_drain_require_exact_pod_and_sample_proof(self):
        async def exercise():
            with tempfile.TemporaryDirectory() as raw:
                evidence = Path(raw) / 'evidence'
                root = evidence / 'state' / 'pod-loss-bg'
                root.mkdir(parents=True)
                config = {'run_id': 'q04-bg', 'drain_seconds': 1,
                          'window': {'max_replacement_seconds': 2,
                                     'max_sample_gap_seconds': 1}}
                config_path = root / 'config.json'
                config_path.write_text(json.dumps(config))
                host = Host(config_path, root, config)

                async def answer(kind, generation, uid, **extra):
                    path = host.control / f'{generation}-{kind}.request.json'
                    while not path.exists():
                        await asyncio.sleep(.01)
                    request = json.loads(path.read_text())
                    directory = root / f'worker-{generation}'
                    directory.mkdir(exist_ok=True)
                    observed = time.time()
                    (directory / 'samples.jsonl').write_text(json.dumps({
                        'time': observed, 'generation': generation,
                    }) + '\n')
                    (directory / 'ready.json').write_text(json.dumps({
                        'time': observed + .001, 'generation': generation,
                        'pid': generation + 10, 'created': observed - 1,
                    }))
                    ready_raw = (directory / 'ready.json').read_bytes()
                    first_raw = (directory / 'samples.jsonl').read_bytes()
                    reply = {'run_id': 'q04-bg', 'kind': kind,
                             'generation': generation, 'status': 'PASS',
                             'pod_uid': uid, 'worker_pid': generation + 10,
                             'worker_created': observed - 1,
                             'ready_sha256': hashlib.sha256(ready_raw).hexdigest(),
                             'first_sample_sha256': hashlib.sha256(first_raw).hexdigest(),
                             **extra}
                    (host.control / f'{generation}-{kind}.reply.json').write_text(
                        json.dumps(reply))
                    return request

                first = asyncio.create_task(answer('start', 1, 'old-uid'))
                await host.start()
                self.assertEqual((await first)['generation'], 1)
                self.assertEqual(host.pod_uid, 'old-uid')
                second = asyncio.create_task(answer('drain', 2, 'new-uid',
                    old_pod_uid='old-uid', old_runtime_absent=True,
                    old_scratch_absent=True))
                proof = await host.drain(99)
                request = await second
                self.assertEqual(request['old_pod_uid'], 'old-uid')
                self.assertEqual(request['child_pid'], 99)
                self.assertLessEqual(request['requested_at'], time.time())
                self.assertEqual(proof['scope'], 'owned_pod')
                self.assertEqual(proof['new_pod_uid'], 'new-uid')
                self.assertEqual(json.loads((host.current / 'host.json').read_text())
                    ['pod']['uid'], 'new-uid')
        asyncio.run(exercise())

    def test_reject_missing_old_pod_cleanup(self):
        async def exercise():
            with tempfile.TemporaryDirectory() as raw:
                root = Path(raw) / 'evidence' / 'state' / 'pod-loss-bg'
                root.mkdir(parents=True)
                config = {'run_id': 'q04-bg', 'drain_seconds': 1,
                          'window': {'max_replacement_seconds': 2}}
                path = root / 'config.json'
                path.write_text(json.dumps(config))
                host = Host(path, root, config)
                host.generation, host.pod_uid = 1, 'old-uid'
                task = asyncio.create_task(host.drain(99))
                reply = host.control / '2-drain.reply.json'
                while not (host.control / '2-drain.request.json').exists():
                    await asyncio.sleep(.01)
                reply.write_text(json.dumps({'run_id': 'q04-bg', 'kind': 'drain',
                    'generation': 2, 'status': 'PASS', 'pod_uid': 'new-uid',
                    'old_pod_uid': 'old-uid', 'old_runtime_absent': False,
                    'old_scratch_absent': True}))
                with self.assertRaisesRegex(ValueError, 'absence unproven'):
                    await task
        asyncio.run(exercise())

    def test_reject_stale_worker_sample(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / 'evidence' / 'state' / 'pod-loss-bg'
            root.mkdir(parents=True)
            config = {'run_id': 'q04-bg', 'drain_seconds': 1,
                      'window': {'max_replacement_seconds': 2,
                                 'max_sample_gap_seconds': 1}}
            path = root / 'config.json'
            path.write_text(json.dumps(config))
            host = Host(path, root, config)
            directory = root / 'worker-1'
            directory.mkdir()
            old = time.time() - 30
            (directory / 'samples.jsonl').write_text(json.dumps({
                'time': old, 'generation': 1}) + '\n')
            (directory / 'ready.json').write_text(json.dumps({
                'time': old + .01, 'generation': 1, 'pid': 11,
                'created': old - 1}) + '\n')
            with self.assertRaisesRegex(ValueError, 'stale'):
                host.adopt({'generation': 1, 'pod_uid': 'old-uid',
                    'worker_pid': 11, 'worker_created': old - 1,
                    'ready_sha256': hashlib.sha256(
                        (directory / 'ready.json').read_bytes()).hexdigest(),
                    'first_sample_sha256': hashlib.sha256(
                        (directory / 'samples.jsonl').read_bytes()).hexdigest()})
            self.assertEqual(host.generation, 0)
            self.assertIsNone(host.pod_uid)

    def test_reject_unbound_worker_evidence_and_still_request_cleanup(self):
        async def exercise():
            with tempfile.TemporaryDirectory() as raw:
                root = Path(raw) / 'evidence' / 'state' / 'pod-loss-bg'
                root.mkdir(parents=True)
                config = {'run_id': 'q04-bg', 'drain_seconds': 1,
                          'window': {'max_replacement_seconds': 2,
                                     'max_sample_gap_seconds': 1}}
                path = root / 'config.json'
                path.write_text(json.dumps(config))
                host = Host(path, root, config)
                directory = root / 'worker-1'
                directory.mkdir()
                observed = time.time()
                (directory / 'samples.jsonl').write_text(json.dumps({
                    'time': observed, 'generation': 1}) + '\n')
                (directory / 'ready.json').write_text(json.dumps({
                    'time': observed + .001, 'generation': 1,
                    'pid': 11, 'created': observed - 1}) + '\n')
                with self.assertRaisesRegex(ValueError, 'binding'):
                    host.adopt({'generation': 1, 'pod_uid': 'old-uid',
                                'worker_pid': 11, 'worker_created': observed - 1,
                                'ready_sha256': 'wrong',
                                'first_sample_sha256': 'wrong'})
                self.assertEqual(host.generation, 0)
                stop = asyncio.create_task(host.stop())
                request_path = host.control / '0-stop.request.json'
                while not request_path.exists():
                    await asyncio.sleep(.01)
                request = json.loads(request_path.read_text())
                self.assertIsNone(request['known_pod_uid'])
                (host.control / '0-stop.reply.json').write_text(json.dumps({
                    'run_id': 'q04-bg', 'kind': 'stop', 'generation': 0,
                    'status': 'PASS', 'activity_pods_absent': True,
                    'worker_absent': True, 'emptydirs_absent': True}))
                await stop
                await host.stop()
                self.assertTrue(host.stopped)
        asyncio.run(exercise())
