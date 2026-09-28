"""Exclusive append-only measurement ledger with explicit interrupted calls."""
import json
import os
from threading import Lock


class Ledger:
    def __init__(self, path):
        self.stream = open(path, 'x', encoding='utf-8')
        self.lock = Lock()

    def write(self, kind, event):
        line = json.dumps(dict(event, kind=kind), sort_keys=True) + '\n'
        with self.lock:
            self.stream.write(line)
            self.stream.flush()
            os.fsync(self.stream.fileno())

    def start(self, event):
        self.write('start', event)

    def __call__(self, event):
        self.write('finish', event)

    def close(self):
        with self.lock:
            self.stream.close()


def reconcile(path):
    starts, finishes = {}, {}
    errors = []
    with open(path, encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            try:
                row = json.loads(line)
                call_id = row['call_id']
                if not isinstance(call_id, str) or not call_id:
                    raise ValueError('invalid call id')
                kind = row['kind']
                if kind == 'start':
                    if call_id in starts or call_id in finishes:
                        raise ValueError('duplicate or late start')
                    starts[call_id] = row
                elif kind == 'finish':
                    if call_id not in starts or call_id in finishes:
                        raise ValueError('unmatched or duplicate finish')
                    if any(row[key] != starts[call_id][key] for key in (
                            'request_id', 'activity_id', 'attempt', 'role', 'operation', 'key')):
                        raise ValueError('call identity changed')
                    if row['outcome'] not in ('call_failed', 'call_succeeded',
                                               'read_complete', 'read_incomplete'):
                        raise ValueError('invalid outcome')
                    finishes[call_id] = row
                else:
                    raise ValueError('invalid event kind')
            except (ValueError, KeyError, TypeError) as error:
                errors.append({'line': number, 'error': str(error)})
    pending = sorted(set(starts) - set(finishes))
    return {'complete': bool(starts) and not pending and not errors,
            'started': len(starts), 'finished': len(finishes),
            'interrupted_calls': pending, 'errors': errors,
            'events': list(finishes.values())}
