"""Owned active native-child stop plus Pod drain/replacement under the shared lock."""
import fcntl
import json
from pathlib import Path
import subprocess
import time
from run import NS,OUT,PYTHON,ROOT,k,pod,inventory,quiesce

TRIAL='drain-native'

def start_sampler(worker):
    k('cp',str(ROOT/'tests/pdf_processing/t09a/sample.py'),worker+':/tmp/sample.py')
    return subprocess.Popen(['kubectl','-n',NS,'exec',worker,'--',PYTHON,'/tmp/sample.py'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

def save_samples(worker,suffix):
    try:k('cp',worker+':/tmp/t09a-samples.jsonl',str(OUT/(TRIAL+suffix+'-samples.jsonl')))
    except subprocess.SubprocessError:return False
    return True

with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    sampler=None;driver=None
    try:
        k('get','pods');inventory(TRIAL+'-before')
        k('scale','deployment/activities','--replicas=1')
        k('rollout','status','deployment/activities','--timeout=90s')
        old=pod();before=json.loads(k('get','pod',old,'-o','json'))
        sampler=start_sampler(old)
        k('cp',str(ROOT/'tests/pdf_processing/t09a/probe.py'),old+':/tmp/probe.py')
        k('cp',str(ROOT/'tests/pdf_processing/t09a/verify.py'),'coordinator:/tmp/t09a-test/verify.py')
        with (OUT/(TRIAL+'.log')).open('w') as log:
            driver=subprocess.Popen(['kubectl','-n',NS,'exec','coordinator','--',PYTHON,'/tmp/t09a-test/verify.py','native',TRIAL],stdout=log,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+180
            event=None
            while time.monotonic()<deadline:
                raw=k('exec',old,'--',PYTHON,'/tmp/probe.py','--stop').strip()
                if raw:event=json.loads(raw);break
                if driver.poll() is not None:raise RuntimeError('Workflow ended before injection')
                time.sleep(.5)
            assert event is not None,'No active long native stage observed'
            save_samples(old,'-old')
            event.update(old_pod=old,old_uid=before['metadata']['uid'],delete_started=time.time())
            k('delete','pod',old,'--wait=false')
            # Keep collecting the terminating Pod until it is truly absent.
            while True:
                inventory(TRIAL+'-during')
                rows=json.loads(k('get','pods','-l','app=t09a-activities','-o','json'))['items']
                if not any(p['metadata']['name']==old for p in rows):break
                save_samples(old,'-old');time.sleep(3)
            event['old_absent']=time.time()
            new=pod();after=json.loads(k('get','pod',new,'-o','json'))
            assert before['metadata']['uid']!=after['metadata']['uid']
            assert not any(p['metadata']['name']==old for p in rows)
            event.update(new_pod=new,new_uid=after['metadata']['uid'])
            sampler.wait(timeout=15);sampler=start_sampler(new)
            while driver.poll() is None:
                inventory(TRIAL+'-during');time.sleep(10)
            assert driver.returncode==0,(OUT/(TRIAL+'.log')).read_text()
            event['complete_observed']=time.time()
            k('exec',new,'--','touch','/tmp/t09a-stop-sampling');sampler.wait(timeout=15)
            save_samples(new,'-new')
            (OUT/(TRIAL+'-controller.json')).write_text(json.dumps(event,indent=2))
    finally:
        quiesce()
        if sampler is not None and sampler.poll() is None:sampler.terminate()
        if driver is not None and driver.poll() is None:driver.terminate()
        fcntl.flock(lock,fcntl.LOCK_UN)
        print('T09a fault window quiescent; lock released',flush=True)
