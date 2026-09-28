import unittest
import io
import json
from minio_trace import accounting, collect


class TraceTest(unittest.TestCase):
    def test_stream_retains_scoped_rows_before_failure_without_raw_secrets(self):
        row = {'time': 'observed', 'request': {'path': '/b/p/key?secret=x',
               'method': 'GET', 'headers': {'Authorization': 'secret'}},
               'response': {'statusCode': 200, 'body': 'private'},
               'callStats': {'rx': 10, 'tx': 4, 'duration': 1}}
        output = io.StringIO()
        with self.assertRaises(ValueError):
            collect(io.StringIO(json.dumps(row) + '\n{truncated'), output, 'b', 'p')
        self.assertEqual(json.loads(output.getvalue())['server_tx_bytes'], 4)
        self.assertNotIn('secret', output.getvalue())
        self.assertNotIn('private', output.getvalue())
        with self.assertRaisesRegex(ValueError, 'no scoped'):
            collect(io.StringIO(''), io.StringIO(), 'b', 'p')
        with self.assertRaisesRegex(ValueError, 'failed native'):
            collect(io.StringIO('{"status":"error"}\n'), io.StringIO(), 'b', 'p')

    def test_scoped_failure_counts_without_headers_or_query(self):
        row = {'time': 'observed', 'request': {'path': '/t09a/t09b/run/key?secret=x',
               'method': 'HEAD', 'headers': {'Authorization': 'secret'}},
               'response': {'statusCode': 404, 'body': 'private'},
               'callStats': {'rx': 123, 'tx': 45, 'duration': 6}}
        report = accounting(row, 't09a', 't09b/run')
        self.assertEqual(report['status'], 404)
        self.assertEqual(report['server_rx_bytes'], 123)
        self.assertNotIn('secret', str(report))
        self.assertIsNone(accounting(row, 't09a', 't09b/ru'))
        row['callStats'].pop('rx')
        with self.assertRaisesRegex(ValueError, 'accounting'):
            accounting(row, 't09a', 't09b/run')
