"""Request-driven operations over shared artifacts, with fresh child processes.

No source, client, remote method or storage namespace is bound at import time.
This is the T01 seam, not the T02 ingestion workflow or canonical schema.
"""
import asyncio
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import tempfile

from .object_store import Store, StoreFailure, digest


class ChildFailure(RuntimeError):
    def __init__(self, category, code):
        super().__init__(code)
        self.category, self.code = category, code


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

    async def child(self, module, request, out):
        """One request per interpreter; S1 explores safe process reuse separately."""
        if self.child_runner is not None and module == 'pdf_processing.parse' and request.get('mode') == 'capture':
            self.observation['parser'] = await self.child_runner.run(request, out, self.heartbeat, self.child_timeout)
            return
        with (out/'process.log').open('wb') as log:
            process = await asyncio.create_subprocess_exec(
                sys.executable, '-m', module, stdin=asyncio.subprocess.PIPE,
                stdout=log, stderr=log, start_new_session=True)
            communication = asyncio.create_task(process.communicate(json.dumps(request).encode()))
            try:
                async with asyncio.timeout(self.child_timeout):
                    while not communication.done():
                        self.heartbeat({'pid': process.pid, 'durable_completion': False})
                        await asyncio.wait({communication}, timeout=1)
                    await communication
                if process.returncode:
                    failure = Path(request['out'])/'failure.json'
                    if failure.is_file():
                        detail = json.loads(failure.read_text())
                        raise ChildFailure(detail['category'], detail['code'])
                    raise RuntimeError('child_process_failed')
            finally:
                if process.returncode is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    await process.wait()
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

    def verify_group(self, out, start, end):
        try:
            manifest = json.loads((out/'complete.json').read_text())
            if (manifest['format'] != 'PROTOTYPE-document-v1' or manifest['status'] != 'success'
                    or manifest['source_sha256'] != self.source.source_sha256
                    or json.loads((out/'method.json').read_text()) != self.source.method
                    or manifest['method_sha256'] != digest((out/'method.json').read_bytes())):
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
        if await asyncio.to_thread(self.store.resolve, identity):
            self.observation = {'reused': True}
            return identity
        self.observation = {'reused': False}
        self.scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='pdf-', dir=self.scratch) as tmp:
            out = Path(tmp)
            result = out/'result'
            request = {'pdf': str(source.pdf), 'model_cache': str(source.model_cache),
                'out': str(result), 'scan': source.scan, 'expected_method': source.method}
            kind = operation['kind']
            if kind == 'group':
                await self.child('pdf_processing.parse', {**request, 'mode': 'capture',
                    'start': operation['start'], 'end': operation['end'], 'checkpoint_only': True}, out)
                self.verify_group(result, operation['start'], operation['end'])
            elif kind == 'assembly':
                merged = out/'merged'
                (merged/'checkpoints').mkdir(parents=True)
                manifest = None
                for i, group_id in enumerate(operation['groups']):
                    group = out/'inputs'/str(i)
                    await asyncio.to_thread(self.materialize, group_id, group)
                    current = json.loads((group/'complete.json').read_text())
                    if manifest is None:
                        manifest = {**current, 'pages': [], 'confidence': {**current['confidence'], 'pages': {}}}
                        (merged/'method.json').write_bytes((group/'method.json').read_bytes())
                    manifest['pages'] += current['pages']
                    manifest['confidence']['pages'].update(current['confidence']['pages'])
                    for path in (group/'checkpoints').iterdir():
                        target = merged/'checkpoints'/path.name
                        if target.exists(): raise ValueError('Duplicate checkpoint page')
                        target.write_bytes(path.read_bytes())
                (merged/'complete.json').write_text(json.dumps(manifest))
                self.verify_group(merged, operation['start'], operation['end'])
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
