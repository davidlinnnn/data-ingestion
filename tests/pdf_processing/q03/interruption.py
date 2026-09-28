"""Test-only OS fault injection; no production bytes or methods are patched.

Requires exclusive, serial ownership of the caller's evidence child and scratch.
Only a new direct child running exactly `-m pdf_processing.evidence` is eligible.
"""
import asyncio
import json
import os
from pathlib import Path
import sys
import time

import psutil
from PIL import Image
from pdf_processing.object_store import digest
from pdf_processing.processing import encoded


def registration_operations(store):
    operations = []
    for page in store.client.get_paginator('list_objects_v2').paginate(
            Bucket=store.bucket, Prefix=store.prefix+'registered/'):
        for item in page.get('Contents', []):
            raw = store.get(item['Key'])
            if raw is None:
                raise RuntimeError('listed_registration_disappeared')
            operations.append(json.loads(raw)['operation'])
    return sorted(operations)


async def join_cleanup(task):
    """Defer repeated cancellation until this owned task has really stopped."""
    joined = asyncio.gather(task, return_exceptions=True)
    cancelled = False
    while not joined.done():
        try:
            await asyncio.shield(joined)
        except asyncio.CancelledError:
            cancelled = True
    return cancelled


class EvidenceInterruption:
    def __init__(self, store, scratch, evidence_id, source_sha256, document_sha256, out, timeout: float = 30):
        self.store, self.scratch = store, Path(scratch)
        self.evidence_id = evidence_id
        self.source_sha256, self.document_sha256 = source_sha256, document_sha256
        self.out, self.timeout = Path(out), timeout
        self.child = None

    def evidence_children(self):
        return [p for p in psutil.Process(os.getpid()).children(recursive=False)
                if p.cmdline() == [sys.executable, '-m', 'pdf_processing.evidence']]

    def audit_incomplete(self):
        if self.store.resolve(self.evidence_id) is not None:
            raise RuntimeError('interruption_evidence_already_published')
        operations = registration_operations(self.store)
        if any(i.startswith('pdf-complete-') for i in operations):
            raise RuntimeError('interruption_complete_already_published')
        return operations

    def capture(self, scratch):
        if (digest((scratch/'source.pdf').read_bytes()) != self.source_sha256
                or digest((scratch/'document.json').read_bytes()) != self.document_sha256):
            raise RuntimeError('interruption_scratch_attribution_mismatch')
        with Image.open(scratch/'result/page-1.png') as image:
            image.load()
        retained = self.out/'partial'
        retained.mkdir()
        files = {}
        for path in sorted(scratch.rglob('*')):
            if path.is_file():
                relative = path.relative_to(scratch)
                target = retained/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                data = path.read_bytes()
                target.write_bytes(data)
                files[str(relative)] = digest(data)
        (self.out/'partial-manifest.json').write_bytes(encoded({'files': files,
            'source_sha256': self.source_sha256, 'document_sha256': self.document_sha256}))
        return self.audit_incomplete(), files

    async def watch(self):
        if self.timeout <= 0:
            raise ValueError('interruption_timeout_must_be_positive')
        self.out.mkdir(parents=True, exist_ok=False)
        if self.evidence_children() or list(self.scratch.glob('activity-evidence-*')):
            raise RuntimeError('interruption_requires_exclusive_fresh_scratch')
        self.audit_incomplete()
        armed_at = time.time()
        (self.out/'armed.json').write_bytes(encoded({'pid': os.getpid(), 'armed_at': armed_at,
            'hook_sha256': digest(Path(__file__).read_bytes()), 'evidence_id': self.evidence_id,
            'source_sha256': self.source_sha256, 'document_sha256': self.document_sha256,
            'timeout_seconds': self.timeout}))
        capture = None
        try:
            async with asyncio.timeout(self.timeout):
                while True:
                    children = self.evidence_children()
                    if len(children) > 1:
                        raise RuntimeError('interruption_ambiguous_evidence_child')
                    ready = []
                    for page in self.scratch.glob('activity-evidence-*/result/page-1.png'):
                        # The file appears before PNG encoding finishes. Do not
                        # suspend the writer until its complete IEND is present.
                        if page.stat().st_size >= 12:
                            with page.open('rb') as stream:
                                stream.seek(-12, 2)
                                if stream.read() == b'\x00\x00\x00\x00IEND\xaeB`\x82':
                                    ready.append(page)
                    if children and ready:
                        if len(ready) != 1 or children[0].create_time() < armed_at - 1:
                            raise RuntimeError('interruption_ambiguous_scratch')
                        self.child = children[0]
                        self.child.suspend()
                        # Process object checks creation identity on signaling, not bare PID.
                        await self.wait_stopped()
                        scratch = ready[0].parents[1]
                        capture = asyncio.create_task(asyncio.to_thread(self.capture, scratch))
                        operations, files = await asyncio.shield(capture)
                        observation = {'pid': self.child.pid, 'create_time': self.child.create_time(),
                            'parent_pid': os.getpid(), 'command': self.child.cmdline(), 'scratch': str(scratch),
                            'source_checked': True, 'progress': 'first_page_decoded', 'partial_files': files,
                            'registered_before_kill': operations, 'evidence_id': self.evidence_id,
                            'signal': 'SIGKILL', 'scope': 'owned evidence child only'}
                        self.child.kill()
                        (self.out/'observation.json').write_bytes(encoded(observation))
                        return observation
                    await asyncio.sleep(.005)
        except BaseException as error:
            (self.out/'hook-failure.json').write_bytes(encoded({'type': type(error).__name__, 'error': str(error)}))
            raise
        finally:
            # Finish retaining diagnostics before killing the child allows the
            # production supervisor to remove its TemporaryDirectory.
            try:
                if capture is not None:
                    cancelled = await join_cleanup(capture)
                    if cancelled:
                        raise asyncio.CancelledError
            finally:
                if self.child is not None:
                    try:
                        self.child.kill()
                    except psutil.NoSuchProcess:
                        pass

    async def wait_stopped(self):
        while self.child is not None:
            if not self.child.is_running() or self.child.ppid() != os.getpid():
                raise RuntimeError('interruption_child_not_owned')
            if self.child.status() == psutil.STATUS_STOPPED:
                return
            await asyncio.sleep(.005)

    async def reaped(self):
        async with asyncio.timeout(5):
            while self.child is not None and self.child.is_running():
                await asyncio.sleep(.01)


async def interrupted_call(hook, call):
    """Fail closed if the hook misses its boundary or the operation succeeds."""
    watcher = asyncio.create_task(hook.watch())
    attempt = asyncio.create_task(call())
    try:
        done, _ = await asyncio.wait((watcher, attempt), return_when=asyncio.FIRST_COMPLETED)
        if attempt in done and not watcher.done():
            raise RuntimeError('operation_finished_before_interruption')
        observation = await watcher
        try:
            await asyncio.wait_for(attempt, hook.timeout)
        except Exception as failure:
            await hook.reaped()
            hook.audit_incomplete()
            return observation, failure
        raise RuntimeError('interruption_did_not_fail_required_work')
    finally:
        cancelled = False
        for task in (watcher, attempt):
            if not task.done():
                task.cancel()
            # Join the watcher/capture before canceling the producer of scratch.
            cancelled = await join_cleanup(task) or cancelled
        reaping = asyncio.create_task(hook.reaped())
        cancelled = await join_cleanup(reaping) or cancelled
        reaping.result()
        if cancelled:
            raise asyncio.CancelledError
