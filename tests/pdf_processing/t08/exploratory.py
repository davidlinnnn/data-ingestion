"""Read-only retained Temporal record of excluded trials; no payload text export."""
import asyncio
import json
from pathlib import Path
from temporalio.client import Client

CASES={
    'baseline_missing_route':'t08-red-missing-routing',
    'api_timeout':'t08-queued-9032f8d597a54707a8ba8880b7f7ae02',
    'scheduling_stall':'t08-loss-fb14abbbbc4b4a75957d597308ee6748',
    'finished_before_loss':'t08-loss-613824947d7d49df976829ba695978fc',
    'fourteen_pod_transport_stall':'t08-loss-ef632569c0f04d7c8b8e6182b583f46c',
}

async def main():
    client=await Client.connect('temporal:7233')
    records=[]
    for case,identity in CASES.items():
        handle=client.get_workflow_handle(identity)
        description=await handle.describe()
        assert description.status is not None, 'Temporal description has no status'
        history=await handle.fetch_history()
        first=history.events[0].workflow_execution_started_event_attributes
        payload=json.loads(first.input.payloads[0].data)
        steps=[]
        for event in history.events:
            if event.HasField('activity_task_scheduled_event_attributes'):
                a=event.activity_task_scheduled_event_attributes
                value=json.loads(a.input.payloads[0].data)
                steps.append({'stage':value.get('operation',{}).get('kind',value['stage']),
                    'queue':a.task_queue.name,'scheduled_at':event.event_time.ToJsonString()})
        records.append({'case':case,'qualification':'excluded','workflow_id':identity,
            'run_id':first.original_execution_run_id,'temporal_status':description.status.name,
            'request':payload.get('request'),'workflow_queue':first.task_queue.name,
            'started_at':history.events[0].event_time.ToJsonString(),
            'last_event_at':history.events[-1].event_time.ToJsonString(),'scheduled_stages':steps})
    Path('/tmp/t08-exploratory-history.json').write_text(json.dumps(records,indent=2))

if __name__=='__main__':asyncio.run(main())
