"""Bounded native-group graceful drain, with immutable r2 request and proof."""
import fcntl
import json
import subprocess
import time
from run import NS, ROOT, RUN_ID, PREFIX, OUT, PYTHON, NODE, ACTIVITIES, WORKFLOWS, k, setup, admission, vm, pod, quiesce

NAME='drain-native'

def remote(script,*args):
    return k('exec','coordinator','--','env','PYTHONPATH=/tmp/'+PREFIX+'-code',PYTHON,'-c',script,*args)

def start_sampler(worker,suffix):
    k('cp',str(ROOT/'tests/pdf_processing/t09a/sample.py'),worker+':/tmp/r2-sample.py')
    stream=(OUT/(NAME+'-'+suffix+'-samples.jsonl')).open('w')
    errors=(OUT/(NAME+'-'+suffix+'-sampler-errors.txt')).open('w')
    process=subprocess.Popen(['kubectl','-n',NS,'exec',worker,'--',PYTHON,'/tmp/r2-sample.py'],stdout=stream,stderr=errors)
    deadline=time.monotonic()+20
    while True:
        assert process.poll() is None and time.monotonic()<deadline,'Sampler readiness failed'
        lines=(OUT/(NAME+'-'+suffix+'-samples.jsonl')).read_text().splitlines()
        if lines:
            try:json.loads(lines[0]);break
            except ValueError:pass
        time.sleep(.2)
    return process,stream,errors

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/(NAME+'-controller.json')
    assert not path.exists(),'Use another run ID rather than overwrite a fault trial'
    record={'status':'admission','run_id':RUN_ID,'started':time.time()}
    def save():path.write_text(json.dumps(record,indent=2)+'\n')
    samplers=[];driver=None;save()
    with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            admission();setup()
            baseline=vm()
            last_node=0
            def monitor():
                nonlocal last_node
                state=vm()
                with (OUT/(NAME+'-vm.jsonl')).open('a') as f:f.write(json.dumps(state)+'\n')
                if time.time()-last_node>=3:
                    node=json.loads(k('get','--raw','/api/v1/nodes/'+NODE+'/proxy/stats/summary'))
                    with (OUT/(NAME+'-node.jsonl')).open('a') as f:f.write(json.dumps({'time':time.time(),'node':node})+'\n')
                    last_node=time.time()
                assert state['oom_kill']==baseline['oom_kill'] and state['available']>=512*2**20,'Resource failure: abort controlled fault'
            for deployment in (WORKFLOWS,ACTIVITIES):
                k('scale','deployment/'+deployment,'--replicas=1');k('rollout','status','deployment/'+deployment,'--timeout=90s')
            old=pod();old_name=old['metadata']['name'];record['old']=old;save()
            assert old['status']['containerStatuses'][0]['restartCount']==0
            samplers.append(start_sampler(old_name,'old'))
            k('exec',old_name,'--','touch','/tmp/r2-enable-polling')
            k('cp',str(ROOT/'tests/pdf_processing/t09a/probe.py'),old_name+':/tmp/r2-probe.py')
            with (OUT/(NAME+'.log')).open('w') as log:
                record['submitted_at']=time.time();save()
                driver=subprocess.Popen(['kubectl','-n',NS,'exec','coordinator','--','env','PYTHONPATH=/tmp/'+PREFIX+'-code','T09A_R2_RUN='+RUN_ID,
                    PYTHON,'/tmp/'+PREFIX+'-test/verify.py','native',NAME,'--require-fresh'],stdout=log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+180
                while True:
                    monitor()
                    assert samplers[0][0].poll() is None,'Sampler lost before injection'
                    raw=k('exec',old_name,'--',PYTHON,'/tmp/r2-probe.py','--stop').strip()
                    if raw:record['injection']=json.loads(raw);save();break
                    assert driver.poll() is None and time.monotonic()<deadline,'No bounded native stage observed'
                    time.sleep(.5)
                state=json.loads(remote('''import asyncio,json,sys
from pathlib import Path
from temporalio.client import Client
async def main():
 a=json.loads((Path(sys.argv[1])/'active.json').read_text());c=await Client.connect('temporal:7233')
 print(json.dumps({'workflow_id':a['workflow_id'],'progress':await c.get_workflow_handle(a['workflow_id']).query('progress')}))
asyncio.run(main())''','/tmp/'+PREFIX+'-results'))
                progress=state['progress'];assert 5<=progress['registered_pages']<51
                record.update(workflow_id=state['workflow_id'],registered_before=progress['registered_pages'],
                    retained_groups=[s['operation'] for s in progress['steps'] if s['stage']=='group'],
                    unfinished_range=[progress['registered_pages']+1,min(progress['registered_pages']+5,51)],
                    status='deleting',delete_started=time.time());save()
                k('delete','pod',old_name,'--wait=false')
                while k('get','pod',old_name,'--ignore-not-found','-o','name').strip():monitor();time.sleep(2)
                record['old_pod_absent']=time.time();save()
                k('rollout','status','deployment/'+ACTIVITIES,'--timeout=90s')
                new=pod();new_name=new['metadata']['name'];assert old['metadata']['uid']!=new['metadata']['uid']
                record.update(new=new,status='recovering');save()
                samplers.append(start_sampler(new_name,'new'))
                record['replacement_polling_enabled_at']=time.time();save()
                k('exec',new_name,'--','touch','/tmp/r2-enable-polling')
                deadline=time.monotonic()+900
                while driver.poll() is None:
                    monitor();current=pod()
                    assert current['metadata']['uid']==new['metadata']['uid'] and current['status']['containerStatuses'][0]['restartCount']==0,'Unexpected recovery restart'
                    assert samplers[1][0].poll() is None and time.monotonic()<deadline,'Recovery observation failed'
                    time.sleep(3)
                monitor();assert driver.returncode==0,'Recovery did not complete'
                record['complete_observed_at']=time.time();save()
                proof=json.loads(remote('''import asyncio,json,sys,boto3
from pathlib import Path
from temporalio.client import Client
from temporalio.converter import DataConverter
from pdf_processing.object_store import Store
async def main():
 r=json.loads((Path(sys.argv[1])/'drain-native.json').read_text());s=Store(boto3.client('s3',endpoint_url='http://objects:9000'),'t09a','final')
 groups=[x['operation'] for x in r['result']['steps'] if x['stage']=='group']
 for identity in groups:
  m=s.resolve(identity);assert m
  for f in m['files']:s.read_artifact(f)
 c=await Client.connect('temporal:7233');history=await c.get_workflow_handle(r['workflow_id']).fetch_history();scheduled={};attempts=[]
 for e in history.events:
  if e.HasField('activity_task_scheduled_event_attributes'):
   v=(await DataConverter.default.decode(e.activity_task_scheduled_event_attributes.input.payloads))[0]
   if v.get('operation',{}).get('kind')=='group':scheduled[e.event_id]=v['operation']
  if e.HasField('activity_task_started_event_attributes'):
   a=e.activity_task_started_event_attributes
   if a.scheduled_event_id in scheduled:attempts.append({'operation':scheduled[a.scheduled_event_id],'attempt':a.attempt})
 print(json.dumps({'groups':groups,'attempts':attempts,'payloads_readable':True,'full_document_equal':r['checks']['fresh_full_document_equal']}))
asyncio.run(main())''','/tmp/'+PREFIX+'-results'))
                assert all(g in proof['groups'] for g in record['retained_groups']) and proof['full_document_equal']
                assert any([a['operation']['start'],a['operation']['end']]==record['unfinished_range'] and a['attempt']==2 for a in proof['attempts'])
                assert all(a['attempt']==1 for a in proof['attempts'] if a['operation']['end']<=record['registered_before'])
                cid=old['status']['containerStatuses'][0]['containerID'].split('://')[1]
                runtime=json.loads(subprocess.check_output(['docker','exec',NODE,'crictl','ps','--id',cid,'--state','Running','-o','json'],text=True,timeout=20));assert not runtime['containers']
                scratch='/var/lib/kubelet/pods/'+old['metadata']['uid']+'/volumes/kubernetes.io~empty-dir/scratch'
                subprocess.run(['docker','exec',NODE,'test','!','-e',scratch],check=True,timeout=20)
                monitor();final=pod();assert final['metadata']['uid']==new['metadata']['uid'] and final['status']['containerStatuses'][0]['restartCount']==0
                deadline=time.monotonic()+10
                while True:
                    assert samplers[1][0].poll() is None,'Recovery sampler ended prematurely'
                    lines=(OUT/(NAME+'-new-samples.jsonl')).read_text().splitlines()
                    try:
                        if lines and json.loads(lines[-1])['time']>=record['complete_observed_at']:break
                    except ValueError:pass
                    assert time.monotonic()<deadline,'No complete recovery sample coverage'
                    time.sleep(.2)
                k('exec',new_name,'--','touch','/tmp/t09a-stop-sampling')
                samplers[1][0].wait(timeout=15);assert samplers[1][0].returncode==0
                coverage={}
                for suffix in ('old','new'):
                    samples=[json.loads(l) for l in (OUT/(NAME+'-'+suffix+'-samples.jsonl')).read_text().splitlines()]
                    gap=max(b['time']-a['time'] for a,b in zip(samples,samples[1:]));assert gap<5
                    coverage[suffix]={'first':samples[0]['time'],'last':samples[-1]['time'],'count':len(samples),'maximum_gap':gap}
                assert coverage['old']['first']<=record['submitted_at'] and coverage['old']['last']>=record['delete_started']
                assert coverage['new']['first']<=record['replacement_polling_enabled_at'] and coverage['new']['last']>=record['complete_observed_at']
                monitor();final=pod();assert final['metadata']['uid']==new['metadata']['uid'] and final['status']['containerStatuses'][0]['restartCount']==0
                record.update(status='passed',proof=proof,sampling_coverage=coverage,old_runtime_stopped=True,old_scratch_absent=True,finished=time.time());save()
        except BaseException as error:
            record.update(status='failed_or_interrupted',error=str(error),finished=time.time());save();raise
        finally:
            quiesce()
            for process,stream,errors in samplers:
                if process.poll() is None:process.terminate()
                process.wait(timeout=15);stream.close();errors.close()
            if driver is not None and driver.poll() is None:driver.terminate();driver.wait(timeout=15)
            record['quiescent_at']=time.time();save()
            fcntl.flock(lock,fcntl.LOCK_UN)

if __name__=='__main__':main()
