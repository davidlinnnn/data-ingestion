"""Actual owned evidence-child interruption at the final-result seam, local S3 only."""
import asyncio
import importlib.metadata
import json
from pathlib import Path
import tempfile
import unittest

from delivery import serialized_document
from fixtures import SOURCE
from test_publication import MemoryS3, seed
from q03_fixtures import profile
from pdf_processing.processing import Processing, encoded
from pdf_processing.enrichment import Enrichment
from pdf_processing.object_store import Store, digest
from pdf_processing.compatibility import dependencies
from oracle.score import score
from interruption import EvidenceInterruption, interrupted_call, registration_operations

class ListingMemoryS3(MemoryS3):
    def get_paginator(self, name):
        assert name == 'list_objects_v2'
        client = self
        class Pages:
            def paginate(self, Bucket, Prefix):
                keys = sorted(k for k in client.objects if k.startswith(Prefix))
                # Exercise pagination, including the final complete registration.
                for key in keys:
                    yield {'Contents': [{'Key': key}]}
        return Pages()

class InterruptedEvidence(unittest.IsolatedAsyncioTestCase):
    def prepared(self, root, client=None):
        store = Store(client or ListingMemoryS3(), 'test', 'q03-interruption')
        prof = profile()
        prof['method']['packages']['pypdfium2'] = importlib.metadata.version('pypdfium2')
        source = Path('/private/tmp/t09a-fixtures/08.pdf').read_bytes()
        self.assertEqual(digest(source), SOURCE)
        key = store.prefix+'sources/source.pdf'
        store.client.put_object(Bucket=store.bucket, Key=key, Body=source)
        request = {'version': 3, 'source_revision': 'q03-interrupted-local',
                   'artifact': {'sha256': SOURCE, 'key': key, 'version_id': 'test-version', 'name': 'source.pdf'}}
        processing = Processing(store, root/'scratch', root/'models', prof)
        doc = serialized_document()
        seed(processing, doc, request)
        evidence_id = 'pdf-evidence-v1:' + digest(encoded({'assembly': 'assembly', 'parsed_result': 'parsed',
            'source': request, 'policy': prof['content_evidence'],
            'dependencies': dependencies('evidence', prof, processing.producer)}))
        value = {'stage': 'finalize', 'plan': 'plan', 'selection': 'selection', 'outcomes': []}
        hook = EvidenceInterruption(store, processing.scratch, evidence_id, SOURCE,
                                    digest(encoded(doc)), root/'interrupted', timeout=30)
        return store, prof, processing, doc, evidence_id, value, hook

    async def test_interrupted_required_evidence_never_completes_then_retries_cleanly(self):
        with tempfile.TemporaryDirectory(prefix='q03-interruption-test-') as tmp:
            root = Path(tmp)
            store, prof, processing, doc, evidence_id, value, hook = self.prepared(root)
            observation, failure = await interrupted_call(hook, lambda: Enrichment(processing).run(value))
            self.assertIsInstance(failure, RuntimeError)
            self.assertEqual(str(failure), 'child_process_failed')
            self.assertTrue(observation['partial_files'])
            self.assertTrue(observation['source_checked'])
            self.assertFalse(any(i.startswith('pdf-complete-') for i in registration_operations(store)))
            self.assertIsNone(store.resolve(evidence_id))
            self.assertFalse(Path(observation['scratch']).exists())
            replacement = Processing(store, root/'replacement', root/'models', prof)
            self.assertEqual(replacement.producer, processing.producer)
            result = await Enrichment(replacement).run(value)
            final = Enrichment(replacement).read(result['operation'], 'processing-result.json')
            binding = Enrichment(replacement).read(final['relationships'], 'relationships.json')
            report = binding['relationships']
            candidate = {**report['candidates'], 'relationships': [{**r, 'disposition': 'candidate'} for r in report['resolved']]}
            self.assertEqual([r['structure_pass'] for r in score(doc, candidate)], [True]*4)
            replay = await Enrichment(replacement).run(value)
            self.assertEqual(replay['operation'], result['operation'])
            self.assertEqual([i for i in registration_operations(store) if i.startswith('pdf-complete-')], [result['operation']])
            self.assertEqual(Enrichment(replacement).read('assembly', 'document.json'), doc)
            self.assertEqual(json.loads((root/'interrupted/observation.json').read_text()), observation)
            # Optional private evidence retention for the handoff; never write
            # full source/partial images into the repository's test evidence.
            import os
            if destination := os.environ.get('Q03_INTERRUPTION_RECORD'):
                import shutil
                retained = Path(destination)
                retained.mkdir(parents=True, exist_ok=False)
                shutil.copytree(root/'interrupted', retained/'interrupted')
                for label, identity in [('final', result['operation']), ('evidence', final['content_evidence']),
                                        ('relationships', final['relationships']), ('assembly', final['assembly'])]:
                    registration = store.resolve(identity)
                    assert registration is not None
                    (retained/label).mkdir()
                    (retained/label/'registration.json').write_bytes(encoded(registration))
                    for entry in registration['files']:
                        (retained/label/entry['name']).write_bytes(store.read_artifact(entry))
                (retained/'summary.json').write_bytes(encoded({'scope': 'local real subprocess; MemoryS3; no Temporal/K8s',
                    'producer': processing.producer, 'source_sha256': SOURCE, 'interruption': observation,
                    'failure': str(failure), 'retry_final': result['operation'], 'exact_replay': replay['operation'],
                    'final_registrations': [i for i in registration_operations(store) if i.startswith('pdf-complete-')],
                    'four_structures_pass': True, 'partial_scratch_removed': True, 'verified': True}))

    async def test_missing_evidence_child_times_out_without_signaling_an_unrelated_child(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = Store(ListingMemoryS3(), 'test', 'q03-unrelated')
            process = await asyncio.create_subprocess_exec(sys.executable, '-c', 'import time; time.sleep(30)',
                                                          start_new_session=True)
            try:
                hook = EvidenceInterruption(store, root/'scratch', 'absent', 'a'*64, 'b'*64,
                                            root/'observation', timeout=.1)
                with self.assertRaises(TimeoutError):
                    await hook.watch()
                self.assertIsNone(process.returncode)
                self.assertFalse((root/'observation/observation.json').exists())
                self.assertEqual(registration_operations(store), [])
            finally:
                process.kill()
                await process.wait()

    async def test_completed_attempt_cannot_be_reported_as_successful_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = Store(ListingMemoryS3(), 'test', 'q03-missed-boundary')
            hook = EvidenceInterruption(store, root/'scratch', 'absent', 'a'*64, 'b'*64,
                                        root/'observation', timeout=.2)
            async def already_done():
                return {'processing_complete': True}
            with self.assertRaisesRegex(RuntimeError, 'operation_finished_before_interruption'):
                await interrupted_call(hook, already_done)
            self.assertFalse((root/'observation/observation.json').exists())

    async def test_published_evidence_is_not_an_interruptible_required_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = Store(ListingMemoryS3(), 'test', 'q03-already-published')
            store.publish('evidence', {'fixture.json': b'{}'})
            hook = EvidenceInterruption(store, root/'scratch', 'evidence', 'a'*64, 'b'*64,
                                        root/'observation', timeout=.2)
            with self.assertRaisesRegex(RuntimeError, 'interruption_evidence_already_published'):
                await hook.watch()
            self.assertEqual(registration_operations(store), ['evidence'])

    async def test_cancellation_joins_capture_before_scratch_cleanup(self):
        await self.cancellation_during_capture(False)

    async def test_hook_timeout_then_outer_cancellation_still_joins_capture(self):
        await self.cancellation_during_capture(True)

    async def cancellation_during_capture(self, expire):
        import threading
        entered, release = threading.Event(), threading.Event()
        class DelayedListing(ListingMemoryS3):
            calls = 0
            def get_paginator(self, name):
                self.calls += 1
                if self.calls == 2:
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError('test_storage_deadline')
                return super().get_paginator(name)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store, _, processing, _, _, value, hook = self.prepared(root, DelayedListing())
            if expire:
                hook.timeout = 1
            task = asyncio.create_task(interrupted_call(hook, lambda: Enrichment(processing).run(value)))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 20))
                if expire:
                    async with asyncio.timeout(3):
                        while not (hook.out/'hook-failure.json').exists():
                            await asyncio.sleep(.01)
                task.cancel()
                await asyncio.sleep(.1)
                self.assertFalse(task.done(), 'capture must finish before cancellation releases scratch')
                self.assertTrue(list(processing.scratch.glob('activity-evidence-*')))
            finally:
                release.set()
                result = await asyncio.gather(task, return_exceptions=True)
            self.assertIsInstance(result[0], asyncio.CancelledError)
            manifest = json.loads((hook.out/'partial-manifest.json').read_text())
            for name, checksum in manifest['files'].items():
                self.assertEqual(digest((hook.out/'partial'/name).read_bytes()), checksum)
            self.assertFalse(list(processing.scratch.glob('activity-evidence-*')))
            self.assertFalse(any(i.startswith('pdf-complete-') for i in registration_operations(store)))
            await hook.reaped()


    async def test_stop_signal_waits_for_observed_os_state(self):
        import os
        from unittest.mock import Mock
        import psutil
        hook = EvidenceInterruption(None, '.', 'id', 'a', 'b', '.', timeout=.2)
        # psutil is the external OS boundary, not a production processing seam.
        process = Mock()
        process.is_running.return_value = True
        process.ppid.return_value = os.getpid()
        process.status.side_effect = [psutil.STATUS_RUNNING, psutil.STATUS_STOPPED]
        hook.child = process
        async with asyncio.timeout(.2):
            await hook.wait_stopped()
        self.assertEqual(process.status.call_count, 2)
        process.is_running.return_value = False
        with self.assertRaisesRegex(RuntimeError, 'interruption_child_not_owned'):
            await hook.wait_stopped()
