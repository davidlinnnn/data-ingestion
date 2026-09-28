import fcntl,json,subprocess,time
from pathlib import Path
root=Path('/private/tmp/pdf-t08-t09a-integration');out=root/'tests/pdf_processing/integration_0914/evidence';ns='pdf-t08-validation';name='integration-0914'
def k(*args):return subprocess.check_output(['kubectl','--request-timeout=20s','-n',ns,*args],text=True,timeout=30)
def apply(obj):subprocess.run(['kubectl','--request-timeout=20s','apply','-f','-'],input=json.dumps(obj),text=True,check=True,timeout=30)
with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 try:
  package={p.name:p.read_text() for p in (root/'src/pdf_processing').glob('*.py')}
  for suffix,data in [('package',package),('driver',{'runtime.py':(root/'tests/pdf_processing/integration_0914/runtime.py').read_text(),'profile.json':(root/'deploy/pdf-processing/profiles/native-v1.json').read_text()})]:
   apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':name+'-'+suffix,'namespace':ns},'immutable':True,'data':data})
  spec=json.load(open('/private/tmp/pdf-integration-coordinator.json'))['spec']
  spec['restartPolicy']='Never';spec['volumes']=[v for v in spec['volumes'] if not v['name'].startswith('kube-api')]
  for v in spec['volumes']:
   if v['name']=='code':v['configMap']['name']=name+'-package'
   if v['name']=='driver':v['configMap']['name']=name+'-driver'
  spec['volumes'].append({'name':'scratch','emptyDir':{'sizeLimit':'2Gi'}})
  c=spec['containers'][0];c['volumeMounts']=[v for v in c['volumeMounts'] if not v['name'].startswith('kube-api')]
  for v in c['volumeMounts']:
   if v['name']=='driver':v['mountPath']='/check'
  c['volumeMounts'].append({'name':'scratch','mountPath':'/scratch'})
  c['image']='docker.io/library/pdf-t08-runtime@sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0'
  c['resources']={'requests':{'memory':'256Mi','cpu':'100m'},'limits':{'memory':'5Gi','cpu':'4'}}
  c['command']=['sh','-c','/experiment/.venv/bin/python /check/runtime.py > /tmp/integration.log 2>&1; echo $? > /tmp/integration.exit; sleep infinity']
  apply({'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':ns},'spec':spec})
  deadline=time.monotonic()+720
  while time.monotonic()<deadline:
   pod=json.loads(k('get','pod',name,'-o','json'))
   if pod['status'].get('phase')=='Running':
    status=k('exec',name,'--','sh','-c','cat /tmp/integration.exit 2>/dev/null || true').strip()
    if status:
     (out/'runtime.log').write_text(k('exec',name,'--','cat','/tmp/integration.log'))
     assert status=='0',(status,(out/'runtime.log').read_text()[-4000:])
     (out/'result.json').write_text(k('exec',name,'--','cat','/tmp/integration-result.json'))
     (out/'pod.json').write_text(json.dumps(pod,indent=2));print('runtime PASS',flush=True);break
   elif pod['status'].get('phase')=='Failed':raise RuntimeError(pod['status'])
   time.sleep(3)
  else:raise TimeoutError('bounded integration window exceeded')
 finally:
  while True:
   try:
    k('delete','pod',name,'--ignore-not-found','--wait=false')
    if not k('get','pod',name,'--ignore-not-found','-o','name').strip():break
   except subprocess.SubprocessError:pass
   print('Holding lock until owned integration Pod disappears',flush=True);time.sleep(5)
  (out/'cleanup.json').write_text(json.dumps({'owned_pod_absent':True,'forced_deletion':False}))
  print('Owned Pod absent; releasing qualification lock',flush=True)
