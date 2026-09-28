import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from storage_ledger import Ledger, reconcile
from storage_measurement import MeasuredClient, scope


class LedgerTest(unittest.TestCase):
    def test_hard_exit_keeps_started_read_and_rejects_partial_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.jsonl'
            code = '''
import os, sys
from storage_ledger import Ledger
from storage_measurement import MeasuredClient, scope
class Client:
    def get_object(self, **args):
        os._exit(17)
with scope('request', 'activity', 1):
    MeasuredClient(Client(), Ledger(sys.argv[1])).get_object(Key='source')
'''
            result = subprocess.run([sys.executable, '-B', '-c', code, str(path)],
                                    cwd=Path(__file__).parent, timeout=10)
            self.assertEqual(result.returncode, 17)
            report = reconcile(path)
            self.assertFalse(report['complete'])
            self.assertEqual(report['started'], 1)
            self.assertEqual(len(report['interrupted_calls']), 1)
            with path.open('a') as stream:
                stream.write('{"kind":')
            self.assertEqual(len(reconcile(path)['errors']), 1)

    def test_close_seals_read_and_prevents_overwrite(self):
        class Client:
            def get_object(self, **args):
                return {'Body': io.BytesIO(b'abc'), 'ContentLength': 3}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.jsonl'
            sink = Ledger(path)
            try:
                with scope('request', 'activity', 1):
                    body = MeasuredClient(Client(), sink).get_object(Key='source')['Body']
                    body.read()
                    self.assertFalse(reconcile(path)['complete'])
                    body.close()
                self.assertTrue(reconcile(path)['complete'])
                with self.assertRaises(FileExistsError):
                    Ledger(path)
            finally:
                sink.close()
