"""Real MinIO second-read loss at production enrichment, through real Temporal."""
import asyncio,json,uuid
from pathlib import Path
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
with workflow.unsafe.imports_passed_through():
    import boto3
    from temporalio.client import Client
    from temporalio.worker import Worker
    from temporalio.exceptions import ActivityError
    from pdf_processing.object_store import Store
    from pdf_processing.processing import Processing

@workflow.defn
class SecondRead:
    @workflow.run
    async def run(self, value: dict):
        try:
            await workflow.execute_activity('pdf_processing_step_v1',value,
                start_to_close_timeout=timedelta(seconds=30),retry_policy=RetryPolicy(maximum_attempts=3))
        except ActivityError as error:
            return {'type':error.cause.type,'non_retryable':error.cause.non_retryable,'message':error.cause.message}
        raise AssertionError('Expected committed integrity failure')

async def main():
    s3=boto3.client('s3',endpoint_url='http://objects:9000')
    store=Store(s3,'integration','second-read-'+uuid.uuid4().hex)
    processing=Processing(store,'/tmp/second-read','/experiment/PROTOTYPE-wipe-me/hf',json.loads(Path('/driver/native-v1.json').read_text()))
    source=json.loads(Path('/tmp/integration-evidence/multiple.json').read_text())
    result=source['results'][0]
    original=Store(s3,'integration','final')
    def read(identity,name):return original.read_artifact(next(x for x in original.resolve(identity)['files'] if x['name']==name))
    parsed_id=result['parsed_result']
    parsed=json.loads(read(parsed_id,'parsed-result.json'))
    plan_id=parsed['plan']
    plan_bytes=read(plan_id,'plan.json')
    processing.limits=json.loads(plan_bytes)['limits']
    store.publish(plan_id,{'plan.json':plan_bytes})
    manifest=store.publish(parsed_id,{'parsed-result.json':read(parsed_id,'parsed-result.json')})
    target=manifest['files'][0]['key']
    class DisappearOnSecondRead:
        reads=0
        def __getattr__(self,name):return getattr(s3,name)
        def get_object(self,**kwargs):
            if kwargs['Key']==target:
                self.reads+=1
                if self.reads==2:s3.delete_object(Bucket='integration',Key=target)
            return s3.get_object(**kwargs)
    fault=DisappearOnSecondRead();store.client=fault
    client=await Client.connect('temporal:7233');queue='second-read-'+uuid.uuid4().hex
    async with Worker(client,task_queue=queue,workflows=[SecondRead],activities=[processing.run]):
        handle=await client.start_workflow(SecondRead.run,{'stage':'select','plan':plan_id,'parsed_result':parsed_id},id=queue,task_queue=queue)
        failure=await handle.result()
        assert failure=={'type':'integrity','non_retryable':True,'message':'committed_payload_missing'},failure
        history=await handle.fetch_history()
        attempts=[e.activity_task_started_event_attributes.attempt for e in history.events if e.HasField('activity_task_started_event_attributes')]
        assert attempts==[1],attempts
        record={'workflow_id':handle.id,'failure':failure,'attempts':attempts,'target_reads':fault.reads}
        assert fault.reads==2
        print(json.dumps(record,indent=2))
if __name__=='__main__':asyncio.run(main())
