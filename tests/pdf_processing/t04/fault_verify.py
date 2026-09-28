"""Real-service required-work barrier and ambiguous publication acceptance."""
import asyncio,json,uuid,sys
from pathlib import Path
import boto3
from datetime import timedelta
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError
from pdf_processing.object_store import Store,digest
from pdf_processing.processing_workflow import PDFProcessing

@workflow.defn(sandboxed=False)
class StageProbe:
    @workflow.run
    async def run(self,value:dict)->dict:
        try:
            return await workflow.execute_activity('pdf_processing_step_v1',value,task_queue='t04-pdf',
                start_to_close_timeout=timedelta(minutes=3),heartbeat_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(maximum_attempts=1))
        except ActivityError:
            return {'failed':True}

async def main(mode):
    client=await Client.connect('temporal:7233');s3=boto3.client('s3',endpoint_url='http://objects:9000');store=Store(s3,'t04','final')
    out=Path('/tmp/t04-evidence');out.mkdir(exist_ok=True)
    if mode=='late':
        old=json.loads((out/'component_failure.json').read_text())
        async with Worker(client,task_queue='t04-probes',workflows=[StageProbe]):
            published=await client.execute_workflow(StageProbe.run,{'stage':'component_ocr','plan':old['result']['plan'],
                'selection':old['result']['selection'],'component':'#/pictures/1'},id='late-'+uuid.uuid4().hex,task_queue='t04-probes')
        terminal=await client.get_workflow_handle(old['workflow']).query(PDFProcessing.progress)
        assert terminal==old['result'] and terminal['status']=='failed'
        assert published.get('operation')
        (out/'late.json').write_text(json.dumps({'late':published,'terminal_unchanged':True},indent=2));return
    data=Path('/tmp/t04-fixtures/multiple.pdf').read_bytes();key='final/sources/fault-'+mode+'.pdf'
    version=s3.put_object(Bucket='t04',Key=key,Body=data)['VersionId']
    request={'version':2,'completion':'required_picture_ocr_v1','profile':'native-v1','request_id':uuid.uuid4().hex,
        'source_revision':'t04-fault:'+mode,'artifact':{'key':key,'version_id':version,'sha256':digest(data),'name':'fault.pdf'}}
    handle=await client.start_workflow(PDFProcessing.run,{'request':request,'activity_queue':'t04-pdf'},id='fault-'+uuid.uuid4().hex,task_queue='t04-workflows')
    result=await handle.result();history=await handle.fetch_history()
    attempts=[e.activity_task_started_event_attributes.attempt for e in history.events if e.HasField('activity_task_started_event_attributes')]
    record={'request':request,'workflow':handle.id,'result':result,'attempts':attempts}
    (out/(mode+'.json')).write_text(json.dumps(record,indent=2))
    if mode=='component_failure':
        assert result['status']=='failed' and not result['processing_complete'] and result['registered_components']==1,result
        assert result['error']['code']=='injected_ocr_failure'
        assert not result.get('processing_result')
    else:
        assert result['status']=='complete' and max(attempts)>1,result
        assert any(s['stage']=='assembly' and s['reused'] for s in result['steps'])
        assert any(s['stage']=='component_ocr' and s['reused'] for s in result['steps'])
        async with Worker(client,task_queue='t04-probes',workflows=[StageProbe]):
            incomplete=await client.execute_workflow(StageProbe.run,{'stage':'finalize','plan':result['plan'],
                'selection':result['selection'],'outcomes':[]},id='incomplete-'+uuid.uuid4().hex,task_queue='t04-probes')
        assert incomplete=={'failed':True},incomplete
    print(mode,'passed',flush=True)

asyncio.run(main(sys.argv[1]))
