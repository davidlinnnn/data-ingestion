"""Real botocore transport against a loopback fault server; no cloud credentials."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import unittest

import boto3
from botocore.config import Config
from botocore.exceptions import IncompleteReadError, ResponseStreamingError

from storage_measurement import MeasuredClient, scope, summarize


class SDKStorageTest(unittest.TestCase):
    def test_real_retry_and_truncated_response(self):
        uploads = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_PUT(self):
                uploads.append(self.rfile.read(int(self.headers['Content-Length'])))
                self.send_response(503 if len(uploads) == 1 else 200)
                self.send_header('Content-Length', '0')
                self.end_headers()

            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Length', '8')
                self.end_headers()
                self.wfile.write(b'abcd')
                self.wfile.flush()
                self.close_connection = True

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        rows = []
        raw = boto3.client('s3', endpoint_url=f'http://127.0.0.1:{server.server_port}',
                           aws_access_key_id='test', aws_secret_access_key='test',
                           region_name='us-east-1', config=Config(
                               connect_timeout=2, read_timeout=2,
                               retries={'mode': 'standard', 'total_max_attempts': 2},
                               request_checksum_calculation='when_required',
                               response_checksum_validation='when_required'))
        client = MeasuredClient(raw, rows.append)
        try:
            with scope('request', 'activity', 1):
                client.put_object(Bucket='test', Key='retry', Body=b'payload')
                body = client.get_object(Bucket='test', Key='partial')['Body']
                try:
                    self.assertEqual(body.read(2), b'ab')
                    with self.assertRaises((IncompleteReadError, ResponseStreamingError)):
                        body.read()
                finally:
                    body.close()
            self.assertEqual(uploads, [b'payload', b'payload'])
            self.assertEqual(rows[0]['sdk_retries'], 1)
            self.assertEqual(rows[1]['outcome'], 'read_incomplete')
            self.assertEqual(rows[1]['delivered_bytes'], 2)
            report = summarize(rows)
            self.assertEqual(report['submitted_put_bytes'], 7)
            self.assertIsNone(report['transport_bytes'])
        finally:
            raw.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
