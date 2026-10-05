import asyncio
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from recovery_trial import Run, drain_checks, ready_to_drain


class RecoveryTrialTest(unittest.TestCase):
    def test_waits_for_next_group_after_ten_durable_pages(self):
        groups = [{'stage': 'group', 'parser': {'request_id': name}}
                  for name in ('first', 'second')]
        progress = {'registered_pages': 10, 'steps': groups}
        self.assertFalse(ready_to_drain(progress, {'parser': {'ready': True, 'request_id': 'second'}}))
        self.assertTrue(ready_to_drain(progress, {'parser': {'ready': True, 'request_id': 'third'}}))
        self.assertFalse(ready_to_drain(progress, {'parser': {'ready': True}}))
        progress['registered_pages'] = 5
        self.assertFalse(ready_to_drain(progress, {'parser': {'ready': True, 'request_id': 'third'}}))

    def test_matched_recovery_proof_for_both_group_sizes(self):
        for size in (5, 10):
            starts = list(range(1, 52, size))
            result = {'pages': 51, 'steps': [
                {'stage': 'group', 'operation': str(start)} for start in starts]}
            retained = [str(start) for start in starts[:10 // size]]
            attempts = [{'range': [start, min(start + size - 1, 51)],
                         'attempt': 2 if start == 11 else 1} for start in starts]
            proof = drain_checks(attempts, retained, result, size)
            self.assertEqual(proof['retried_range'], [11, 10 + size])
            with self.assertRaisesRegex(ValueError, 'durable groups'):
                drain_checks(attempts, [], result, size)
            attempts[0]['attempt'] = 2
            with self.assertRaisesRegex(ValueError, 'wrong group'):
                drain_checks(attempts, retained, result, size)


class RecoveryHookTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_trial_does_not_drain_the_just_completed_second_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / 'config.json'
            config_path.write_text('{}')
            groups = [{'stage': 'group', 'operation': name, 'parser': {'request_id': name}}
                      for name in ('first', 'second')]
            progress = {'registered_pages': 10, 'steps': groups}
            queries = AsyncMock(return_value=progress)

            async def pending_result():
                await asyncio.sleep(60)

            handle = SimpleNamespace(query=queries, result=pending_result)
            host = SimpleNamespace(current=root, config_path=config_path, generation=1,
                                   drain=AsyncMock(side_effect=ValueError('injected drain stop')))
            run = Run.__new__(Run)
            run.root = root
            run.config = {'profiles': {'native': {'id': 'native', 'group_pages': 5}},
                          'bundle': str(root), 'producer': {}, 'window': {
                              'ends_at': time.time() + 300, 'cleanup_seconds': 120},
                          'trial_seconds': 180, 'run_id': 'local-hook',
                          'workflow_queue': 'local', 'queues': {'native': 'local'}}
            run.bundle = {'fixtures': [{'id': 'native', 'source_revision': 'local'}]}
            run.store = None
            run.host = host
            run.client = SimpleNamespace(start_workflow=AsyncMock(return_value=handle))
            # Admission sample, stale last-completed sample, then next-group sample.
            run.guard = AsyncMock(side_effect=[{},
                {'parser': {'pid': 1, 'ready': True, 'request_id': 'second'}, 'vm_oom_kill': 0},
                {'parser': {'pid': 1, 'ready': True, 'request_id': 'third'}, 'vm_oom_kill': 0}])

            async def settle(target, error, injection, handle, task, request, audit):
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                return {}

            run.retain_failure = settle
            namespace = Run.trial.__globals__
            with patch.dict(namespace, capture=lambda *args: {},
                            validate_window=lambda *args: None,
                            sample=lambda: {'vm_oom_kill': 0, 'available': 100,
                                            'psi_full_avg10': 100}):
                run.config['window'].update(min_available_bytes=1, max_replacement_seconds=5)
                with self.assertRaisesRegex(ValueError, 'injected drain stop'):
                    await run.trial('native', 'drain', 'drain-native')
            self.assertEqual(queries.await_count, 2)
            host.drain.assert_awaited_once_with(1)
            before = json.loads((root / 'drain-native/before-drain.json').read_text())
            self.assertEqual(before['retained'], ['first', 'second'])
