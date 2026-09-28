"""Real captured-source submission/result assertions; no production collaborators replaced."""
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
import boto3
from temporalio.client import Client
from temporalio.api.enums.v1 import EventType, TaskQueueType
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
from pdf_processing.object_store import Store, digest
from pdf_processing.routing import submission

OUT = Path('/tmp/t08-results')
OUT.mkdir(exist_ok=True)

async def main():
    command, *args = sys.argv[1:]
    client = await Client.connect('temporal:7233')
    routes = json.loads(Path('/tmp/t08-routes.json').read_text())
    retained = {r['id']:r for r in routes.values()}
    def payload_for(request, route):
        return submission(request, route['id'], retained)
    s3 = boto3.client('s3',endpoint_url='http://objects:9000')
    store = Store(s3,'t08','rollout')
    def read(identity,name):
        return json.loads(store.read_artifact(next(f for f in store.resolve(identity)['files'] if f['name']==name)))
    async def capture_pollers(label):
        expected=json.loads(Path('/tmp/t08-expected-population.json').read_text())
        observed=[]
        for release_name, route in routes.items():
            for stage,kind in (('workflow',TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW),('component_ocr',TaskQueueType.TASK_QUEUE_TYPE_ACTIVITY)):
                prefix='t08-'+release_name+'-'+stage.replace('_','-')+'-'
                pods=[p for p in expected if p['name'].startswith(prefix)]
                assert len(pods)==1,(prefix,pods)
                deadline=asyncio.get_running_loop().time()+60
                while True:
                    description=await client.workflow_service.describe_task_queue(DescribeTaskQueueRequest(
                        namespace=client.namespace,task_queue=TaskQueue(name=route['queues'][stage]),task_queue_type=kind))
                    now=datetime.now(timezone.utc)
                    pollers=[{'identity':p.identity,'last_access_time':p.last_access_time.ToJsonString()}
                        for p in description.pollers if p.identity.endswith('@'+pods[0]['name']) and
                        -5 <= now.timestamp()-(p.last_access_time.seconds+p.last_access_time.nanos/1e9) <= 120]
                    if pollers:break
                    assert asyncio.get_running_loop().time()<deadline,(release_name,stage,'No current Pod poller')
                    await asyncio.sleep(.5)
                observed.append({'release':release_name,'stage':stage,'queue':route['queues'][stage],
                    'pod':pods[0]['name'],'uid':pods[0]['uid'],'pollers':pollers})
        (OUT/(label+'-pollers.json')).write_text(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'queues':observed},indent=2))

    if command == 'init':
        abandoned=[]
        async for execution in client.list_workflows("ExecutionStatus = 'Running'"):
            assert execution.id.startswith('t08-'), execution.id
            await client.get_workflow_handle(execution.id).terminate('Superseded exploratory T08 trial; excluded from acceptance')
            abandoned.append(execution.id)
        (OUT/('abandoned-'+uuid.uuid4().hex+'.json')).write_text(json.dumps(abandoned))
        if not any(b['Name']=='t08' for b in s3.list_buckets()['Buckets']):s3.create_bucket(Bucket='t08')
        s3.put_bucket_versioning(Bucket='t08',VersioningConfiguration={'Status':'Enabled'})
        data = Path('/fixtures/multiple.pdf').read_bytes()
        key = 'rollout/sources/multiple.pdf'
        saved = s3.put_object(Bucket='t08',Key=key,Body=data)
        request = {'version':3,'completion':'required_evidence_v1','profile':'native-v1',
            'source_revision':'synthetic:t08:multiple',
            'artifact':{'key':key,'name':'multiple.pdf','sha256':digest(data),'version_id':saved['VersionId']}}
        (OUT/'source.json').write_text(json.dumps(request))
    elif command == 'idle':
        open_runs=[execution.id async for execution in client.list_workflows("ExecutionStatus = 'Running'")]
        assert not open_runs,open_runs
        print('No accepted execution remains open before quiescent-stage drain')
    elif command == 'submit':
        case, version = args
        if case in ('new','mixed'):await capture_pollers(case+'-before')
        request = {**json.loads((OUT/'source.json').read_text()),'request_id':'t08-'+case+'-'+uuid.uuid4().hex}
        if case in ('loss','drain'):request['source_revision'] += ':'+case
        payload = payload_for(request,routes[version])
        identity = request['request_id']
        handle = await client.start_workflow('PDFRolloutProcessing',payload,id=identity,
            task_queue=routes[version]['queues']['workflow'])
        (OUT/(case+'-request.json')).write_text(json.dumps({'workflow_id':identity,'request':payload['request'],'version':version}))
        print(identity,flush=True)
    elif command == 'progress':
        record = json.loads((OUT/(args[0]+'-request.json')).read_text())
        handle = client.get_workflow_handle(record['workflow_id'])
        description = await handle.describe()
        assert description.status is not None, 'Temporal description has no status'
        history = await handle.fetch_history()
        names = [EventType.Name(e.event_type) for e in history.events]
        scheduled = [e.activity_task_scheduled_event_attributes.activity_type.name for e in history.events if e.HasField('activity_task_scheduled_event_attributes')]
        pending = {}
        for e in history.events:
            if e.HasField('activity_task_scheduled_event_attributes'):
                value=json.loads(e.activity_task_scheduled_event_attributes.input.payloads[0].data)
                pending[e.event_id]={'stage':value.get('operation',{}).get('kind',value['stage']), 'started':False,'queue':e.activity_task_scheduled_event_attributes.task_queue.name}
            elif e.HasField('activity_task_started_event_attributes'):
                pending[e.activity_task_started_event_attributes.scheduled_event_id]['started']=True
            elif e.HasField('activity_task_completed_event_attributes'):
                pending.pop(e.activity_task_completed_event_attributes.scheduled_event_id,None)
        print(json.dumps({'status':description.status.name,'events':names,'scheduled':scheduled,'pending':list(pending.values())}))
    elif command == 'result':
        case = args[0]
        record = json.loads((OUT/(case+'-request.json')).read_text())
        handle = client.get_workflow_handle(record['workflow_id'])
        result = await handle.result()
        assert result['status']=='complete',result
        final = read(result['processing_result'],'processing-result.json')
        assert final['source']==record['request'] and final['processing_complete'] and not final['canonical_accepted']
        route = routes[record['version']]
        assert result['routing_id']==route['id']
        assert final['provenance']['profile']['picture_ocr']['render_scale']==(3 if record['version']=='v1' else 4)
        assert 'content_evidence' in final
        read(final['content_evidence'],'content-evidence.json')
        selected=read(final['selection'],'selection.json')
        ocr=[]
        for item in final['enrichments']:
            report=read(item['operation'],'ocr.json')
            assert report['source']==record['request']
            assert report['method']==selected['ocr_method']
            assert report['render_scale']==(3 if record['version']=='v1' else 4)
            expected={k.split('/')[-1]:v for k,v in final['provenance']['profile']['method']['model_artifacts'].items() if k.startswith('rapidocr/')}
            assert report['producer']['model_sha256']==expected
            ocr.append({k:report[k] for k in ('component','source_sha256','parsed_result_sha256','render_scale','crop_sha256','producer','method','outcome')})
        for step in result['steps']:
            assert step['routing_id']==route['id'] and step['task_queue']==route['queues'][step['worker_stage']]
        if case in ('new','mixed'):
            assert all(s['reused'] for s in result['steps'] if s['stage'] in ('group','assembly'))
        if case in ('loss','drain'):
            assert any(s['attempt']>=2 for s in result['steps'] if s['stage']=='group'),result
        history = await handle.fetch_history()
        activities=[]
        for e in history.events:
            if e.HasField('activity_task_scheduled_event_attributes'):
                a=e.activity_task_scheduled_event_attributes
                activities.append({'type':a.activity_type.name,'queue':a.task_queue.name,'event_id':e.event_id})
        assert {a['queue'] for a in activities}=={route['queues'][s] for s in ('prepare','group','assembly','select','component_ocr','finalize')}
        report = {**record,'result':result,'profile':final['provenance']['profile'],
            'producer':final['provenance']['producer'],'ocr':ocr,'activities':activities,
            'run_id':history.events[0].workflow_execution_started_event_attributes.original_execution_run_id}
        (OUT/(case+'.json')).write_text(json.dumps(report,indent=2))
        if case in ('new','mixed'):await capture_pollers(case+'-after')
        print(case+': PASS',flush=True)
    elif command == 'negative':
        route=routes['v1']
        try:
            submission(json.loads((OUT/'queued-request.json').read_text())['request'], 'unavailable', retained)
        except ValueError as error:
            assert str(error)=='routing_unavailable'
            (OUT/'unavailable.json').write_text(json.dumps({'status':'rejected_before_submission','code':str(error)}))
        else:raise AssertionError('Unavailable release accepted')
        for case in ('missing','malformed','inconsistent','conflict'):
            old=json.loads((OUT/'queued-request.json').read_text())['request']
            if case=='conflict':
                payload=payload_for({k:v for k,v in old.items() if k!='routing_id'},routes['v2'])
                queue=routes['v2']['queues']['workflow']
            else:
                payload=payload_for(old,route);queue=route['queues']['workflow']
                if case=='missing':payload.pop('routing')
                elif case=='malformed':payload['request']=[]
                else:payload['routing']['queues']['component_ocr']='latest'
            r=await client.execute_workflow('PDFRolloutProcessing',payload,id='t08-negative-'+uuid.uuid4().hex,task_queue=queue)
            assert r['status']=='failed',r
            assert r['error']['code']==('worker_method_mismatch' if case=='conflict' else 'invalid_routing'),r
            (OUT/(case+'.json')).write_text(json.dumps(r,indent=2))
            routes=json.loads(Path('/tmp/t08-routes.json').read_text());route=routes['v1']
        print('Missing/inconsistent routes and accepted-ID method changes: PASS')

if __name__=='__main__':asyncio.run(main())
