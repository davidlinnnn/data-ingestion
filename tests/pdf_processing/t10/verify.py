"""In-Pod checks of the packaged operator and actual Temporal/storage seam."""
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, '/app')
from manage import read_json, store_for
from pdf_processing.routing import validate
from temporalio.client import Client


async def main():
    command, route_path, *args = sys.argv[1:]
    route = validate(json.loads(Path(route_path).read_text()))
    store = store_for(route)
    client = await Client.connect(os.environ['TEMPORAL_ADDRESS'])
    if command == 'idle':
        open_runs = [e.id async for e in client.list_workflows("ExecutionStatus = 'Running'")]
        assert not open_runs, open_runs
        return {'open_executions': open_runs}
    if command == 'failure':
        handle=client.get_workflow_handle(args[0])
        result=await asyncio.wait_for(handle.result(),60)
        assert result['status']=='failed' and result['processing_complete'] is False
        assert result['registered_pages']==0 and result['error']=={'category':'input','code':'digest_mismatch'}
        assert result['observed_at']
        return result
    if command == 'held':
        handle=client.get_workflow_handle(args[0])
        description=await handle.describe()
        history=await handle.fetch_history()
        assert description.status is not None and description.status.name=='RUNNING'
        assert not any(e.HasField('workflow_task_started_event_attributes') for e in history.events)
        return {'workflow_id':args[0],'temporal_status':'RUNNING','workflow_task_started':False,'routing_id':route['id']}
    if command == 'check':
        workflow_id, directory, fixture = args
        handle = client.get_workflow_handle(workflow_id)
        summary = await asyncio.wait_for(handle.result(), 300)
        assert summary['status'] == 'complete' and summary['processing_complete'], summary
        final = read_json(store, summary['processing_result'], 'processing-result.json')
        document = read_json(store, final['assembly'], 'document.json')
        assert final['source']['routing_id'] == route['id'] and not final['canonical_accepted']
        assert final['required_work']['pages'] == len(document['pages'])
        if fixture == 'ten':
            text = '\n'.join(t.get('text', '') for t in document['texts'])
            assert len(document['pages']) == 10
            assert all(f'T03 recovery fixture page {n}' in text for n in range(1, 11))
        if fixture == 'multiple':
            reports = [read_json(store, item['operation'], 'ocr.json') for item in final['enrichments']]
            assert len(reports) == 2
            text = ' '.join(t for report in reports for t in report['texts'])
            assert 'ALPHA 12345' in text and 'BETA 67890' in text, text
        if fixture == '08':
            expected = json.loads(Path('/tmp/aima-reference.json').read_text())
            assert document == expected, 'Full AIMA graph differs from accepted #44/#45 reference'
            assert final['required_work']['relationships'] == 'finished'
            assert len(final['enrichments']) == 9
        history = await handle.fetch_history()
        attempts = []
        scheduled = {}
        starts = []
        for event in history.events:
            if event.HasField('activity_task_scheduled_event_attributes'):
                activity = event.activity_task_scheduled_event_attributes
                value = json.loads(activity.input.payloads[0].data)
                stage = value.get('operation', {}).get('kind', value['stage'])
                scheduled[event.event_id] = stage
                assert activity.task_queue.name == route['queues'][stage]
            if event.HasField('activity_task_started_event_attributes'):
                started = event.activity_task_started_event_attributes
                attempts.append(started.attempt)
                starts.append({'stage': scheduled[started.scheduled_event_id], 'attempt': started.attempt})
        Path(directory).mkdir(exist_ok=True)
        (Path(directory)/'history.json').write_text(history.to_json())
        registration = store.resolve(summary['processing_result'])
        assert registration is not None
        return {'summary': summary, 'required_work': final['required_work'],
            'processing_result_registration': registration, 'activity_attempts': attempts,
            'activity_starts': starts,
            'document_sha256': next(f['sha256'] for f in store.resolve(final['assembly'])['files']
                                    if f['name'] == 'document.json'),
            'quality_accepted': final['quality_accepted'], 'canonical_accepted': final['canonical_accepted']}
    if command == 'unregistered':
        assert store.resolve(args[0]) is None
        return {'operation': args[0], 'registration': None, 'processing_complete': False}
    if command == 'inventory':
        return store.inventory(max_objects=10000, capacity_bytes=1024**3)
    if command == 'store':
        sys.path.insert(0, '/tmp/t10')
        from verify_store import verify
        return verify(store.client, store.bucket)
    raise ValueError(command)


if __name__ == '__main__':
    print(json.dumps(asyncio.run(main()), indent=2, default=str))
