"""Bind committed scenario reports to actual Temporal histories; metadata only."""
import asyncio,json
from pathlib import Path
from temporalio.client import Client

async def main():
    root=Path('/tmp/t07-matrix')
    reports={p.stem:json.loads(p.read_text()) for p in root.glob('*.json') if p.stem!='source'}
    by_request={v['request']['request_id']:k for k,v in reports.items() if 'request' in v}
    client=await Client.connect('temporal:7233');records=[]
    async for listed in client.list_workflows():
        history=await client.get_workflow_handle(listed.id,run_id=listed.run_id).fetch_history()
        start=history.events[0].workflow_execution_started_event_attributes
        values=await client.data_converter.decode(start.input.payloads)
        if not values or not isinstance(values[0],dict):continue
        submitted=values[0];request=submitted.get('request',{})
        if request.get('request_id') not in by_request:continue
        activity_types=[]
        for event in history.events:
            if event.HasField('activity_task_scheduled_event_attributes'):
                activity_types.append(event.activity_task_scheduled_event_attributes.activity_type.name)
        records.append({'scenario':by_request[request['request_id']],'workflow_id':listed.id,
            'run_id':listed.run_id,'activity_queue':submitted.get('activity_queue'),
            'request_id':request['request_id'],'history_event_count':len(history.events),
            'scheduled_activity_types':activity_types,'status':listed.status.name if listed.status else None})
    assert all(any(r['scenario']==name for r in records) for name in by_request.values())
    (root/'temporal.json').write_text(json.dumps(records,indent=2))
    print('Temporal history attribution: PASS')

asyncio.run(main())
