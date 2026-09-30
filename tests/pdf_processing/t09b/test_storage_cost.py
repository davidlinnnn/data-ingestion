from pathlib import Path
import tempfile
import unittest

from storage_cost import summarize
from storage_ledger import Ledger


class StorageCostTest(unittest.TestCase):
    def test_payload_amplification_and_buffer_peak(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'storage.jsonl'
            ledger = Ledger(path)
            identity = dict(request_id='request', activity_id='activity', attempt=1,
                            role='workload', sdk_retries=0, transport_bytes=None)
            rows = [
                dict(identity, call_id='put', operation='put_object', key='p/attempts/a/x',
                     delivered_bytes=0, submitted_bytes=10, outcome='call_succeeded'),
                dict(identity, call_id='get-1', operation='get_object', key='p/attempts/a/x',
                     delivered_bytes=10, peak_read_chunk_bytes=6, outcome='read_complete'),
                dict(identity, call_id='get-2', operation='get_object', key='p/attempts/a/x',
                     delivered_bytes=10, peak_read_chunk_bytes=5, outcome='read_complete'),
                dict(identity, call_id='buffer', operation='publication_buffers', key='operation',
                     delivered_bytes=0, concurrent_publication_payload_bytes=12,
                     outcome='call_succeeded'),
            ]
            for row in rows:
                ledger.start(row)
                ledger(row)
            ledger.close()
            result = summarize(path)['requests'][0]
            self.assertEqual(result['unique_attempt_upload_bytes'], 10)
            self.assertEqual(result['read_amplification'], 2)
            self.assertEqual(result['application_submission_ratio'], 1)
            self.assertIsNone(result['committed_payload_bytes'])
            self.assertEqual(result['peak_publication_payload_bytes'], 12)
            self.assertEqual(result['peak_read_chunk_bytes'], 6)
