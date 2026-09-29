"""Own a bounded native trace process and retain only sanitized accounting.

The caller supplies the native command and issues uniquely tagged marker requests
before workload admission and after all workers stop. Markers prove observation
at both boundaries; ledger reconciliation still determines per-call coverage.
For kubectl exec, the remote command must have its own finite timeout: closing
the local kubectl process alone does not prove the remote process has stopped.
"""
import json
import subprocess
from threading import Condition, Thread
from time import monotonic

from minio_trace import accounting


class TraceSession:
    def __init__(self, command, output, bucket, prefix, marker_prefix=None):
        self.condition = Condition()
        self.seen = set()
        self.error = None
        self.ended = False
        self.stopping = False
        self.ready_id = None
        self.final_id = None
        self.output = output.open('x')
        try:
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                            stderr=subprocess.DEVNULL, text=True)
        except BaseException:
            self.output.close()
            raise
        self.thread = Thread(target=self._read, args=(bucket, prefix, marker_prefix), daemon=True)
        self.thread.start()

    def _read(self, bucket, prefix, marker_prefix):
        try:
            for line in self.process.stdout:
                event = json.loads(line)
                if not isinstance(event, dict) or not isinstance(event.get('request'), dict):
                    raise ValueError('invalid native trace record')
                row = accounting(event, bucket, prefix)
                if row is None and marker_prefix is not None:
                    row = accounting(event, bucket, marker_prefix)
                if row is None:
                    continue
                self.output.write(json.dumps(row) + '\n')
                self.output.flush()
                with self.condition:
                    if row['call_id']:
                        self.seen.add(row['call_id'])
                    self.condition.notify_all()
        except BaseException as error:
            # Never retain raw JSON, stderr, headers or exception messages.
            with self.condition:
                self.error = type(error).__name__
        finally:
            self.output.close()
            with self.condition:
                self.ended = True
                self.condition.notify_all()

    def check(self):
        if self.error or (not self.stopping and (self.ended or self.process.poll() is not None)):
            raise RuntimeError('native trace failed or ended prematurely: '
                               f'error={self.error or "none"}, exit={self.process.poll()}')

    def _wait(self, call_id, timeout):
        deadline = monotonic() + timeout
        with self.condition:
            while True:
                self.check()
                if call_id in self.seen:
                    return
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError('native trace marker not observed')
                self.condition.wait(remaining)

    def ready(self, call_id, timeout=10):
        if self.ready_id is not None:
            raise ValueError('trace already admitted')
        self._wait(call_id, timeout)
        self.ready_id = call_id

    def finish(self, call_id, timeout=10):
        if self.ready_id is None or call_id == self.ready_id:
            raise ValueError('distinct final marker required after readiness')
        self._wait(call_id, timeout)
        self.final_id = call_id
        self.close()
        if self.error:
            raise RuntimeError('native trace collection failed')
        return {'ready_call_id': self.ready_id, 'final_call_id': self.final_id,
                'collector_stopped': not self.thread.is_alive(),
                'process_exit': self.process.returncode,
                'coverage_requires_ledger_reconciliation': True}

    def close(self):
        self.stopping = True
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError('native trace reader did not stop')
        self.process.stdout.close()
