"""Export attributable metadata and actual Temporal stage histories, never PDF text."""
import asyncio
import hashlib
import json
from pathlib import Path
import platform
import sys
from temporalio.client import Client
from temporalio.api.enums.v1 import EventType
from temporalio.converter import DataConverter

async def main():
    root = Path('/tmp/t09a-results'); out = Path('/tmp/t09a-public'); out.mkdir(exist_ok=True)
    client = await Client.connect('temporal:7233')
    profiles = {'native':json.loads(Path('/driver/native-v1.json').read_text())}
    runtime = {'python':sys.version,'platform':platform.platform(),'profiles':profiles,
        'producer':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/app/pdf_processing').glob('*.py')},
        'worker_sha256':hashlib.sha256(Path('/driver/worker.py').read_bytes()).hexdigest()}
    (out/'runtime.json').write_text(json.dumps(runtime,indent=2))
    for path in root.glob('*.json'):
        if path.name.endswith(('-document.json','-evidence.json')):continue
        value = json.loads(path.read_text())
        if not isinstance(value,dict) or not value.get('workflow_id') or not value.get('result'):continue
        history = await client.get_workflow_handle(value['workflow_id']).fetch_history()
        events = []
        for event in history.events:
            kind = EventType.Name(event.event_type)
            row = {'id':event.event_id,'kind':kind,'time':event.event_time.ToJsonString()}
            if kind=='EVENT_TYPE_ACTIVITY_TASK_SCHEDULED':
                attr=event.activity_task_scheduled_event_attributes
                args=await DataConverter.default.decode(attr.input.payloads)
                row.update(activity=attr.activity_type.name,queue=attr.task_queue.name,
                    stage=args[0].get('stage'),operation_kind=args[0].get('operation',{}).get('kind'),
                    range=[args[0].get('operation',{}).get('start'),args[0].get('operation',{}).get('end')])
            elif kind=='EVENT_TYPE_ACTIVITY_TASK_STARTED':
                attr=event.activity_task_started_event_attributes
                row.update(scheduled_event_id=attr.scheduled_event_id,attempt=attr.attempt,identity=attr.identity)
            elif kind=='EVENT_TYPE_ACTIVITY_TASK_COMPLETED':
                attr=event.activity_task_completed_event_attributes
                row.update(scheduled_event_id=attr.scheduled_event_id,started_event_id=attr.started_event_id)
            events.append(row)
        value['events']=events
        (out/path.name).write_text(json.dumps(value,indent=2))
    for path in root.glob('*-quality.json'):(out/path.name).write_bytes(path.read_bytes())
    print('Metadata exported to',out)

if __name__=='__main__':asyncio.run(main())
