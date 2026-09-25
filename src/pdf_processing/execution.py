"""Request-driven operations over shared artifacts, with fresh child processes.

No source, client, remote method or storage namespace is bound at import time.
This is the T01 seam, not the T02 ingestion workflow or canonical schema.
"""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time


LIFECYCLE_LOCK_ENV = 'PDF_PROCESS_LIFECYCLE_LOCK'
LIFECYCLE_LOCK_TIMEOUT_ENV = 'PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS'


class ProcessLifecycleSynchronizationError(RuntimeError):
    pass


@asynccontextmanager
async def process_lifecycle_transition():
    """Serialize an owned-process exit with an external process snapshot."""
    path = os.environ.get(LIFECYCLE_LOCK_ENV)
    if not path:
        yield True
        return
    import fcntl
    with open(path, 'a') as stream:
        deadline = time.monotonic() + float(
            os.environ.get(LIFECYCLE_LOCK_TIMEOUT_ENV, '1')
        )
        acquired = False
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    break
                await asyncio.sleep(.01)
        try:
            yield acquired
        finally:
            if acquired:
                fcntl.flock(stream, fcntl.LOCK_UN)


from .compatibility import CONTRACT, methods_match
from .object_store import Store, StoreFailure, digest


# Owned by this worker's event loop; fresh OCR/preflight/assembly are also children.
_fresh_children = set()


async def _stop_children(children):
    first_error = None
    for process in tuple(children):
        async with process_lifecycle_transition() as synchronized:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), 5)
            except TimeoutError as error:
                if first_error is None:
                    first_error = FreshChildReapFailure('fresh_child_reap_failed')
                    first_error.__cause__ = error
            else:
                children.discard(process)
                _fresh_children.discard(process)
        if not synchronized and first_error is None:
            first_error = ProcessLifecycleSynchronizationError(
                'process_lifecycle_lock_timeout'
            )
    if first_error is not None:
        raise first_error


async def stop_fresh_children():
    """Worker-shutdown backstop for every fresh child in this event loop."""
    await _stop_children(_fresh_children)


async def stop_owned_children(parser, reason='worker_shutdown'):
    """Settle warm and fresh cleanup before propagating the first failure."""
    tasks = []
    if parser is not None:
        tasks.append(asyncio.create_task(parser.close(reason)))
    tasks.append(asyncio.create_task(stop_fresh_children()))
    settling = asyncio.gather(*tasks, return_exceptions=True)
    cancelled = None
    try:
        results = await asyncio.shield(settling)
    except asyncio.CancelledError as error:
        cancelled = error
        results = await settling
    for result in results:
        if isinstance(result, BaseException):
            raise result
    if cancelled is not None:
        raise cancelled


class ChildFailure(RuntimeError):
    def __init__(self, category, code):
        super().__init__(code)
        self.category, self.code = category, code


class FreshChildReapFailure(RuntimeError):
    """A killed fresh child still has not produced a confirmed exit."""


@dataclass(frozen=True)
class SourceRequest:
    pdf: Path
    source_revision: str
    source_sha256: str
    method: dict
    model_cache: Path
    scan: bool = False


