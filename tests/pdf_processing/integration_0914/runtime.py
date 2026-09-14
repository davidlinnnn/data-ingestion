"""Bounded combined-producer regression; no rollout or resource qualification."""
import asyncio
from contextlib import AsyncExitStack
import json
from pathlib import Path
import uuid

import boto3
from temporalio.client import Client
from temporalio.worker import Worker
from pdf_processing.object_store import Store, digest
from pdf_processing.processing import Processing
from pdf_processing.rollout_workflow import PDFRolloutProcessing
from pdf_processing.routed_activity import RoutedActivity
from pdf_processing.routing import STAGES, release, release_binding, submission
from pdf_processing.evidence import top_left, overlap

IMAGE = 'docker.io/library/pdf-t08-runtime@sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0'

async def main():
    client = await Client.connect('temporal:7233')
    s3 = boto3.client('s3', endpoint_url='http://objects:9000')
    store = Store(s3, 't08', 'integration-0914')
    profile = json.loads(Path('/check/profile.json').read_text())
    processing = Processing(store, '/scratch', '/experiment/PROTOTYPE-wipe-me/hf', profile)
    route = release(release_binding(profile, processing.producer, processing.limits,
        store.bucket, store.prefix), {s: IMAGE for s in ('workflow', *STAGES)}, 'integration-0914')
    raw = Path('/fixtures/multiple.pdf').read_bytes()
    key = store.prefix+'sources/'+uuid.uuid4().hex+'.pdf'
    saved = s3.put_object(Bucket=store.bucket, Key=key, Body=raw)
    request = {'version': 3, 'completion': 'required_evidence_v1', 'profile': 'native-v1',
        'request_id': 'integration-0914-'+uuid.uuid4().hex,
        'source_revision': 'synthetic:integration-0914:multiple',
        'artifact': {'key': key, 'name': 'multiple.pdf', 'sha256': digest(raw), 'version_id': saved['VersionId']}}
    def read(identity, name):
        return json.loads(store.read_artifact(next(f for f in store.resolve(identity)['files'] if f['name']==name)))
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(Worker(client, task_queue=route['queues']['workflow'], workflows=[PDFRolloutProcessing]))
        for stage in STAGES:
            adapter = RoutedActivity(processing, route, stage, route['queues'][stage], IMAGE)
            await stack.enter_async_context(Worker(client, task_queue=route['queues'][stage], activities=[adapter.run], max_concurrent_activities=1))
        payload = submission(request, route['id'], {route['id']: route})
        handle = await client.start_workflow(PDFRolloutProcessing.run, payload, id=request['request_id'], task_queue=route['queues']['workflow'])
        result = await asyncio.wait_for(handle.result(), 600)
        assert result['status']=='complete' and result['processing_complete'], result
        final = read(result['processing_result'], 'processing-result.json')
        assert final['processing_complete'] and not final['canonical_accepted']
        assert final['source']==payload['request'] and final['provenance']['producer']==processing.producer
        evidence = read(final['content_evidence'], 'content-evidence.json')
        assert evidence and len(final['enrichments'])==2
        for outcome in final['enrichments']:
            report = read(outcome['operation'], 'ocr.json')
            assert report['source']==payload['request'] and report['render_scale']==3
        history = await handle.fetch_history()
        scheduled = [e.activity_task_scheduled_event_attributes for e in history.events if e.HasField('activity_task_scheduled_event_attributes')]
        assert len(scheduled)==7
        assert {a.task_queue.name for a in scheduled}=={route['queues'][s] for s in STAGES}
        assert all(a.activity_type.name=='pdf_processing_routed_step_v1' for a in scheduled)
        negatives = {}
        for name, value in [('missing', {'request': request}), ('malformed', {**payload, 'request': []})]:
            answer = await client.execute_workflow(PDFRolloutProcessing.run, value, id='integration-negative-'+uuid.uuid4().hex, task_queue=route['queues']['workflow'])
            assert answer['status']=='failed' and answer['error']['code']=='invalid_routing'
            negatives[name] = answer
        try:
            RoutedActivity(processing, route, 'group', 'latest', IMAGE)
        except ValueError as error:
            assert str(error)=='worker_routing_mismatch'
        else:
            raise AssertionError('Mismatched queue accepted')
        Path('/tmp/integration-result.json').write_text(json.dumps({'request': payload['request'], 'route': route,
            'producer': processing.producer, 'result': result, 'required_ocr_count': len(final['enrichments']),
            'activities': [{'type': a.activity_type.name, 'queue': a.task_queue.name} for a in scheduled],
            'negatives': negatives, 'scope': 'Single Pod, fresh child execution; not multi-Pod rollout or resource qualification'}, indent=2))
    # Geometry validation does not turn zero-area parser lines into overlap evidence.
    line={'l':2,'t':3,'r':2,'b':8,'coord_origin':'TOPLEFT'}
    assert top_left(line,10,10,allow_zero_width=True)==[2,3,2,8]
    assert overlap([2,3,2,8],[0,0,10,10])==0
    for box in (line, {**line,'r':1}, {**line,'l':-1,'r':-1}, {**line,'b':3}):
        try: top_left(box,10,10,allow_zero_width=box!=line)
        except ValueError: pass
        else: raise AssertionError('Invalid geometry accepted')
    print('PASS: combined producer, seven routed Activities, required OCR/evidence completion, routing negatives, geometry boundaries', flush=True)

if __name__=='__main__': asyncio.run(main())
