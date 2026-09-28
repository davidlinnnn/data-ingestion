import unittest
from minio_trace import accounting


class TraceTest(unittest.TestCase):
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
