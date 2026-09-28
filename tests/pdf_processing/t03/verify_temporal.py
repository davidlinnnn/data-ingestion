"""Real Temporal and MinIO: timeout does not terminate the old native/thread attempt.

Small byte producers isolate late-write behavior without repeating Docling inference.
This supplements, never replaces, the real PDF/Pod-loss acceptance driver.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json
import time
import uuid
from threading import Event

import boto3
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError
from temporalio.worker import Worker

from pdf_processing.object_store import Store


@workflow.defn(sandboxed=False)
class RecoveryProbe:
    @workflow.run
    async def run(self, value: dict) -> dict:
        try:
            return await workflow.execute_activity('recovery_probe',value,
                start_to_close_timeout=timedelta(seconds=1),
                retry_policy=RetryPolicy(initial_interval=timedelta(milliseconds=100),maximum_attempts=2))
        except ActivityError:
            return {'status':'failed'}


async def main():
    client=await Client.connect('temporal:7233')
    s3=boto3.client('s3',endpoint_url='http://objects:9000')
    prefix='temporal-'+uuid.uuid4().hex
    store=Store(s3,'t03',prefix)
    events=[]
    release={case:Event() for case in ('overlap','ack','terminal')}
    old_finished={case:Event() for case in release}
    def record(case,attempt,event):
        events.append({'case':case,'attempt':attempt,'event':event,'time':time.time()})
    @activity.defn(name='recovery_probe')
    def probe(value):
        attempt=activity.info().attempt
        case=value['case']; operation=value.get('operation',case)
        record(case,attempt,'started')
        prior=store.resolve(operation)
        if prior:
            record(case,attempt,'reused')
            return {'status':'accepted','manifest':prior,'reused':True}
        if case=='terminal' and attempt==2:
            record(case,attempt,'required_failure')
            raise ApplicationError('required_failure',non_retryable=True)
        if case=='terminal':
            assert release[case].wait(15), 'Terminal result was not observed'
        def uploaded(_):
            record(case,attempt,'uploaded')
            if case=='overlap' and attempt==1:
                assert release[case].wait(15), 'Retry did not register'
        result=store.publish(operation,{'value':str(attempt).encode()},after_upload=uploaded)
        record(case,attempt,'registered')
        if case=='overlap' and attempt==2:
            release[case].set()
        if case=='ack' and attempt==1:
            assert release[case].wait(15), 'Retry acknowledgement not observed'
        if attempt==1 and case in old_finished:
            old_finished[case].set()
        return {'status':'accepted','manifest':result,'reused':False}

    results={}
    with ThreadPoolExecutor(max_workers=4) as executor:
        async with Worker(client,task_queue=prefix,workflows=[RecoveryProbe],activities=[probe],
                          activity_executor=executor,max_concurrent_activities=4):
            for case in ('overlap','ack','terminal'):
                handle=await client.start_workflow(RecoveryProbe.run,{'case':case},id=prefix+'-'+case,task_queue=prefix)
                result=await handle.result()
                release[case].set()
                assert await asyncio.to_thread(old_finished[case].wait,15), 'Old thread did not finish'
                history=await handle.fetch_history()
                starts=[e.activity_task_started_event_attributes.attempt for e in history.events
                        if e.HasField('activity_task_started_event_attributes')]
                assert 2 in starts, starts
                records=[e for e in events if e['case']==case]
                old_done=next(e['time'] for e in records if e['attempt']==1 and e['event']=='registered')
                if case!='ack':
                    retry_started=next(e['time'] for e in records if e['attempt']==2 and e['event']=='started')
                    assert old_done>retry_started
                accepted=store.resolve(case)
                assert accepted is not None
                if case=='overlap':
                    assert result['manifest']==accepted
                    assert store.read_artifact(accepted['files'][0])==b'2'
                    keys=s3.list_objects_v2(Bucket='t03',Prefix=prefix+'/diagnostics/').get('Contents',[])
                    assert keys, 'Differing alive attempts were not diagnosed'
                elif case=='ack':
                    assert result['reused']
                    assert len([e for e in records if e['event']=='uploaded'])==1
                else:
                    assert result=={'status':'failed'} and await handle.result()==result, (result, records)
                    reuse=await client.execute_workflow(RecoveryProbe.run,{'case':'reuse-terminal','operation':'terminal'},
                        id=prefix+'-reuse-terminal',task_queue=prefix)
                    assert reuse['reused'] and reuse['manifest']==accepted
                    assert await handle.result()=={'status':'failed'}, 'Late output resurrected terminal workflow'
                results[case]={'result':result,'attempts':starts,'workflow_id':handle.id,'events':records}
    print(json.dumps({'prefix':prefix,'cases':results,'inventory':store.inventory()},indent=2,default=str))


if __name__=='__main__': asyncio.run(main())
