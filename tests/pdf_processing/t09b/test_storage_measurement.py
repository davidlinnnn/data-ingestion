import asyncio
import io
import unittest

from storage_measurement import MeasuredClient, scope, summarize


class Client:
    def get_object(self, **args):
        return {'Body': io.BytesIO(args['Key'].encode()),
                'ContentLength': len(args['Key']),
                'ResponseMetadata': {'RetryAttempts': 0}}

    def put_object(self, **args):
        return {'ResponseMetadata': {'RetryAttempts': 2}}


class MeasurementTest(unittest.TestCase):
    def test_failed_put_keeps_unknown_transfer_and_scope_resets(self):
        class Failed(Client):
            def put_object(self, **args):
                raise OSError('connection lost after unknown transfer')
        rows = []
        client = MeasuredClient(Failed(), rows.append)
        with self.assertRaises(OSError):
            with scope('r', 'a', 1):
                client.put_object(Key='x', Body=b'123')
        self.assertEqual(rows[0]['outcome'], 'call_failed')
        self.assertIsNone(rows[0]['transport_bytes'])
        with self.assertRaisesRegex(ValueError, 'scope missing'):
            client.put_object(Key='x', Body=b'123')

    def test_interleaved_requests_and_thread_context(self):
        rows = []
        client = MeasuredClient(Client(), rows.append)

        async def run(key):
            with scope(key, 'activity', 1):
                response = await asyncio.to_thread(client.get_object, Key=key)
                await asyncio.sleep(0)
                await asyncio.to_thread(response['Body'].read)
                await asyncio.to_thread(response['Body'].close)

        async def both():
            await asyncio.gather(run('aaa'), run('bb'))
        asyncio.run(both())
        self.assertEqual({r['request_id']: r['delivered_bytes'] for r in rows},
                         {'aaa': 3, 'bb': 2})
        with self.assertRaisesRegex(ValueError, 'scope missing'):
            client.get_object(Key='unscoped')

    def test_partial_read_and_observer_are_not_full_workload_traffic(self):
        rows = []
        client = MeasuredClient(Client(), rows.append)
        with scope('r', 'a', 1):
            body = client.get_object(Key='abcd')['Body']
            self.assertEqual(body.read(2), b'ab')
            body.close()
            body.close()
        with scope('r', 'verify', 1, 'observer'):
            body = client.get_object(Key='abcd')['Body']
            body.read()
            body.close()
        report = summarize(rows)
        self.assertEqual(report['operations'], 1)
        self.assertEqual(report['delivered_get_bytes'], 2)
        self.assertEqual(report['incomplete_operations'], 1)
        self.assertFalse(report['transport_measurement_complete'])

    def test_sdk_retries_are_not_multiplied_into_invented_wire_bytes(self):
        rows = []
        client = MeasuredClient(Client(), rows.append)
        with scope('r', 'a', 2):
            client.put_object(Key='x', Body=b'123')
        report = summarize(rows)
        self.assertEqual(report['submitted_put_bytes'], 3)
        self.assertEqual(report['sdk_retries'], 2)
        self.assertIsNone(report['transport_bytes'])
        self.assertEqual(rows[0]['attempt'], 2)

    def test_failed_read_retains_returned_bytes_and_closes_body(self):
        class Broken(io.BytesIO):
            def read(self, *args, **kwargs):
                if self.tell():
                    raise OSError('partial transport failure')
                return super().read(2)
        class Partial(Client):
            def get_object(self, **args):
                self.body = Broken(b'abcd')
                return {'Body': self.body, 'ContentLength': 4}
        rows, raw = [], Partial()
        client = MeasuredClient(raw, rows.append)
        with scope('r', 'a', 1):
            body = client.get_object(Key='x')['Body']
            try:
                body.read()
                with self.assertRaises(OSError):
                    body.read()
            finally:
                body.close()
        self.assertTrue(raw.body.closed)
        self.assertEqual(rows[0]['delivered_bytes'], 2)
        self.assertEqual(rows[0]['peak_read_chunk_bytes'], 2)
        self.assertEqual(rows[0]['outcome'], 'read_incomplete')
        self.assertEqual(summarize(rows)['unknown_retry_counts'], 1)


if __name__ == '__main__':
    unittest.main()
