"""Versioned PDF submission and required-work retry assertions for lifecycle faults."""
import asyncio,json,sys,uuid
from pathlib import Path
import boto3
from temporalio.client import Client
from pdf_processing.object_store import Store,digest
from pdf_processing.processing_workflow import PDFProcessing

async def main():
    case=sys.argv[1]
    s3=boto3.client('s3',endpoint_url='http://objects:9000')
    data=Path('/tmp/integration-fixtures/multiple.pdf').read_bytes()
    key='final/sources/lifecycle-'+case+'.pdf'
    saved=s3.put_object(Bucket='integration',Key=key,Body=data)
    request={'version':2,'completion':'required_picture_ocr_v1','request_id':uuid.uuid4().hex,
        'profile':'native-v1','source_revision':'integration:'+case,
        'artifact':{'key':key,'version_id':saved['VersionId'],'name':'multiple.pdf','sha256':digest(data)}}
    client=await Client.connect('temporal:7233')
    handle=await client.start_workflow(PDFProcessing.run,{'request':request,'activity_queue':'integration-'+case},
        id='integration-'+case+'-'+uuid.uuid4().hex,task_queue='integration-workflows')
    result=await handle.result()
    assert result['status']=='complete' and result['processing_complete'] and not result['canonical_accepted'],result
    store=Store(s3,'integration','final')
    def read(identity,name):
        manifest=store.resolve(identity)
        return json.loads(store.read_artifact(next(f for f in manifest['files'] if f['name']==name)))
    final=read(result['processing_result'],'processing-result.json')
    assert len(final['enrichments'])>=2,final
    texts=' '.join(t for x in final['enrichments'] for t in read(x['operation'],'ocr.json')['texts'])
    assert all(t in texts for t in ('ALPHA','12345','BETA','67890')),texts
    history=await handle.fetch_history()
    attempts=[e.activity_task_started_event_attributes.attempt for e in history.events if e.HasField('activity_task_started_event_attributes')]
    assert 2 in attempts,attempts
    Path('/tmp/integration-'+case+'.json').write_text(json.dumps({'workflow_id':handle.id,'request':request,'result':result,'attempts':attempts,'final':final},indent=2))
    print(case+' recovery and complete OCR references passed',flush=True)
asyncio.run(main())
