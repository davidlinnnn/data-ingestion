"""Restart-aware fixed-configuration admission, measurement and owned cleanup."""
import fcntl
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from r2_resources import NS, ROOT, RUN_ID, PREFIX, OUT, k, setup

PYTHON='/experiment/.venv/bin/python'
NODE='internal-a2a-vs6-local-worker2'
ACTIVITIES='r2-activities-'+RUN_ID
WORKFLOWS='r2-workflows-'+RUN_ID

def vm():
    raw=subprocess.check_output(['docker','exec',NODE,'cat','/proc/meminfo','/proc/vmstat','/proc/pressure/memory'],text=True,timeout=15)
    available=re.search(r'MemAvailable:\s+(\d+)',raw)
    kills=re.search(r'^oom_kill (\d+)',raw,re.M)
    assert available and kills,'Incomplete VM telemetry'
    return {'time':time.time(),'available':int(available[1])*1024,
        'oom_kill':int(kills[1]),'raw':raw}

def running_owned():
    data=json.loads(subprocess.check_output(['docker','exec',NODE,'crictl','ps','--state','Running','-o','json'],text=True,timeout=20))
    return [c for c in data['containers'] if c.get('labels',{}).get('io.kubernetes.pod.namespace')==NS
        and c.get('labels',{}).get('io.kubernetes.pod.name','').startswith(('r2-activities-','r2-workflows-'))]

def quiesce():
    while True:
        try:
            deployments=json.loads(k('get','deployments','-o','json'))['items']
            for deployment in deployments:
                name=deployment['metadata']['name']
                if name.startswith(('r2-activities-','r2-workflows-')):k('scale','deployment/'+name,'--replicas=0')
            pods=json.loads(k('get','pods','-o','json'))['items']
            owned=[p for p in pods if p['metadata']['name'].startswith(('r2-activities-','r2-workflows-'))]
            if not owned and not running_owned():
                OUT.mkdir(parents=True,exist_ok=True)
                with (OUT/'cleanup.jsonl').open('a') as f:f.write(json.dumps({'time':time.time(),'owned_pods':0,'owned_running_containers':0})+'\n')
                return
        except subprocess.SubprocessError:pass
        print('Holding flock until owned r2 Pods AND runtime containers are absent',flush=True)
        time.sleep(5)

def admission():
    initial=vm();deadline=time.monotonic()+60
    while True:
        value=vm()
        with (OUT/'admission.jsonl').open('a') as f:f.write(json.dumps(value)+'\n')
        assert value['available']>=3*2**30,'Insufficient VM MemAvailable; no workload admitted'
        assert value['oom_kill']==initial['oom_kill'],'New global OOM during admission'
        pressure=re.search(r'^full avg10=([\d.]+)',value['raw'],re.M)
        assert pressure and float(pressure[1])==0,'Memory pressure during admission'
        assert not running_owned(),'Prior owned runtime still active'
        if time.monotonic()>=deadline:return value
        time.sleep(10)

def pod():
    rows=json.loads(k('get','pods','-l','app='+PREFIX+'-activities','-o','json'))['items']
    return next(p for p in rows if not p['metadata'].get('deletionTimestamp'))

