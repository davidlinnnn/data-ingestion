import subprocess,json,time,sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,'/private/tmp/t09a-bounds/tests/pdf_processing/q04')
from sentinel import run_yolo_pod_cgroup_p as base

def cluster():
    items=json.loads(subprocess.check_output(['kubectl','--context',base.CONTEXT,'get','deployments','-A','-o','json']))['items']
    by={(x['metadata']['namespace'],x['metadata']['name']):x for x in items}
    for e in base.lifecycle.CANDIDATES:
        x=by[e['namespace'],e['name']]
        assert x['metadata']['uid']==e['uid'] and x['spec'].get('replicas',1)==0 and x['status'].get('readyReplicas',0)==0
    x=by['pdf-t09a-validation','objects']
    assert x['status'].get('readyReplicas')==1 and x['spec']['template']['spec']['containers'][0]['resources']['limits']['memory']=='512Mi'
    return {'held_deployments_off':32,'object_memory':'512Mi','object_ready':True}
root=Path(sys.argv[1]); assert not (root/'controller.json').exists()
(root/'preflight.json').write_text(json.dumps(cluster(),indent=2))
cmd=['docker','create','--pull=never','--name',root.name,'--network=none','--memory=5g','--memory-swap=5g','--cpus=4','--read-only','--tmpfs','/tmp:rw,size=512m','-e','PYTHONPATH=/probe/src','-e','PYTHONDONTWRITEBYTECODE=1','-v',str(root)+':/probe','-v',str(root/'input')+':/input:ro','-v','/private/tmp/t09a-bounds:/source:ro','pdf-checkpoint-prototype:linux-v2',sys.argv[2]]
cid=subprocess.check_output(cmd,text=True,timeout=30).strip();r={'container_id':cid,'started':time.time(),'automatic_retry':False,'command':cmd}
(root/'controller.json').write_text(json.dumps(r,indent=2))
try:
    with (root/'runtime.log').open('w') as log:
        result=subprocess.run(['docker','start','-a',cid],stdout=log,stderr=subprocess.STDOUT,timeout=150)
    r['exit_code']=result.returncode
except subprocess.TimeoutExpired:r['timeout']=True
finally:
    state=json.loads(subprocess.check_output(['docker','inspect','--format','{{json .State}}',cid],text=True));r['state']=state
    if state['Running']:subprocess.run(['docker','kill',cid],check=True,stdout=subprocess.DEVNULL,timeout=15)
    subprocess.run(['docker','rm',cid],check=True,stdout=subprocess.DEVNULL,timeout=15)
    r['removed']=True;r['finished']=time.time();(root/'controller.json').write_text(json.dumps(r,indent=2))
    assert cid not in subprocess.check_output(['docker','ps','-aq','--no-trunc'],text=True).splitlines()
    (root/'independent-cleanup.json').write_text(json.dumps({'container_absent':True,**cluster()},indent=2))
print(json.dumps({k:v for k,v in r.items() if k not in ('command','state')},indent=2))
print((root/'runtime.log').read_text()[-1800:])
for path in (root/'trace').glob('*.jsonl'):print(path.read_text())
