"""Real Temporal + S3 acceptance against separately deployed workers."""
import argparse
import asyncio
import json
from pathlib import Path
import uuid

import boto3
from temporalio.client import Client
from pdf_processing.object_store import Store, digest
from pdf_processing.processing_workflow import PDFProcessing


async def main(args):
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    client = await Client.connect(args.temporal)
    s3 = boto3.client('s3', endpoint_url=args.endpoint)
    if args.mode == 'setup':
        if not any(b['Name'] == args.bucket for b in s3.list_buckets()['Buckets']):
            s3.create_bucket(Bucket=args.bucket)
        s3.put_bucket_versioning(Bucket=args.bucket, VersioningConfiguration={'Status':'Enabled'})
        sources = {}
        paths = list(Path(args.fixtures).glob('*.pdf'))
        paths.append(Path('/experiment/fixtures/llm-survey-2303.18223v1.pdf'))
        for path in paths:
            data = path.read_bytes(); key = args.prefix+'/sources/'+path.name
            result = s3.put_object(Bucket=args.bucket, Key=key, Body=data)
            sources[path.name] = {'version': 1, 'request_id': 't02:'+path.name, 'profile':'native-v1',
                'source_revision': 'captured:'+path.name+':v1',
                'artifact': {'key':key,'name':path.name,'version_id':result['VersionId'],'sha256':digest(data)}}
        (out/'requests.json').write_text(json.dumps(sources,indent=2))
        print('Uploaded immutable versioned fixtures'); return
    sources = json.loads((out/'requests.json').read_text())
    async def run(request, suffix=''):
        handle = await client.start_workflow(PDFProcessing.run,
            {'request':request,'activity_queue':'' if suffix=='-missing-queue' else args.activity_queue},
            id='t02-'+uuid.uuid4().hex+suffix, task_queue=args.workflow_queue)
        result = await handle.result()
        assert await handle.query(PDFProcessing.progress) == result, 'Query disagrees with terminal result'
        assert result['observed_at']
        if suffix == '-mismatch':
            history = await handle.fetch_history()
            starts = [event.activity_task_started_event_attributes.attempt for event in history.events if event.HasField('activity_task_started_event_attributes')]
            assert starts and max(starts)==1, starts
        return result
    if args.mode == 'mismatch':
        request = {**sources['native-review.pdf'], 'request_id': 't02:runtime-mismatch'}
        result = await run(request, '-mismatch')
        assert result['status']=='failed' and result['registered_pages']==0, result
        assert result['error']=={'category':'method','code':'worker_method_mismatch'}, result
        (out/'mismatch.json').write_text(json.dumps(result,indent=2)); print('Method mismatch permanently rejected'); return
    if args.mode == 'invalid':
        cases = [('invalid_request', {'version':99}),
            ('invalid_pdf',sources['invalid.pdf']),('password_required',sources['password.pdf']),
            ('page_limit',sources['too-many-pages.pdf']),('pixel_limit',sources['too-many-pixels.pdf']),
            ('byte_limit',sources['too-many-bytes.pdf'])]
        mismatch = json.loads(json.dumps(sources['native-review.pdf']))
        mismatch['request_id'] += '-mismatch'; mismatch['artifact']['sha256'] = '0'*64
        cases.append(('digest_mismatch', mismatch))
        missing = json.loads(json.dumps(sources['native-review.pdf']))
        missing['request_id'] += '-missing'; missing['artifact']['key'] += '-missing'
        cases.append(('source_missing', missing))
        no_queue = await run({'version':1}, '-missing-queue')
        assert no_queue['error']=={'category':'input','code':'invalid_activity_queue'}, no_queue
        results = [no_queue]
        for code, request in cases:
            result = await run(request)
            assert result['status']=='failed' and result['registered_pages']==0, result
            assert result['error']=={'category':'input','code':code}, result
            results.append(result)
        (out/'invalid.json').write_text(json.dumps(results,indent=2)); print('Invalid cases passed'); return
    store = Store(s3,args.bucket,args.prefix)
    def read(key):
        data = store.get(key)
        assert data is not None, 'Referenced artifact is absent'
        return data
    results = {}
    for name in ('native-review.pdf','llm-survey-2303.18223v1.pdf'):
        result = await run(sources[name])
        assert result['status']=='parsed_ready' and not result['processing_complete'] and not result['canonical_accepted'], result
        assert result['registered_pages'] == (3 if name=='native-review.pdf' else 51), result
        manifest = store.resolve(result['parsed_result'])
        assert manifest is not None
        item = next(i for i in manifest['files'] if i['name']=='parsed-result.json')
        delivery = json.loads(read(item['key']))
        assert delivery['pages']==result['registered_pages'] and len(delivery['page_groups'])==(1 if name=='native-review.pdf' else 11)
        assembly = store.resolve(delivery['assembly'])
        assert assembly is not None
        metrics = json.loads(read(next(i['key'] for i in assembly['files'] if i['name']=='metrics.json')))
        assert not any(v for k,v in metrics['page_stage_inputs'].items() if k.endswith('Model')), metrics
        document_bytes = read(next(i['key'] for i in assembly['files'] if i['name']=='document.json'))
        document = json.loads(document_bytes)
        if name=='llm-survey-2303.18223v1.pdf':
            assert digest(document_bytes)=='fd45828175ad659df5b25d90a6c463adc43ddc8c813737d98e1ae6f583d71aab', 'Historical native document changed'
        if name=='native-review.pdf':
            texts = ' '.join(t.get('text','') for t in document['texts'])
            for n in range(1,4): assert f'T02 native contract fixture page {n}' in texts
        if args.mode=='reuse':
            assert all(step['reused'] and step['storage']['put_bytes']==0 for step in result['steps']), result
            previous = json.loads((out/'native.json').read_text())[name]
            assert result['parsed_result']==previous['parsed_result']
        results[name]=result
    if args.mode=='native':
        conflicting = json.loads(json.dumps(sources['native-review.pdf']))
        conflicting['source_revision'] += ':changed'
        conflict = await run(conflicting)
        assert conflict['error']['code']=='request_identity_conflict', conflict
    (out/(args.mode+'.json')).write_text(json.dumps(results,indent=2)); print(json.dumps(results,indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('temporal','workflow-queue','activity-queue','endpoint','bucket','prefix','out','fixtures'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--mode',choices=['setup','invalid','native','reuse','mismatch'],required=True)
    asyncio.run(main(parser.parse_args()))
