"""Exact 60/30/5/5 lifecycle gate; a real publication remains blocked for 90s."""
import json,subprocess,time
from pathlib import Path
NAMESPACE='pdf-t05-validation'
def kubectl(*args):
    return subprocess.check_output(['kubectl','-n',NAMESPACE,*args],text=True)

def pod_spec(name, paused):
    deployment=json.loads(kubectl('get','deployment','activities','-o','json'))
    spec=deployment['spec']['template']['spec']
    spec['restartPolicy']='Never'
    spec['terminationGracePeriodSeconds']=60
    container=spec['containers'][0]
    container['command']=['/experiment/.venv/bin/python','/driver/fault_worker.py' if paused else '/driver/worker.py']
    settings={'TASK_QUEUE':'t05-deadline','DRAIN_SECONDS':'30','PARSER_BUDGETS':json.dumps({'startup_seconds':120,'no_progress_seconds':180,'terminate_seconds':5,'reap_seconds':5,'max_requests':100}), 'T05_PUBLICATION_PAUSE_SECONDS':'90'}
    env={item['name']:item for item in container['env']}
    env.update({key:{'name':key,'value':value} for key,value in settings.items()})
    container['env']=list(env.values())
    return {'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':NAMESPACE},'spec':spec}

name='deadline-expiry'
first=pod_spec(name,True)
Path('/private/tmp/t05-deadline-pod.json').write_text(json.dumps(first))
subprocess.run(['kubectl','apply','-f','/private/tmp/t05-deadline-pod.json'],check=True)
kubectl('wait','pod/'+name,'--for=condition=Ready','--timeout=60s')
run=subprocess.Popen(['kubectl','-n',NAMESPACE,'exec','coordinator','--','/experiment/.venv/bin/python','/tmp/case.py','deadline-expiry-1','t05-deadline'])
start=time.monotonic()
while time.monotonic()-start<60:
    if 'T05_PUBLICATION_PAUSED' in kubectl('logs',name): break
    time.sleep(.2)
else: raise AssertionError('Publication pause not observed')
start=time.monotonic()
kubectl('exec',name,'--','sh','-c','kill -TERM 1')
while time.monotonic()-start<60:
    state=json.loads(kubectl('get','pod',name,'-o','json'))
    status=state['status']['containerStatuses'][0]['state']
    if 'terminated' in status: break
    time.sleep(.2)
else: raise AssertionError('Worker exceeded configured Pod grace')
elapsed=time.monotonic()-start
log=kubectl('logs',name)
rows=[]
for line in log.splitlines():
    try: rows.append(json.loads(line))
    except ValueError: pass
cleanup=next(row for row in rows if row.get('event')=='T05_CLEANUP_OBSERVED')
assert cleanup['parser_reaped'] and cleanup['scratch_remaining']==[],cleanup
assert status['terminated']['exitCode']==0,status
assert elapsed<60 and elapsed>=29,elapsed
record={'pod_grace_seconds':60,'sdk_drain_seconds':30,'term_seconds':5,'reap_seconds':5,'blocked_publication_seconds':90,'signal_to_observed_exit_seconds':elapsed,'termination':status['terminated'],'cleanup':cleanup,'signal':'SIGTERM to container PID1','pod_uid':state['metadata']['uid']}
Path('/private/tmp/t05-deadline-evidence.json').write_text(json.dumps(record,indent=2))
Path('/private/tmp/t05-deadline-worker.log').write_text(log)
recovery=pod_spec('deadline-recovery',False)
Path('/private/tmp/t05-deadline-recovery.json').write_text(json.dumps(recovery))
subprocess.run(['kubectl','apply','-f','/private/tmp/t05-deadline-recovery.json'],check=True)
assert run.wait(timeout=120)==0
print(json.dumps(record))
