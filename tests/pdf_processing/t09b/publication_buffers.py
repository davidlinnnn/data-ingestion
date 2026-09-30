"""Observe existing serialized publication buffers without copying their data.

This excludes parser/native allocations, transport buffers and caller-retained
GET results. Whole-Pod telemetry remains the total memory observation.
"""
from functools import wraps
from threading import Lock
from time import monotonic
from uuid import uuid4

from storage_measurement import _identity


def instrument(store, ledger):
    original = store.publish
    lock = Lock()
    active = {}

    @wraps(original)
    def publish(operation, files, *args, **kwargs):
        identity = _identity.get()
        if identity is None:
            raise ValueError('publication measurement scope missing')
        call_id = uuid4().hex
        # Count unique bytes objects, not references or copies of their contents.
        buffers = {id(value): len(value) for value in files.values() if isinstance(value, bytes)}
        event = dict(identity, call_id=call_id, operation='publication_buffers',
                     key=operation, started=monotonic(), delivered_bytes=0,
                     sdk_retries=None, transport_bytes=None)
        with lock:
            active[call_id] = buffers
            union = {key: size for values in active.values() for key, size in values.items()}
            event.update(publication_payload_bytes=sum(buffers.values()),
                         concurrent_publication_payload_bytes=sum(union.values()))
        try:
            ledger.start(event)
            result = original(operation, files, *args, **kwargs)
        except BaseException:
            event['outcome'] = 'call_failed'
            raise
        else:
            event['outcome'] = 'call_succeeded'
            return result
        finally:
            with lock:
                active.pop(call_id)
            if 'outcome' in event:
                event['finished'] = monotonic()
                ledger(event)

    store.publish = publish