def trial(sid,name,restart=False,args=None):
    assert not (OUT/(name+'-controller.json')).exists(),'Use a new trial name; never overwrite evidence'
    record={'trial':name,'sid':sid,'started':time.time(),'status':'starting'}
    def save(): (OUT/(name+'-controller.json')).write_text(json.dumps(record,indent=2))
    save();sampler=None;driver=None;stream=None;err=None
    try:
        if restart:
            k('scale','deployment/'+ACTIVITIES,'--replicas=0')
            while json.loads(k('get','pods','-l','app='+PREFIX+'-activities','-o','json'))['items']:time.sleep(3)
            while any(c.get('labels',{}).get('io.kubernetes.pod.name','').startswith('r2-activities-') for c in running_owned()):time.sleep(2)
        k('scale','deployment/'+ACTIVITIES,'--replicas=1');k('rollout','status','deployment/'+ACTIVITIES,'--timeout=90s')
        worker=pod();name_pod=worker['metadata']['name'];count=worker['status']['containerStatuses'][0]['restartCount']
        assert count==0,'Container restarted between trials; do not qualify warm continuity'
        first_trial=None
        if name.startswith('warm-') and name!='warm-0-06':
            first_trial=json.loads((OUT/'warm-0-06-controller.json').read_text())
            assert worker['metadata']['uid']==first_trial['pod_uid'],'Warm Pod changed between trials'
        record.update(pod=name_pod,pod_uid=worker['metadata']['uid'],before=worker['status']['containerStatuses']);save()
        k('cp',str(ROOT/'tests/pdf_processing/t09a/sample.py'),name_pod+':/tmp/r2-sample.py')
        k('exec',name_pod,'--','rm','-f','/tmp/t09a-stop-sampling','/tmp/t09a-samples.jsonl')
        stream=(OUT/(name+'-samples.jsonl')).open('w');err=(OUT/(name+'-sampler-errors.txt')).open('w')
        sampler=subprocess.Popen(['kubectl','-n',NS,'exec',name_pod,'--',PYTHON,'/tmp/r2-sample.py'],stdout=stream,stderr=err)
        ready_deadline=time.monotonic()+20
        while True:
            assert sampler.poll() is None,'Sampler failed before submission'
            lines=(OUT/(name+'-samples.jsonl')).read_text().splitlines()
            if lines:
                try:first=json.loads(lines[0]);break
                except ValueError:pass
            assert time.monotonic()<ready_deadline,'Sampler readiness deadline'
            time.sleep(.2)
        baseline=vm();record['oom_before']=baseline['oom_kill'];save()
        if first_trial is not None:assert baseline['oom_kill']==first_trial['oom_before'],'Global OOM between warm trials'
        k('exec',name_pod,'--','touch','/tmp/r2-enable-polling')
        with (OUT/(name+'.log')).open('w') as log:
            record['submitted_at']=time.time();save()
            driver=subprocess.Popen(['kubectl','-n',NS,'exec','coordinator','--','env','PYTHONPATH=/tmp/'+PREFIX+'-code','T09A_R2_RUN='+RUN_ID,PYTHON,'/tmp/'+PREFIX+'-test/verify.py',sid,name]+(args or []),stdout=log,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+1200
            while driver.poll() is None:
                state=vm();current=pod();status=current['status']['containerStatuses'][0]
                node=json.loads(k('get','--raw','/api/v1/nodes/'+NODE+'/proxy/stats/summary'))
                with (OUT/(name+'-monitor.jsonl')).open('a') as f:f.write(json.dumps({'vm':state,'worker':status,'pod_uid':current['metadata']['uid'],'node':node})+'\n')
                assert current['metadata']['uid']==record['pod_uid'] and status['restartCount']==count,'Unexpected worker replacement/restart'
                assert sampler.poll() is None,'Sampler ended before complete workflow'
                assert state['oom_kill']==baseline['oom_kill'],'Global OOM: stop, diagnose, no automatic rerun'
                assert state['available']>=512*2**20,'VM headroom below stop threshold'
                assert time.monotonic()<deadline,'Controller observation deadline'
                time.sleep(3)
            assert driver.returncode==0,'Verifier failed; retain log'
        record['complete_observed_at']=time.time()
        final_vm=vm();final_pod=pod()
        record.update(final_vm=final_vm,after=final_pod['status']['containerStatuses']);save()
        assert final_vm['oom_kill']==baseline['oom_kill'] and final_vm['available']>=512*2**20,'Final resource check failed'
        assert final_pod['metadata']['uid']==record['pod_uid'] and final_pod['status']['containerStatuses'][0]['restartCount']==count,'Final worker continuity failed'
        sample_deadline=time.monotonic()+10
        while True:
            assert sampler.poll() is None,'Sampler ended before completion coverage'
            lines=(OUT/(name+'-samples.jsonl')).read_text().splitlines()
            try:
                if lines and json.loads(lines[-1])['time']>=record['complete_observed_at']:break
            except ValueError:pass
            assert time.monotonic()<sample_deadline,'Missing post-completion sample'
            time.sleep(.2)
        k('exec',name_pod,'--','touch','/tmp/t09a-stop-sampling');sampler.wait(timeout=15)
        assert sampler.returncode==0,'Sampler transport failure'
        stream.flush();samples=[json.loads(l) for l in (OUT/(name+'-samples.jsonl')).read_text().splitlines()]
        assert samples and first['time']<=record['submitted_at'] and samples[0]['time']==first['time']
        assert samples[-1]['time']>=record['complete_observed_at'],'Sampling does not cover completion'
        assert time.time()-samples[-1]['time']<15,'Incomplete measurement tail'
        assert max(b['time']-a['time'] for a,b in zip(samples,samples[1:]))<5,'Measurement gap'
        final_vm=vm();final_pod=pod()
        assert final_vm['oom_kill']==baseline['oom_kill'] and final_vm['available']>=512*2**20,'Resource failure at acceptance'
        assert final_pod['metadata']['uid']==record['pod_uid'] and final_pod['status']['containerStatuses'][0]['restartCount']==count,'Worker changed at acceptance'
        record.update(status='passed',finished=time.time(),final_vm=final_vm,after=final_pod['status']['containerStatuses'],continuous_observation=True);save()
    except BaseException as error:
        record.update(status='failed_or_interrupted',error=str(error),finished=time.time(),continuous_observation=False);save()
        raise
    finally:
        if record['status']!='passed':quiesce()
        for child in (sampler,driver):
            if child is not None and child.poll() is None:child.terminate();child.wait(timeout=15)
        if stream is not None:stream.close()
        if err is not None:err.close()

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            admission()
            if sys.argv[1]=='admission':raise SystemExit(0)
            names=setup()
            (OUT/'immutable-configs.json').write_text(json.dumps(names))
            k('scale','deployment/'+WORKFLOWS,'--replicas=1');k('rollout','status','deployment/'+WORKFLOWS,'--timeout=60s')
            mode=sys.argv[1]
            if mode=='preflight':trial('10','preflight-10',True)
            elif mode=='fresh':
                for sid in sys.argv[2:]:trial(sid,'fresh-'+sid,True)
            elif mode=='warm':
                for i,sid in enumerate(('06','07','08','native','06')):trial(sid,f'warm-{i}-{sid}',i==0,['--require-fresh'])
            elif mode=='replay':
                for i,sid in enumerate(sys.argv[2:]):
                    script='from pathlib import Path; import sys; r=Path(sys.argv[1]); (r/(sys.argv[2]+"-request.json")).write_bytes((r/(sys.argv[3]+"-request.json")).read_bytes())'
                    k('exec','coordinator','--',PYTHON,'-c',script,'/tmp/'+PREFIX+'-results','replay-'+sid,'fresh-'+sid)
                    trial(sid,'replay-'+sid,i==0,['--expect-reuse','--expect-exact-replay','--require-fresh'])
            elif mode=='compatibility':
                trial('native','compatible-old-native',True,['--source-from-old','drain-native','--expect-old-groups','--require-fresh'])
            else:raise ValueError(mode)
        finally:
            quiesce()
            fcntl.flock(lock,fcntl.LOCK_UN)
