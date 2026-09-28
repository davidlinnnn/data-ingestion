from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from publication_buffers import instrument
from storage_ledger import Ledger, reconcile
from storage_measurement import scope, summarize


class BufferTest(unittest.TestCase):
    def test_aliases_count_once_and_failure_releases_buffers(self):
        def fail(*args):
            raise RuntimeError('publication interrupted')
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory)/'buffers.jsonl')
            store = SimpleNamespace(publish=fail)
            instrument(store, ledger)
            payload = b'abcd'
            try:
                with scope('r', 'a', 1):
                    for _ in range(2):
                        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                            store.publish('operation', {'a': payload, 'b': payload})
            finally:
                ledger.close()
            report = reconcile(Path(directory)/'buffers.jsonl')
            self.assertTrue(report['complete'])
            self.assertEqual([x['publication_payload_bytes'] for x in report['events']], [4, 4])
            self.assertEqual([x['concurrent_publication_payload_bytes'] for x in report['events']], [4, 4])
            self.assertEqual(summarize(report['events'])['operations'], 0)
