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

from .object_store import Store, digest


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
                 heartbeat=lambda detail: None):
        self.source, self.store, self.scratch = source, store, scratch
        self.heartbeat = heartbeat

    async def child(self, module, request, out):
        """One request per interpreter; S1 explores safe process reuse separately."""
        with (out/'process.log').open('wb') as log:
            process = await asyncio.create_subprocess_exec(
                sys.executable, '-m', module, stdin=asyncio.subprocess.PIPE,
                stdout=log, stderr=log, start_new_session=True)
            communication = asyncio.create_task(process.communicate(json.dumps(request).encode()))
            try:
                while not communication.done():
                    self.heartbeat({'pid': process.pid})
                    await asyncio.wait({communication}, timeout=1)
                await communication
                if process.returncode:
                    raise RuntimeError((out/'process.log').read_text()[-4000:])
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
            data = self.store.get(item['key'])
            assert digest(data) == item['sha256']
            path = out/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return manifest

    def verify_group(self, out, start, end):
        manifest = json.loads((out/'complete.json').read_text())
        assert manifest['source_sha256'] == self.source.source_sha256
        assert json.loads((out/'method.json').read_text()) == self.source.method
        assert manifest['method_sha256'] == digest((out/'method.json').read_bytes())
        pages = []
        for entry in manifest['pages']:
            path = out/'checkpoints'/entry['file']
            assert digest(path.read_bytes()) == entry['sha256']
            page = json.loads(path.read_text())
            assert page['method_sha256'] == manifest['method_sha256']
            assert page['source_sha256'] == manifest['source_sha256']
            assert digest((path.parent/page['visual']['file']).read_bytes()) == page['visual']['sha256']
            pages.append(page['page_no'])
        assert pages == list(range(start, end+1))
        return manifest

    async def produce(self, operation):
        source = self.source
        assert digest(source.pdf.read_bytes()) == source.source_sha256
        producer = {p.name: digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}
        identity = digest(json.dumps({'operation': operation, 'source': source.source_sha256,
            'source_revision': source.source_revision, 'method': source.method, 'producer': producer}, sort_keys=True).encode())
        if await asyncio.to_thread(self.store.resolve, identity):
            return identity
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
