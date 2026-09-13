"""Host lock spans the full rollout experiment. Mutates only T08 resources."""
import fcntl
import json
from pathlib import Path
import subprocess
import time
from releases import NS, ROOT, STAGES

OUT=ROOT/'tests/pdf_processing/t08/evidence'
PYTHON='/experiment/.venv/bin/python'

def k(*args):
    return subprocess.check_output(['kubectl','--request-timeout=15s','-n',NS,*args],text=True,timeout=1800)

def quiesce():
    # API uncertainty must not relinquish cross-task isolation. Keep the live host
    # lock until all owned workers have stopped, even when cleanup needs retries.
    while True:
        try:
            scale('v1',('workflow',*STAGES),0)
            scale('v2',('workflow',*STAGES),0)
            pods=json.loads(k('get','pods','-o','json'))['items']
            active=[p['metadata']['name'] for p in pods if p['metadata']['name'].startswith('t08-')]
            if not active:
                print('T08 remote workers confirmed stopped; coordinator is client-only.',flush=True)
                return
            print('Waiting for T08 worker termination: '+str(active),flush=True)
        except Exception as error:
            print('T08 cleanup uncertain; retaining qualification lock: '+str(error),flush=True)
        time.sleep(5)


def driver(*args):
    return k('exec','coordinator','--','env','PYTHONPATH=/tmp/t08-code',PYTHON,'/tmp/t08-verify.py',*args)

def scale(version,stages,replicas):
    for stage in stages:k('scale','deployment/t08-'+version+'-'+stage.replace('_','-'),'--replicas='+str(replicas))

def ready(version):
    for stage in ('workflow',*STAGES):k('rollout','status','deployment/t08-'+version+'-'+stage.replace('_','-'),'--timeout=90s')

def inject(case,graceful):
    started=time.monotonic()
    while time.monotonic()-started<120:
        pods=json.loads(k('get','pods','-l','app=t08-v1-group','-o','json'))['items']
        pods=[p for p in pods if not p['metadata'].get('deletionTimestamp') and p['status'].get('phase')=='Running']
        if pods:
            pod=pods[0]
            probe=k('exec',pod['metadata']['name'],'--',PYTHON,'-c', '''from pathlib import Path
import json
for p in Path('/scratch').glob('activity-*/pdf-*/process.log'):
 for line in p.read_text(errors='replace').splitlines():
  try:r=json.loads(line)
  except ValueError:continue
  if r.get('stage')=='stage_enter' and 'pid' in r:
   print(json.dumps({'pid':r['pid'],'stage':r.get('native_stage'),'pages':r.get('pages')}));raise SystemExit
''')
            if probe.strip():
                record={'case':case,'pod':pod['metadata']['name'],'uid':pod['metadata']['uid'],
                    'image':pod['status']['containerStatuses'][0]['imageID'],'native_event':json.loads(probe)}
                # The new release coexists while accepted old work is in flight.
                if case=='loss':scale('v2',('workflow',*STAGES),1)
                delete_started=time.monotonic()
                opts=() if graceful else ('--grace-period=0','--force')
                k('delete','pod',pod['metadata']['name'],'--wait=false',*opts)
                while time.monotonic()-delete_started<65:
                    live=json.loads(k('get','pods','-l','app=t08-v1-group','-o','json'))['items']
                    if not any(p['metadata']['uid']==record['uid'] for p in live):break
                    time.sleep(.5)
                else:raise RuntimeError('Old Pod exceeded retirement observation budget')
                record['deletion_seconds']=time.monotonic()-delete_started
                if graceful:assert record['deletion_seconds']<60
                (OUT/(case+'-controller.json')).write_text(json.dumps(record,indent=2))
                return
        time.sleep(.15)
    raise RuntimeError('No real native stage observed for fault injection')

with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    while True:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
        except BlockingIOError:
            print('Waiting for shared qualification lock; no inference running in T08.',flush=True);time.sleep(10)
    try:
        print('T08 qualification lock acquired',flush=True)
        k('cp',str(ROOT/'src/pdf_processing'),'coordinator:/tmp/t08-code/pdf_processing')
        k('cp',str(ROOT/'tests/pdf_processing/t08/verify.py'),'coordinator:/tmp/t08-verify.py')
        scale('v1',('workflow',*STAGES),0)
        driver('init');print(driver('submit','queued','v1'),flush=True)
        state=json.loads(driver('progress','queued'))
        assert state['status']=='RUNNING' and not state['scheduled'],state
        (OUT/'queued-before-workers.json').write_text(json.dumps(state,indent=2))
        scale('v1',('workflow','prepare'),1)
        time.sleep(4)
        state=json.loads(driver('progress','queued'))
        (OUT/'queued-before-parser.json').write_text(json.dumps(state,indent=2))
        scale('v1',STAGES,1);ready('v1')
        print(driver('result','queued'),flush=True)
        print(driver('submit','loss','v1'),flush=True);inject('loss',False)
        print(driver('result','loss'),flush=True);ready('v2')
        print(driver('submit','new','v2'),flush=True)
        print(driver('submit','mixed','v1'),flush=True)
        print(driver('result','new'),flush=True);print(driver('result','mixed'),flush=True)
        print(driver('submit','drain','v1'),flush=True);inject('drain',True)
        print(driver('result','drain'),flush=True)
        print(driver('negative'),flush=True)
        k('cp','coordinator:/tmp/t08-results',str(OUT/'results'))
        pods=json.loads(k('get','pods','-o','json'))
        (OUT/'pods.json').write_text(json.dumps([{'name':p['metadata']['name'],'uid':p['metadata']['uid'],
            'containers':p['status'].get('containerStatuses',[])} for p in pods['items']],indent=2))
    finally:
        quiesce()
        fcntl.flock(lock,fcntl.LOCK_UN)
        print('T08 qualification lock released',flush=True)
