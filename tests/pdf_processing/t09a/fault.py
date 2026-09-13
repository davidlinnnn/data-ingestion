"""Pause an observed native child, then drain/replace its owned Pod under flock."""
import fcntl
import json
import subprocess
import time
from run import NS,OUT,PYTHON,ROOT,k,pod,inventory,quiesce

TRIAL='drain-native'

def sample(worker,suffix):
    k('cp',str(ROOT/'tests/pdf_processing/t09a/sample.py'),worker+':/tmp/sample.py')
    stream=(OUT/(TRIAL+suffix+'-live-samples.jsonl')).open('w')
    child=subprocess.Popen(['kubectl','-n',NS,'exec',worker,'--',PYTHON,'/tmp/sample.py'],stdout=stream,stderr=subprocess.DEVNULL)
    return child,stream

def save_samples(worker,suffix):
    try:k('cp',worker+':/tmp/t09a-samples.jsonl',str(OUT/(TRIAL+suffix+'-samples.jsonl')))
    except subprocess.SubprocessError:return False
    return True

with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    samplers=[];driver=None
    event={'status':'preparing','started':time.time()}
    def record(): (OUT/(TRIAL+'-controller.json')).write_text(json.dumps(event,indent=2))
    record()
    try:
        k('get','pods');inventory(TRIAL+'-before')
        k('scale','deployment/activities','--replicas=1')
        k('rollout','status','deployment/activities','--timeout=90s')
        old=pod();before=json.loads(k('get','pod',old,'-o','json'))
        event.update(old_pod=old,old_uid=before['metadata']['uid']);record()
        samplers.append(sample(old,'-old'))
        k('cp',str(ROOT/'tests/pdf_processing/t09a/probe.py'),old+':/tmp/probe.py')
        k('cp',str(ROOT/'tests/pdf_processing/t09a/verify.py'),'coordinator:/tmp/t09a-test/verify.py')
        with (OUT/(TRIAL+'.log')).open('w') as log:
            driver=subprocess.Popen(['kubectl','-n',NS,'exec','coordinator','--',PYTHON,'/tmp/t09a-test/verify.py','native',TRIAL],stdout=log,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                raw=k('exec',old,'--',PYTHON,'/tmp/probe.py','--stop').strip()
                if raw:event.update(json.loads(raw));break
                if driver.poll() is not None:raise RuntimeError('Workflow ended before injection')
                time.sleep(.5)
            assert event.get('stopped'),'No active long native stage observed'
            progress_script='''import asyncio,json
from pathlib import Path
from temporalio.client import Client
async def main():
 c=await Client.connect('temporal:7233');a=json.loads(Path('/tmp/t09a-results/active.json').read_text())
 p=await c.get_workflow_handle(a['workflow_id']).query('progress')
 print(json.dumps({'workflow_id':a['workflow_id'],'progress':p}))
asyncio.run(main())'''
            state=json.loads(k('exec','coordinator','--',PYTHON,'-c',progress_script));progress=state['progress']
            assert 5<=progress['registered_pages']<51 and progress['status']=='parsing'
            event.update(workflow_id=state['workflow_id'],registered_pages_before=progress['registered_pages'],
                retained_groups_before=[s['operation'] for s in progress['steps'] if s['stage']=='group'],
                unfinished_group=[progress['registered_pages']+1,min(progress['registered_pages']+5,51)],status='native_stopped')
            record();save_samples(old,'-old')
            event.update(delete_started=time.time(),status='deleting');record()
            k('delete','pod',old,'--wait=false')
            while True:
                inventory(TRIAL+'-during')
                rows=json.loads(k('get','pods','-l','app=t09a-activities','-o','json'))['items']
                if not any(p['metadata']['name']==old for p in rows):break
                save_samples(old,'-old');time.sleep(3)
            event.update(old_absent=time.time(),status='replacing');record()
            new=pod();after=json.loads(k('get','pod',new,'-o','json'))
            assert before['metadata']['uid']!=after['metadata']['uid']
            event.update(new_pod=new,new_uid=after['metadata']['uid']);record()
            samplers.append(sample(new,'-new'))
            while driver.poll() is None:inventory(TRIAL+'-during');time.sleep(10)
            assert driver.returncode==0,(OUT/(TRIAL+'.log')).read_text()
            event['complete_observed']=time.time();record()
            proof_script='''import asyncio,json
from pathlib import Path
import boto3
from temporalio.client import Client
from temporalio.converter import DataConverter
from pdf_processing.object_store import Store
async def main():
 r=json.loads(Path('/tmp/t09a-results/drain-native.json').read_text())
 s=Store(boto3.client('s3',endpoint_url='http://objects:9000'),'t09a','final')
 groups=[x['operation'] for x in r['result']['steps'] if x['stage']=='group']
 for identity in groups:
  m=s.resolve(identity)
  for f in m['files']:s.read_artifact(f)
 c=await Client.connect('temporal:7233');h=await c.get_workflow_handle(r['workflow_id']).fetch_history()
 scheduled={};attempts=[]
 for e in h.events:
  if e.HasField('activity_task_scheduled_event_attributes'):
   a=e.activity_task_scheduled_event_attributes;v=(await DataConverter.default.decode(a.input.payloads))[0]
   if v.get('operation',{}).get('kind')=='group':scheduled[e.event_id]=v['operation']
  if e.HasField('activity_task_started_event_attributes'):
   a=e.activity_task_started_event_attributes
   if a.scheduled_event_id in scheduled:attempts.append({'operation':scheduled[a.scheduled_event_id],'attempt':a.attempt})
 print(json.dumps({'groups':groups,'attempts':attempts,'registered_payloads_readable':True,'fresh_full_document_equal':r['checks']['fresh_full_document_equal']}))
asyncio.run(main())'''
            proof=json.loads(k('exec','coordinator','--',PYTHON,'-c',proof_script))
            assert all(g in proof['groups'] for g in event['retained_groups_before'])
            assert any([a['operation']['start'],a['operation']['end']]==event['unfinished_group'] and a['attempt']==2 for a in proof['attempts'])
            assert proof['fresh_full_document_equal']
            event['proof']=proof;record()
            node=before['spec']['nodeName'];cid=before['status']['containerStatuses'][0]['containerID'].split('://')[1]
            running=json.loads(subprocess.check_output(['docker','exec',node,'crictl','ps','--id',cid,'--state','Running','-o','json'],text=True))
            assert not running['containers']
            scratch='/var/lib/kubelet/pods/'+before['metadata']['uid']+'/volumes/kubernetes.io~empty-dir/scratch'
            subprocess.run(['docker','exec',node,'test','!','-e',scratch],check=True)
            event.update(old_runtime_container_stopped=True,old_scratch_removed=True,status='passed');record()
            k('exec',new,'--','touch','/tmp/t09a-stop-sampling');save_samples(new,'-new')
    except BaseException as error:
        event.update(status='interrupted_or_failed',error=type(error).__name__,failed_at=time.time());record();raise
    finally:
        quiesce()
        for sampler,stream in samplers:
            if sampler.poll() is None:sampler.terminate()
            stream.close()
        if driver is not None and driver.poll() is None:driver.terminate()
        event['quiescent_at']=time.time();record()
        fcntl.flock(lock,fcntl.LOCK_UN)
        print('T09a fault window quiescent; lock released',flush=True)
