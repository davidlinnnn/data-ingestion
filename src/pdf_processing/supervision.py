"""One sequential, correlated native parser process; memory never owns progress."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import sys
import time
import uuid

from .execution import ChildFailure


def now():
    return datetime.now(timezone.utc).isoformat()


class WarmParser:
    def __init__(self, *, startup_seconds=120, no_progress_seconds=180,
                 terminate_seconds=5, reap_seconds=5, max_requests=100, command=None):
        if any(v <= 0 for v in (startup_seconds, no_progress_seconds, terminate_seconds, reap_seconds, max_requests)):
            raise ValueError('Parser budgets must be positive; provisional pending T09 calibration')
        self.startup_seconds, self.no_progress_seconds = startup_seconds, no_progress_seconds
        self.terminate_seconds, self.reap_seconds = terminate_seconds, reap_seconds
        self.max_requests = max_requests
        self.command = command or [sys.executable, '-m', 'pdf_processing.warm_child']
        self.process = None
        self.lock = asyncio.Lock()
        self.closed = False
        self.count = 0
        self.observation = {'ready': False, 'restarts': 0, 'recycles': 0, 'handoffs': 0,
                            'last_local_progress': None, 'termination_reason': None}

    async def stop(self, reason):
        p = self.process
        self.observation.update(ready=False, termination_reason=reason, forced_kill=False, observed_at=now())
        if p is None:
            return
        if p.returncode is None:
            try:
                os.killpg(p.pid, signal.SIGCONT)
                os.killpg(p.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(p.wait(), self.terminate_seconds)
            except TimeoutError:
                self.observation['forced_kill'] = True
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await asyncio.wait_for(p.wait(), self.reap_seconds)
        if p.returncode is None:
            raise RuntimeError('owned parser was not reaped')
        self.observation['exit_code'] = p.returncode
        self.process = None
        self.count = 0

    async def close(self):
        self.closed = True
        async with self.lock:
            await self.stop('worker_shutdown')

    @asynccontextmanager
    async def fresh_child_handoff(self):
        """Own parser capacity while one memory-heavy fresh child runs.

        The same lock covers ``run``. A handoff requested during capture waits
        for that request to finish. The lock remains held until the caller's
        fresh child has exited, so another queue cannot rebuild the warm parser
        concurrently. Caller cancellation during the initial reap waits for
        owned-process cleanup before it is propagated.
        """
        async with self.lock:
            if self.closed:
                raise ChildFailure('infrastructure', 'worker_draining')
            if self.process is not None:
                self.observation['handoffs'] += 1
                cleanup = asyncio.create_task(self.stop('fresh_child_handoff'))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    # Process ownership outlives the cancelled caller. Do not
                    # let scratch teardown race an unreaped warm parser.
                    await cleanup
                    raise
            yield dict(self.observation)

    async def run(self, request, out, heartbeat, hard_seconds):
        async with self.lock:
            if self.closed:
                raise ChildFailure('infrastructure', 'worker_draining')
            if self.process is None:
                self.process = await asyncio.create_subprocess_exec(*self.command,
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT, start_new_session=True, limit=1024*1024)
                self.observation['restarts'] += 1
            p = self.process
            assert p.stdin is not None and p.stdout is not None
            correlation = uuid.uuid4().hex
            self.observation.update(ready=False, pid=p.pid, request_id=correlation,
                                    observed_at=now(), forced_kill=False)
            started = last = time.monotonic()
            reader = None
            try:
                p.stdin.write((json.dumps({'version':1, 'request_id':correlation, 'request':request})+'\n').encode())
                await p.stdin.drain()
                with (Path(out)/'process.log').open('ab') as log:
                    reader = asyncio.create_task(p.stdout.readline())
                    while True:
                        elapsed = time.monotonic()-started
                        if elapsed > hard_seconds:
                            raise ChildFailure('parser', 'child_hard_deadline')
                        if not self.observation['ready'] and elapsed > self.startup_seconds:
                            raise ChildFailure('parser', 'child_startup_deadline')
                        if self.observation['ready'] and time.monotonic()-last > self.no_progress_seconds:
                            raise ChildFailure('parser', 'child_no_progress')
                        heartbeat({'parser': dict(self.observation), 'durable_completion':False})
                        done, _ = await asyncio.wait({reader}, timeout=.2)
                        if not done:
                            continue
                        raw = reader.result()
                        if not raw:
                            await p.wait()
                            code = 'child_killed_or_oom' if p.returncode == -9 else 'child_crashed'
                            raise ChildFailure('parser', code)
                        log.write(raw); log.flush()
                        reader = asyncio.create_task(p.stdout.readline())
                        try:
                            row = json.loads(raw)
                        except (ValueError, UnicodeDecodeError):
                            continue
                        if not isinstance(row, dict) or row.get('protocol') != 'pdf-warm-v1':
                            continue
                        if row.get('request_id') != correlation:
                            raise ChildFailure('integrity', 'child_correlation_mismatch')
                        kind = row.get('kind')
                        if kind == 'failure':
                            raise ChildFailure(row['category'], row['code'])
                        if kind == 'ready':
                            from .compatibility import methods_match
                            if not methods_match(row.get('method'), request['expected_method'], request.get('checkpoint_compatibility') is not None):
                                raise ChildFailure('method', 'worker_method_mismatch')
                            self.observation['ready'] = True
                        elif kind == 'progress':
                            if not self.observation['ready']:
                                raise ChildFailure('integrity', 'progress_before_readiness')
                            self.observation['stage'] = row.get('stage')
                        elif kind == 'done':
                            if not self.observation['ready']:
                                raise ChildFailure('integrity', 'completion_before_readiness')
                            self.observation.update(memory=row.get('memory'), completed_at=now())
                            self.count += 1
                            if self.count >= self.max_requests:
                                self.observation['recycles'] += 1
                                await self.stop('request_recycle')
                            return dict(self.observation)
                        else:
                            raise ChildFailure('integrity', 'invalid_child_protocol')
                        last = time.monotonic()
                        self.observation['last_local_progress'] = now()
            except BaseException as error:
                await self.stop(error.code if isinstance(error, ChildFailure) else 'attempt_cancelled' if isinstance(error, asyncio.CancelledError) else 'child_transport_failure')
                raise
            finally:
                if reader is not None:
                    reader.cancel()
                    await asyncio.gather(reader, return_exceptions=True)
