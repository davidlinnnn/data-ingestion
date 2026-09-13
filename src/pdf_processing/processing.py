"""Versioned request -> registered internal parsed result.

The object-store adapter is the only persistence implementation. Profiles are
operator-published immutable files, not arbitrary options supplied by callers.
"""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time
from typing import NoReturn

from temporalio import activity
from temporalio.exceptions import ApplicationError

from .execution import ChildFailure, Execution, SourceRequest
from .object_store import digest


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def observed():
    return datetime.now(timezone.utc).isoformat()


def reject(code, category='input') -> NoReturn:
    raise ApplicationError(code, {'category': category, 'code': code},
                           type=category, non_retryable=category in ('input', 'integrity', 'method'))


class Processing:
    def __init__(self, store, scratch, model_cache, profile, limits=None, child_runner=None):
        self.store, self.scratch = store, Path(scratch)
        self.child_runner = child_runner
        self.model_cache, self.profile = Path(model_cache), profile
        self.limits = limits or {'max_bytes': 100*1024*1024, 'max_pages': 100,
            'max_page_pixels': 20_000_000, 'preflight_seconds': 30, 'child_seconds': 540}
        if any(type(v) is not int or v <= 0 for v in self.limits.values()):
            raise ValueError('All provisional limits must be positive integers')
        if profile['id'] != 'native-v1' or profile['method']['options']['do_ocr'] is not False:
            raise ValueError('T02 only supports the pinned native-v1 profile without parsing OCR')
        self.producer = {p.name: digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}
        self.scratch.mkdir(parents=True, exist_ok=True)

    def read_source(self, request, path):
        ref = request['artifact']
        started = time.monotonic()
        try:
            response = self.store.client.get_object(Bucket=self.store.bucket,
                Key=ref['key'], VersionId=ref['version_id'])
            body = response['Body']
            try:
                if response['ContentLength'] > self.limits['max_bytes']:
                    reject('byte_limit')
                data = body.read(self.limits['max_bytes']+1)
            finally:
                body.close()
        except ApplicationError:
            raise
        except Exception as error:
            code = getattr(error, 'response', {}).get('Error', {}).get('Code')
            if code in ('NoSuchKey', 'NoSuchVersion', '404'):
                reject('source_missing')
            raise
        if len(data) > self.limits['max_bytes']:
            reject('byte_limit')
        if digest(data) != ref['sha256']:
            reject('digest_mismatch')
        path.write_bytes(data)
        with self.store.lock:
            self.store.io['get_bytes'] += len(data)
            self.store.io['get_seconds'] += time.monotonic()-started
        return len(data)

    def load_plan(self, identity):
        registration = self.store.resolve(identity)
        if registration is None:
            reject('plan_missing', 'integrity')
        files = [item for item in registration['files'] if item['name'] == 'plan.json']
        if len(files) != 1:
            reject('plan_invalid', 'integrity')
        plan = json.loads(self.store.get(files[0]['key']))
        if plan['profile'] != self.profile or plan['producer'] != self.producer or plan['limits'] != self.limits:
            reject('worker_method_mismatch', 'method')
        return plan

    def validate_request(self, request):
        try:
            if request['version'] != 1 or request['profile'] != self.profile['id']:
                reject('invalid_request')
            for key in ('request_id', 'source_revision'):
                if not isinstance(request[key], str) or not 0 < len(request[key]) <= 256:
                    reject('invalid_request')
            ref = request['artifact']
            if not all(isinstance(ref[k], str) and ref[k] for k in ('key', 'version_id', 'sha256', 'name')):
                reject('invalid_request')
            if ref['version_id'] == 'null' or not ref['key'].startswith(self.store.prefix+'sources/'):
                reject('invalid_source_reference')
            if len(ref['sha256']) != 64 or any(c not in '0123456789abcdef' for c in ref['sha256']):
                reject('invalid_request')
            if Path(ref['name']).name != ref['name'] or not ref['name'].lower().endswith('.pdf'):
                reject('invalid_request')
            if len(encoded(request)) > 8192:
                reject('invalid_request')
        except (KeyError, TypeError, AttributeError):
            reject('invalid_request')

    async def prepare(self, request):
        self.validate_request(request)
        identity = 'pdf-plan-v1:' + digest(encoded(request['request_id']))
        prior = await asyncio.to_thread(self.store.resolve, identity)
        if prior:
            plan = await asyncio.to_thread(self.load_plan, identity)
            if plan['request'] != request:
                reject('request_identity_conflict')
            return {'plan': identity, 'pages': plan['pages'], 'groups': plan['groups'], 'observed_at': observed()}
        with tempfile.TemporaryDirectory(prefix='preflight-', dir=self.scratch) as tmp:
            root = Path(tmp)
            pdf = root/request['artifact']['name']
            size = await asyncio.to_thread(self.read_source, request, pdf)
            dummy = SourceRequest(pdf, request['source_revision'], request['artifact']['sha256'],
                                  self.profile['method'], self.model_cache)
            execution = Execution(dummy, self.store, root, activity.heartbeat, self.limits['preflight_seconds'])
            await execution.child('pdf_processing.preflight', {'pdf': str(pdf), 'out': str(root/'inspection.json'),
                'max_pages': self.limits['max_pages'], 'max_page_pixels': self.limits['max_page_pixels'],
                'render_scale': 1}, root)
            inspection = json.loads((root/'inspection.json').read_text())
            if 'error' in inspection:
                reject(inspection['error'])
            pages = inspection['pages']
            plan = {'version': 1, 'request': request, 'profile': self.profile,
                'producer_contract': 'pdf-operation-v1', 'checkpoint_format': 'PROTOTYPE-page-v1',
                'pages': pages, 'page_sizes': inspection['page_sizes'], 'source_bytes': size,
                'groups': [[n, min(n+4, pages)] for n in range(1, pages+1, 5)],
                'limits': self.limits, 'producer': self.producer, 'created_at': observed()}
            await asyncio.to_thread(self.store.publish, identity, {'plan.json': encoded(plan)})
            accepted = await asyncio.to_thread(self.load_plan, identity)
            if accepted['request'] != request:
                reject('request_identity_conflict')
            return {'plan': identity, 'pages': accepted['pages'], 'groups': accepted['groups'], 'observed_at': observed()}

    async def execute(self, value):
        started = time.monotonic()
        before = dict(self.store.io)
        plan = await asyncio.to_thread(self.load_plan, value['plan'])
        operation = value['operation']
        if operation['kind'] == 'group':
            if [operation['start'], operation['end']] not in plan['groups']:
                reject('operation_outside_plan', 'integrity')
        elif operation['kind'] == 'assembly':
            if operation['start'] != 1 or operation['end'] != plan['pages'] or len(operation['groups']) != len(plan['groups']):
                reject('operation_outside_plan', 'integrity')
        else:
            reject('unsupported_stage')
        with tempfile.TemporaryDirectory(prefix='activity-', dir=self.scratch) as tmp:
            root = Path(tmp)
            request = plan['request']
            pdf = root/request['artifact']['name']
            await asyncio.to_thread(self.read_source, request, pdf)
            source = SourceRequest(pdf, request['source_revision'], request['artifact']['sha256'],
                                   plan['profile']['method'], self.model_cache)
            execution = Execution(source, self.store, root, activity.heartbeat, plan['limits']['child_seconds'], child_runner=self.child_runner)
            contract = {**operation, 'contract': 'pdf-operation-v1', 'plan': value['plan'],
                'dependencies': {'source': request['artifact'], 'profile': digest(encoded(plan['profile'])),
                                 'groups': operation.get('groups', [])}}
            identity = await execution.produce(contract)
            result = {'operation': identity, 'stage': operation['kind'], 'reused': execution.observation['reused'],
                'observed_at': observed()}
            if 'parser' in execution.observation:
                result['parser'] = execution.observation['parser']
            if operation['kind'] == 'assembly':
                # Full reconstruction is not enrichment completion or canonical acceptance.
                delivered = root/'delivered'
                await asyncio.to_thread(execution.materialize, identity, delivered)
                document = json.loads((delivered/'document.json').read_text())
                if sorted(int(n) for n in document['pages']) != list(range(1,plan['pages']+1)):
                    reject('incomplete_page_coverage', 'integrity')
                manifest = {'version': 1, 'status': 'parsed_ready', 'processing_complete': False,
                    'canonical_accepted': False, 'plan': value['plan'], 'source': request,
                    'profile': digest(encoded(plan['profile'])), 'pages': plan['pages'],
                    'page_groups': operation['groups'], 'assembly': identity,
                    'evidence_contract': 'Each group registration includes hashed page JSON and page image; assembly includes Docling document JSON and Markdown.',
                    'created_at': observed()}
                result_id = 'pdf-parsed-v1:'+identity
                await asyncio.to_thread(self.store.publish, result_id, {'parsed-result.json': encoded(manifest)})
                result['parsed_result'] = result_id
            result.update(seconds=time.monotonic()-started, observed_at=observed(),
                          storage={key: self.store.io[key]-before[key] for key in before})
            return result

    @activity.defn(name='pdf_processing_step_v1')
    async def run(self, value):
        async def beat():
            while True:
                activity.heartbeat({'stage': value['stage'], 'durable_completion': False})
                await asyncio.sleep(2)
        heartbeat = asyncio.create_task(beat())
        try:
            if value['stage'] == 'prepare':
                return await self.prepare(value['request'])
            return await self.execute(value)
        except ApplicationError:
            raise
        except ChildFailure as error:
            reject(error.code, error.category)
        except AssertionError:
            reject('artifact_or_method_validation_failed', 'integrity')
        except TimeoutError:
            raise ApplicationError('child_deadline', {'category': 'parser', 'code': 'child_deadline'}, type='parser')
        except Exception as error:
            code = 'storage_unavailable' if hasattr(error, 'response') or type(error).__module__.startswith('botocore') else 'execution_failed'
            category = 'storage' if code == 'storage_unavailable' else 'parser'
            raise ApplicationError(code, {'category': category, 'code': code}, type=category) from None
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