class Execution:
    def __init__(self, source: SourceRequest, store: Store, scratch: Path,
                 heartbeat=lambda detail: None, child_timeout=540, child_runner=None):
        self.source, self.store, self.scratch = source, store, scratch
        self.heartbeat = heartbeat
        self.child_timeout = child_timeout
        self.observation = {}
        self.child_runner = child_runner
        self.fresh_children = set()

    async def child(self, module, request, out):
        """Reuse one parser for native capture and checkpoint restoration."""
        warm_parse = (
            self.child_runner is not None
            and module == 'pdf_processing.parse'
            and (
                request.get('mode') == 'capture'
                or (request.get('mode') == 'restore' and not request.get('scan', False))
            )
        )
        if warm_parse:
            self.observation['parser'] = await self.child_runner.run(request, out, self.heartbeat, self.child_timeout)
            return
        if self.child_runner is not None and module == 'pdf_processing.parse' and request.get('mode') == 'restore':
            # The runner owns serialization across every profile queue. Keep
            # that ownership until the fresh process has exited, not merely
            # until the previous warm process has been reaped.
            async with self.child_runner.fresh_child_handoff() as observation:
                self.observation['parser_handoff'] = observation
                try:
                    await self.fresh_child(module, request, out)
                except FreshChildReapFailure:
                    # Still inside the shared handoff lock: prevent a later
                    # profile queue from rebuilding warm capacity around an
                    # owned fresh process whose exit was not confirmed.
                    self.child_runner.fail_closed('fresh_child_reap_failed')
                    raise
            return
        await self.fresh_child(module, request, out)

    async def fresh_child(self, module, request, out):
        with (out/'process.log').open('wb') as log:
            lifecycle = os.environ.get(LIFECYCLE_LOCK_ENV)
            control_parent = control_child = None
            command = [sys.executable, '-m', module]
            options = {}
            cancelled = None
            async with process_lifecycle_transition() as synchronized:
                if not synchronized:
                    raise ProcessLifecycleSynchronizationError(
                        'process_lifecycle_lock_timeout'
                    )
                if lifecycle:
                    import socket
                    control_parent, control_child = socket.socketpair()
                    control_parent.setblocking(False)
                    command = [sys.executable, '-m', 'pdf_processing.lifecycle_child', module]
                    options = {
                        'env': {**os.environ, 'PDF_PROCESS_LIFECYCLE_FD': str(control_child.fileno())},
                        'pass_fds': (control_child.fileno(),),
                    }
                spawning = asyncio.create_task(asyncio.create_subprocess_exec(
                    *command, stdin=asyncio.subprocess.PIPE, stdout=log, stderr=log,
                    start_new_session=True, **options))
                try:
                    process = await asyncio.shield(spawning)
                except asyncio.CancelledError as error:
                    try:
                        process = await asyncio.shield(spawning)
                    except asyncio.CancelledError:
                        spawning.cancel()
                        await asyncio.gather(spawning, return_exceptions=True)
                        if spawning.cancelled():
                            if control_parent is not None:
                                control_parent.close()
                            raise
                        try:
                            process = spawning.result()
                        except BaseException:
                            if control_parent is not None:
                                control_parent.close()
                            raise
                    except BaseException:
                        if control_parent is not None:
                            control_parent.close()
                        raise
                    cancelled = error
                except BaseException:
                    if control_parent is not None:
                        control_parent.close()
                    raise
                finally:
                    if control_child is not None:
                        control_child.close()
                self.fresh_children.add(process)
                _fresh_children.add(process)
            if cancelled is not None:
                if control_parent is not None:
                    control_parent.close()
                await _stop_children(self.fresh_children)
                raise cancelled
            communication = asyncio.create_task(process.communicate(json.dumps(request).encode()))
            ready = None
            group_cleanup_done = False
            try:
                async with asyncio.timeout(self.child_timeout):
                    if control_parent is not None:
                        ready = asyncio.create_task(
                            asyncio.get_running_loop().sock_recv(control_parent, 1)
                        )
                    while not communication.done() and not (ready and ready.done()):
                        self.heartbeat({'pid': process.pid, 'durable_completion': False})
                        await asyncio.wait(
                            {communication, *(() if ready is None else (ready,))}, timeout=1,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                    if ready is not None and ready.done() and ready.result() == b'1':
                        async with process_lifecycle_transition() as synchronized:
                            await asyncio.get_running_loop().sock_sendall(control_parent, b'1')
                            await communication
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            group_cleanup_done = True
                        if not synchronized:
                            raise ProcessLifecycleSynchronizationError(
                                'process_lifecycle_lock_timeout'
                            )
                    else:
                        await communication
                if process.returncode:
                    failure = Path(request['out'])/'failure.json'
                    if failure.is_file():
                        detail = json.loads(failure.read_text())
                        raise ChildFailure(detail['category'], detail['code'])
                    raise RuntimeError('child_process_failed')
            finally:
                try:
                    primary_active = sys.exc_info()[0] is not None
                    synchronized = True
                    if not group_cleanup_done:
                        async with process_lifecycle_transition() as synchronized:
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                            if process.returncode is None:
                                try:
                                    await asyncio.wait_for(process.wait(), 5)
                                except TimeoutError as error:
                                    # Retain ownership for worker-shutdown cleanup. Callers
                                    # that coordinate warm capacity must fail closed before
                                    # releasing their handoff lock.
                                    raise FreshChildReapFailure(
                                        'fresh_child_reap_failed'
                                    ) from error
                    if process.returncode is not None:
                        self.fresh_children.discard(process)
                        _fresh_children.discard(process)
                    if not synchronized and not primary_active:
                        raise ProcessLifecycleSynchronizationError(
                            'process_lifecycle_lock_timeout'
                        )
                finally:
                    if control_parent is not None:
                        control_parent.close()
                    if ready is not None and not ready.done():
                        ready.cancel()
                        await asyncio.gather(ready, return_exceptions=True)
                    if not communication.done():
                        communication.cancel()
                        await asyncio.gather(communication, return_exceptions=True)

    def materialize(self, operation, out):
        manifest = self.store.resolve(operation)
        if manifest is None:
            raise ValueError('Required input operation has not been registered')
        for item in manifest['files']:
            name = item['name']
            if name.startswith('/') or '..' in name.split('/'):
                raise ValueError('Invalid artifact path')
            data = self.store.read_artifact(item)
            path = out/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return manifest

    def verify_group(self, out, start, end, compatibility=None):
        try:
            manifest = json.loads((out/'complete.json').read_text())
            if (manifest['format'] != 'PROTOTYPE-document-v1' or manifest['status'] != 'success'
                    or manifest['source_sha256'] != self.source.source_sha256
                    or not methods_match(json.loads((out/'method.json').read_text()), self.source.method, compatibility is not None)
                    or manifest['method_sha256'] != digest((out/'method.json').read_bytes())):
                raise ValueError()
            if compatibility is not None and json.loads((out/'compatibility.json').read_text()) != compatibility:
                raise ValueError()
            pages, evidence = [], set()
            for entry in manifest['pages']:
                if Path(entry['file']).name != entry['file']:
                    raise ValueError()
                path = out/'checkpoints'/entry['file']
                if digest(path.read_bytes()) != entry['sha256']:
                    raise ValueError()
                page = json.loads(path.read_text())
                visual = page['visual']['file']
                if (page['format'] != 'PROTOTYPE-page-v1'
                        or page['method_sha256'] != manifest['method_sha256']
                        or page['source_sha256'] != manifest['source_sha256']
                        or Path(visual).name != visual or visual in evidence
                        or digest((path.parent/visual).read_bytes()) != page['visual']['sha256']
                        or set(page['assembled']) != {'elements', 'headers', 'body'}
                        or any(not isinstance(v, list) for v in page['assembled'].values())
                        or page['size']['width'] <= 0 or page['size']['height'] <= 0):
                    raise ValueError()
                evidence.add(visual)
                pages.append(page['page_no'])
            if pages != list(range(start, end+1)):
                raise ValueError()
            return manifest
        except (ValueError, KeyError, TypeError, OSError):
            raise StoreFailure('integrity', 'checkpoint_coverage_invalid') from None

    async def produce(self, operation):
        source = self.source
        assert digest(source.pdf.read_bytes()) == source.source_sha256
        producer = {p.name: digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}
        identity = digest(json.dumps({'operation': operation, 'source': source.source_sha256,
            'source_revision': source.source_revision, 'method': source.method, 'producer': producer}, sort_keys=True).encode())
        scoped = operation.get('contract') == CONTRACT
        checkpoint = operation['dependencies']['checkpoint'] if scoped else None
        if scoped:
            identity = digest(json.dumps(operation, sort_keys=True).encode())
        if await asyncio.to_thread(self.store.resolve, identity):
            if scoped:
                with tempfile.TemporaryDirectory(prefix='reuse-', dir=self.scratch) as tmp:
                    saved = Path(tmp)
                    await asyncio.to_thread(self.materialize, identity, saved)
                    attribution = json.loads((saved/'attribution.json').read_text())
                    if (attribution['operation'] != operation or attribution['source_revision'] != source.source_revision
                            or attribution['source_sha256'] != source.source_sha256):
                        raise StoreFailure('integrity', 'reuse_attribution_mismatch')
                    if operation['kind'] == 'group':
                        self.verify_group(saved, operation['start'], operation['end'], checkpoint)
                    elif (json.loads((saved/'compatibility.json').read_text()) != checkpoint
                          or not methods_match(json.loads((saved/'method.json').read_text()), source.method, True)):
                        raise StoreFailure('integrity', 'reuse_method_mismatch')
            self.observation = {'reused': True}
            return identity
        self.observation = {'reused': False}
        self.scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='pdf-', dir=self.scratch) as tmp:
            out = Path(tmp)
            result = out/'result'
            request = {'pdf': str(source.pdf), 'model_cache': str(source.model_cache),
                'out': str(result), 'scan': source.scan, 'expected_method': source.method,
                'checkpoint_compatibility': checkpoint}
            kind = operation['kind']
            if kind == 'group':
                await self.child('pdf_processing.parse', {**request, 'mode': 'capture',
                    'start': operation['start'], 'end': operation['end'], 'checkpoint_only': True}, out)
                self.verify_group(result, operation['start'], operation['end'], checkpoint)
            elif kind == 'assembly':
                merged = out/'merged'
                (merged/'checkpoints').mkdir(parents=True)
                manifest = None
                for i, group_id in enumerate(operation['groups']):
                    group = out/'inputs'/str(i)
                    await asyncio.to_thread(self.materialize, group_id, group)
                    current = json.loads((group/'complete.json').read_text())
                    numbers = [json.loads((group/'checkpoints'/p['file']).read_text())['page_no'] for p in current['pages']]
                    self.verify_group(group, min(numbers), max(numbers), checkpoint)
                    if manifest is None:
                        manifest = {**current, 'pages': [], 'confidence': {**current['confidence'], 'pages': {}}}
                        (merged/'method.json').write_bytes((group/'method.json').read_bytes())
                        if checkpoint is not None:
                            (merged/'compatibility.json').write_text(json.dumps(checkpoint))
                    manifest['confidence']['pages'].update(current['confidence']['pages'])
                    for path in (group/'checkpoints').iterdir():
                        target = merged/'checkpoints'/path.name
                        if target.exists(): raise ValueError('Duplicate checkpoint page')
                        raw = path.read_bytes()
                        if path.suffix == '.json' and current['method_sha256'] != manifest['method_sha256']:
                            # Each original was verified above. Normalize only the transient
                            # merge envelope; immutable originals retain full environment hashes.
                            page = json.loads(raw)
                            page['method_sha256'] = manifest['method_sha256']
                            raw = json.dumps(page, sort_keys=True).encode()
                        target.write_bytes(raw)
                    manifest['pages'] += [{**entry, 'sha256': digest((merged/'checkpoints'/entry['file']).read_bytes())}
                                          for entry in current['pages']]
                (merged/'complete.json').write_text(json.dumps(manifest))
                self.verify_group(merged, operation['start'], operation['end'], checkpoint)
                await self.child('pdf_processing.parse', {**request, 'mode': 'restore',
                    'checkpoint': str(merged), 'start': operation['start'], 'end': operation['end']}, out)
                try:
                    document = json.loads((result/'document.json').read_text())
                    if sorted(int(n) for n in document['pages']) != list(range(operation['start'], operation['end']+1)):
                        raise ValueError()
                except (ValueError, KeyError, TypeError, OSError):
                    raise StoreFailure('integrity', 'assembly_coverage_invalid') from None
            elif kind == 'ocr':
                parsed = out/'parsed'
                await asyncio.to_thread(self.materialize, operation['parsed'], parsed)
                await self.child('pdf_processing.ocr', {'parsed': str(parsed/'document.json'),
                    'pdf': str(source.pdf), 'out': str(result), 'component': operation['component']}, out)
            else:
                raise ValueError('Unsupported operation kind')
            files = {str(p.relative_to(result)): p.read_bytes() for p in result.rglob('*') if p.is_file()}
            files['attribution.json'] = json.dumps({'source_revision': source.source_revision,
                'source_sha256': source.source_sha256, 'method': source.method,
                'producer': producer, 'operation': operation}, sort_keys=True).encode()
            publication = asyncio.create_task(asyncio.to_thread(self.store.publish, identity, files))
            while not publication.done():
                self.heartbeat({'operation': identity, 'stage': 'publication'})
                await asyncio.wait({publication}, timeout=1)
            await publication
            return identity
