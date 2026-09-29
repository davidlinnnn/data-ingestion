import json
from pathlib import Path
import sys
import tempfile
import unittest

from trace_session import TraceSession


class TraceSessionTest(unittest.TestCase):
    def test_boundary_markers_cleanup_and_early_exit(self):
        def row(call_id):
            return json.dumps({'time': 'now', 'request': {'path': '/b/p/marker',
                              'method': 'GET', 'headers': {'X-T09b-Call-Id': call_id,
                                                          'Authorization': 'secret'}},
                              'response': {'statusCode': 200},
                              'callStats': {'rx': 12, 'tx': 1, 'duration': 1}})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'trace.jsonl'
            first, last = 'a' * 32, 'b' * 32
            script = f'import time; print({row(first)!r}, flush=True); print({row(last)!r}, flush=True); time.sleep(30)'
            trace = TraceSession([sys.executable, '-c', script], output, 'b', 'p')
            try:
                trace.ready(first)
                result = trace.finish(last)
                self.assertTrue(result['collector_stopped'])
                self.assertIsNotNone(trace.process.poll())
                self.assertNotIn('secret', output.read_text())
                self.assertEqual(len(output.read_text().splitlines()), 2)
            finally:
                trace.close()
            failed = TraceSession([sys.executable, '-c', 'print("{truncated")'],
                                  Path(directory) / 'failed.jsonl', 'b', 'p')
            try:
                with self.assertRaisesRegex(RuntimeError, r'error=JSONDecodeError, exit='):
                    failed.ready(first)
            finally:
                failed.close()
