"""Run adversarial finalization checks in a disposable owned Pod under flock."""
import fcntl
import json
import subprocess
import time
from run import NS,ROOT,OUT,k

NAME='geometry-negatives'
with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        seed=k('exec','coordinator','--','cat','/tmp/t09a-results/fresh-09.json')
        config={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':NAME,'namespace':NS},
                'data':{'seed.json':seed,'verify.py':(ROOT/'tests/pdf_processing/t09a/geometry_negatives.py').read_text()}}
        subprocess.run(['kubectl','apply','-f','-'],input=json.dumps(config),text=True,check=True)
        spec=json.loads(k('get','pod','coordinator','-o','json'))['spec']
        spec.pop('nodeName',None)
        spec['volumes']=[v for v in spec['volumes'] if not v['name'].startswith('kube-api')]
        spec['volumes'].append({'name':'negative','configMap':{'name':NAME}})
        for container in spec['containers']:
            container['volumeMounts']=[v for v in container['volumeMounts'] if not v['name'].startswith('kube-api')]
            container['volumeMounts'].append({'name':'negative','mountPath':'/negative'})
            container['command']=['sh','-c','/experiment/.venv/bin/python /negative/verify.py > /tmp/result.log 2>&1; echo $? > /tmp/finished; sleep infinity']
            container['resources']={'limits':{'memory':'512Mi','cpu':'1'},'requests':{'memory':'64Mi','cpu':'100m'}}
        pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':NAME,'namespace':NS},'spec':spec}
        subprocess.run(['kubectl','apply','-f','-'],input=json.dumps(pod),text=True,check=True)
        k('wait','--for=condition=Ready','pod/'+NAME,'--timeout=60s')
        deadline=time.monotonic()+600
        while time.monotonic()<deadline:
            status=k('exec',NAME,'--','sh','-c','cat /tmp/finished 2>/dev/null || true').strip()
            if status:
                log=k('exec',NAME,'--','cat','/tmp/result.log')
                (OUT/'geometry-negatives.log').write_text(log);print(log,flush=True)
                assert status=='0','Geometry regression failed'
                k('cp',NAME+':/tmp/t09a-results/review-failures.json',str(OUT/'geometry-negatives.json'))
                break
            time.sleep(3)
        else:raise TimeoutError('Geometry regression did not finish')
    finally:
        while True:
            try:
                k('delete','pod',NAME,'--ignore-not-found','--wait=false')
                if not k('get','pod',NAME,'--ignore-not-found','-o','name').strip():break
            except subprocess.SubprocessError:pass
            print('Holding regression lock until owned Pod is absent',flush=True);time.sleep(5)
        fcntl.flock(lock,fcntl.LOCK_UN)
