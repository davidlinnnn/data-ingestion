"""External controller: delete only prototype worker Pods at announced fault points."""
import json
from pathlib import Path
import subprocess
import time

NAMESPACE='pdf-checkpoint-prototype'
OUT=Path(__file__).resolve().parent/'evidence-linux'
OUT.mkdir(exist_ok=True)
seen=set()
def kubectl(*args):
    return subprocess.check_output(['kubectl','-n',NAMESPACE,*args],text=True)
start=time.monotonic()
while len(seen)<5 and time.monotonic()-start<1800:
    pods=json.loads(kubectl('get','pods','-l','app=pdf-worker','-o','json'))['items']
    for pod in pods:
        if pod['status'].get('phase')!='Running':
            continue
        name=pod['metadata']['name']
        try:
            logs=kubectl('logs',name)
        except subprocess.CalledProcessError:
            continue
        for line in logs.splitlines():
            try:
                event=json.loads(line)
            except ValueError:
                continue
            if event.get('event')!='fault_ready' or event['identity'] in seen:
                continue
            evidence={'time':time.time(),'pod':name,'uid':pod['metadata']['uid'],'point':event['point'],'identity':event['identity']}
            (OUT/(name+'.log')).write_text(logs)
            result=kubectl('delete','pod',name,'--grace-period=0','--force','--wait=false')
            evidence['delete_response']=result
            with (OUT/'pod-deletions.jsonl').open('a') as f:
                f.write(json.dumps(evidence)+'\n')
            print(json.dumps(evidence),flush=True)
            seen.add(event['identity'])
            break
    time.sleep(1)
assert len(seen)==5, f'Only {len(seen)} fault points observed'
