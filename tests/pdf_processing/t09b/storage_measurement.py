"""Harness-only S3 payload observation; deliberately not a network-byte meter.

Wrap the worker's S3 client before constructing Store. Use scope around each
Activity (including prepare/enrichment), with a separate observer scope for
verification. Context follows asyncio.to_thread without shared-counter deltas.
The caller owns the append-only sink and must treat sink failures as fatal.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from time import monotonic
from uuid import uuid4


_identity = ContextVar('t09b_storage_identity', default=None)


@contextmanager
def scope(request_id, activity_id, attempt, role='workload'):
    if not request_id or not activity_id or type(attempt) is not int or attempt < 1:
        raise ValueError('request, activity and positive attempt required')
    if role not in ('workload', 'observer'):
        raise ValueError('unknown measurement role')
    token = _identity.set(dict(request_id=request_id, activity_id=activity_id,
                               attempt=attempt, role=role))
    try:
        yield
    finally:
        _identity.reset(token)


class MeasuredClient:
    def __init__(self, client, emit):
        self.client, self.emit, self.lock = client, emit, Lock()

    def __getattr__(self, name):
        return getattr(self.client, name)

    def record(self, event):
        with self.lock:
            self.emit(event)

    def call(self, operation, args):
        identity = _identity.get()
        if identity is None:
            raise ValueError('storage measurement scope missing')
        event = dict(identity, operation=operation, key=args['Key'],
                     call_id=uuid4().hex,
                     started=monotonic(), delivered_bytes=0,
                     sdk_retries=None, transport_bytes=None)
        body = args.get('Body')
        if operation == 'put_object':
            # Do not consume or seek streams for measurement.
            event['submitted_bytes'] = len(body) if isinstance(body, (bytes, bytearray)) else None
        # Durable sinks persist intent before invoking the SDK. Simple list sinks
        # remain useful for unit tests, but cannot prove interrupted coverage.
        if hasattr(self.emit, 'start'):
            self.emit.start(event)
        try:
            result = getattr(self.client, operation)(**args)
        except BaseException as error:
            response = getattr(error, 'response', {})
            event.update(outcome='call_failed', error_type=type(error).__name__,
                         sdk_retries=response.get('ResponseMetadata', {}).get('RetryAttempts'),
                         finished=monotonic())
            self.record(event)
            raise
        event['sdk_retries'] = result.get('ResponseMetadata', {}).get('RetryAttempts')
        if operation == 'get_object':
            return {**result, 'Body': MeasuredBody(result['Body'], event, self.record,
                                                 result.get('ContentLength'))}
        event.update(outcome='call_succeeded', finished=monotonic())
        self.record(event)
        return result

    def get_object(self, **args):
        return self.call('get_object', args)

    def put_object(self, **args):
        return self.call('put_object', args)


class MeasuredBody:
    def __init__(self, body, event, emit, expected):
        self.body, self.event, self.emit, self.expected = body, event, emit, expected
        self.failed, self.closed = False, False

    def read(self, *args, **kwargs):
        try:
            data = self.body.read(*args, **kwargs)
        except BaseException:
            self.failed = True
            raise
        self.event['delivered_bytes'] += len(data)
        return data

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            self.body.close()
        except BaseException:
            self.failed = True
            raise
        finally:
            complete = not self.failed and self.expected == self.event['delivered_bytes']
            self.event.update(outcome='read_complete' if complete else 'read_incomplete',
                              finished=monotonic())
            self.emit(self.event)


def summarize(events):
    """Never promote successful payloads to total wire traffic or hide retries."""
    rows = [row for row in events if row['role'] == 'workload']
    return {
        'operations': len(rows),
        'delivered_get_bytes': sum(row['delivered_bytes'] for row in rows
                                   if row['operation'] == 'get_object'),
        'submitted_put_bytes': sum(row.get('submitted_bytes') or 0 for row in rows),
        'unknown_put_sizes': sum(row['operation'] == 'put_object' and
                                 row.get('submitted_bytes') is None for row in rows),
        'incomplete_operations': sum(row['outcome'] in ('call_failed', 'read_incomplete')
                                     for row in rows),
        'sdk_retries': sum(row['sdk_retries'] or 0 for row in rows),
        'unknown_retry_counts': sum(row['sdk_retries'] is None for row in rows),
        'transport_bytes': None,
        'transport_measurement_complete': False,
    }
