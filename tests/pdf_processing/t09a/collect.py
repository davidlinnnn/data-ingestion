"""Export attributable metadata and actual Temporal stage histories, never PDF text."""
import asyncio
import hashlib
import json
from pathlib import Path
import platform
import sys
import boto3
from pdf_processing.object_store import Store
from temporalio.client import Client
from temporalio.api.enums.v1 import EventType
from temporalio.converter import DataConverter

async def main():
    root = Path('/tmp/t09a-results'); out = Path('/tmp/t09a-public'); out.mkdir(exist_ok=True)
    client = await Client.connect('temporal:7233')
    store = Store(boto3.client('s3',endpoint_url='http://objects:9000'),'t09a','final')
    def artifacts(identity):
        manifest=store.resolve(identity)
        assert manifest is not None
        return {x['name']:x for x in manifest['files']}
    def read(identity,name):return json.loads(store.read_artifact(artifacts(identity)[name]))
    profiles = {'native':json.loads(Path('/driver/native-v1.json').read_text())}
    runtime = {'python':sys.version,'platform':platform.platform(),'profiles':profiles,
        'producer':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/app/pdf_processing').glob('*.py')},
        'worker_sha256':hashlib.sha256(Path('/driver/worker.py').read_bytes()).hexdigest()}
    (out/'runtime.json').write_text(json.dumps(runtime,indent=2))
    active=json.loads((root/'active.json').read_text())
    active_handle=client.get_workflow_handle(active['workflow_id'])
    active['progress']=await active_handle.query('progress')
    active['history_event_types']=[EventType.Name(e.event_type) for e in (await active_handle.fetch_history()).events]
    (out/'last-active-workflow.json').write_text(json.dumps(active,indent=2))
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
        if value.get('final'):
            final=value['final']
            value['accepted_plan']=read(final['plan'],'plan.json')
            stages=[]
            for step in value['result']['steps']:
                if step['stage'] not in ('group','assembly'):continue
                files=artifacts(step['operation'])
                row={'operation':step['operation'],'stage':step['stage'],'reused':step['reused']}
                if 'events.jsonl' in files:
                    row['native_events']=[json.loads(line) for line in store.read_artifact(files['events.jsonl']).splitlines()]
                if 'metrics.json' in files:row['metrics']=read(step['operation'],'metrics.json')
                if 'method.json' in files:row['actual_method']=read(step['operation'],'method.json')
                stages.append(row)
            value['retained_native_stage_observations']=stages
            ocr=[]
            for component in final['enrichments']:
                report=read(component['operation'],'ocr.json')
                ocr.append({key:report[key] for key in ('component','render_scale','pixel_dimensions','crop_sha256','producer','seconds_including_engine_load')})
            value['ocr_execution_metadata']=ocr
        (out/path.name).write_text(json.dumps(value,indent=2))
    for path in root.glob('*-quality.json'):(out/path.name).write_bytes(path.read_bytes())
    print('Metadata exported to',out)

if __name__=='__main__':asyncio.run(main())
