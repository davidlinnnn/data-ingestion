"""Submit an independent native lifecycle case through the real versioned seam."""
import asyncio,json,sys,uuid
from pathlib import Path
import boto3
from temporalio.client import Client
from pdf_processing.processing_workflow import PDFProcessing
from pdf_processing.object_store import Store

async def main(name):
    filename='llm-survey-2303.18223v1.pdf' if name.startswith(('pod','drain')) else 'native-review.pdf'
    source=json.loads(Path('/tmp/t05-run/requests.json').read_text())[filename]
    source['request_id']='t05:'+name
    client=await Client.connect('temporal:7233')
    handle=await client.start_workflow(PDFProcessing.run,{'request':source,'activity_queue':sys.argv[2] if len(sys.argv)>2 else 't05-pdf'},id='t05-'+name,task_queue='t05-workflows')
    result=await handle.result()
    history=await handle.fetch_history()
    attempts=[e.activity_task_started_event_attributes.attempt for e in history.events if e.HasField('activity_task_started_event_attributes')]
    identities=[e.activity_task_started_event_attributes.identity for e in history.events if e.HasField('activity_task_started_event_attributes')]
    if name.startswith('pod'):
        assert max(attempts)>=2 and len(set(identities))>=2, (attempts,identities)
    if name.startswith('drain'):
        assert max(attempts)==1 and len(set(identities))>=2, (attempts,identities)
    store=Store(boto3.client('s3',endpoint_url='http://objects:9000'),'t05',source['artifact']['key'].split('/sources/')[0])
    if name.startswith('exhaust'):
        assert result['status']=='failed' and result['error']['category']=='parser',result
        assert max(attempts)==3,attempts
        Path('/tmp/t05-run/'+name+'.json').write_text(json.dumps({'result':result,'attempts':attempts},indent=2))
        print(json.dumps({'case':name,'attempts':attempts,'result':'failed'})); return
    assert result['status']=='parsed_ready',result
    def document(result):
        manifest=store.resolve(result['steps'][-1]['operation'])
        return json.loads(store.get(next(f['key'] for f in manifest['files'] if f['name']=='document.json')))
    baseline=json.loads(Path('/tmp/t05-run/native.json').read_text())[filename]
    assert document(result)==document(baseline),'Native output changed after lifecycle event'
    Path('/tmp/t05-run/'+name+'.json').write_text(json.dumps({'result':result,'attempts':attempts,'worker_identities':[e.activity_task_started_event_attributes.identity for e in history.events if e.HasField('activity_task_started_event_attributes')],'equal_baseline':True},indent=2))
    print(json.dumps({'case':name,'attempts':attempts,'result':result['status']}))
asyncio.run(main(sys.argv[1]))
