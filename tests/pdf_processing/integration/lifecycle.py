"""Run isolated SIGTERM gates against actual OCR children/publication and retry."""
import json,subprocess,time
from pathlib import Path
NS='pdf-integration-0913'
ROOT=Path(__file__).resolve().parent

def k(*args):return subprocess.check_output(['kubectl','-n',NS,*args],text=True)
def apply(obj):subprocess.run(['kubectl','apply','-f','-'],input=json.dumps(obj),text=True,check=True)
cm=json.loads(k('get','cm','integration-driver','-o','json'))
cm['data']['fault_worker.py']=(ROOT/'fault_worker.py').read_text()
cm['metadata']={'name':'integration-driver','namespace':NS}
apply(cm)
subprocess.run(['kubectl','-n',NS,'cp',str(ROOT/'lifecycle_request.py'),'coordinator:/tmp/lifecycle_request.py'],check=True)

def spec(name,case,fault):
 s=json.loads(k('get','deployment','activities','-o','json'))['spec']['template']['spec']
 s['restartPolicy']='Never'
 c=s['containers'][0]
 c['command']=['/experiment/.venv/bin/python','/driver/fault_worker.py' if fault else '/driver/worker.py']
 for e in c['env']:
  if e['name']=='TASK_QUEUE':e['value']='integration-'+case
 c['env'].append({'name':'INTEGRATION_FAULT','value':case})
 return {'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':NS},'spec':s}

for case in ('active','publication'):
 name='ocr-'+case
 apply(spec(name,case,True))
 k('wait','pod/'+name,'--for=condition=Ready','--timeout=60s')
 run=subprocess.Popen(['kubectl','-n',NS,'exec','coordinator','--','/experiment/.venv/bin/python','/tmp/lifecycle_request.py',case])
 start=time.monotonic()
 while time.monotonic()-start<180:
  if 'INTEGRATION_OCR_PAUSED' in k('logs',name):break
  time.sleep(.5)
 else:raise AssertionError('No actual OCR fault seam reached')
 start=time.monotonic()
 k('exec',name,'--','sh','-c','kill -TERM 1')
 while time.monotonic()-start<60:
  state=json.loads(k('get','pod',name,'-o','json'))
  status=state['status']['containerStatuses'][0]['state']
  if 'terminated' in status:break
  time.sleep(.3)
 else:raise AssertionError('Shutdown exceeded 60s Pod budget')
 elapsed=time.monotonic()-start
 log=k('logs',name)
 rows=[]
 for line in log.splitlines():
  try:rows.append(json.loads(line))
  except ValueError:pass
 cleanup=next(row for row in rows if row.get('event')=='integration_cleanup')
 assert cleanup['alive']==[] and cleanup['tracked_children']==0 and cleanup['scratch']==[],cleanup
 assert status['terminated']['exitCode']==0,status
 assert 29<=elapsed<60,elapsed
 if case=='active':assert cleanup['pids'],cleanup
 record={'case':case,'signal':'SIGTERM to container PID1','pod_uid':state['metadata']['uid'],
  'signal_to_exit_seconds':elapsed,'pod_grace_seconds':60,'sdk_drain_seconds':30,
  'cleanup':cleanup,'termination':status['terminated']}
 (ROOT/'evidence'/f'{case}-shutdown.json').write_text(json.dumps(record,indent=2))
 (ROOT/'evidence'/f'{case}-worker.log').write_text(log)
 apply(spec(name+'-recovery',case,False))
 assert run.wait(timeout=180)==0
 subprocess.run(['kubectl','-n',NS,'cp','coordinator:/tmp/integration-'+case+'.json',str(ROOT/'evidence'/f'{case}-result.json')],check=True)
 print(json.dumps(record),flush=True)
 # Release the replacement model memory; keep Pod log and durable evidence.
 k('exec',name+'-recovery','--','sh','-c','kill -TERM 1')
