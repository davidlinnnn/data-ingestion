"""Recreate isolated verification resources; see README for retained inputs."""
import subprocess,json,pathlib
root=pathlib.Path(__file__).resolve().parents[3]
ns='pdf-t09a-validation'
def k(*args):return subprocess.check_output(['kubectl',*args],text=True)
def apply(obj):return subprocess.run(['kubectl','apply','-f','-'],input=json.dumps(obj),text=True,check=True)
apply({'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns}})
apply({'apiVersion':'v1','kind':'Secret','metadata':{'name':'store-access','namespace':ns},'stringData':{'AWS_ACCESS_KEY_ID':'prototype-local','AWS_SECRET_ACCESS_KEY':'prototype-local-only-password'}})
for name in ('storage','temporal'):
 data=(root/f'docs/prototypes/pdf-checkpoint-prototype/performance/{name}.yaml').read_text().replace('pdf-checkpoint-performance',ns)
 subprocess.run(['kubectl','apply','-f','-'],input=data,text=True,check=True)
apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'t09a-package','namespace':ns},'data':{p.name:p.read_text() for p in (root/'src/pdf_processing').glob('*.py')}})
profile=pathlib.Path('/private/tmp/t09a-profile.json')
old={'native-v1.json':profile.read_text() if profile.exists() else (root/'deploy/pdf-processing/profiles/native-v1.json').read_text()}
old['worker.py']=(root/'deploy/pdf-processing/worker.py').read_text()
old['verify.py']=(root/'tests/pdf_processing/t09a/verify.py').read_text()
apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'t09a-driver','namespace':ns},'data':old})
import base64
fixture={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'t09a-fixtures','namespace':ns},'binaryData':{p.name:base64.b64encode(p.read_bytes()).decode() for p in pathlib.Path('/private/tmp/pdf-integration-fixtures').glob('*.pdf') if p.stat().st_size < 100000}}
assert fixture['binaryData'], 'Prepare qualified fixtures first'
apply(fixture)
for role in ('workflows','activities','coordinator'):
 if role == 'coordinator' and subprocess.run(['kubectl','-n',ns,'get','pod','coordinator'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0: continue
 kind='pod' if role=='coordinator' else 'deployment'
 old=json.loads(k('-n','pdf-t04-validation','get',kind,role,'-o','json'))
 spec=old['spec'] if kind=='pod' else old['spec']['template']['spec']
 for key in ('nodeName','serviceAccount','serviceAccountName'):spec.pop(key,None)
 spec['volumes']=[v for v in spec['volumes'] if not v['name'].startswith('kube-api')]
 for v in spec['volumes']:
  if 'configMap' in v:v['configMap']['name']=v['configMap']['name'].replace('t04','t09a')
 spec['terminationGracePeriodSeconds']=60
 for v in spec['volumes']:
  if 'emptyDir' in v:v['emptyDir']['sizeLimit']='2Gi'
 for c in spec['containers']:
  c['volumeMounts']=[v for v in c['volumeMounts'] if not v['name'].startswith('kube-api')]
  for env in c.get('env',[]):
   if 'value' in env:env['value']=env['value'].replace('t04','t09a')
  if role=='activities':
   for env in c['env']:
    if env['name']=='LIMITS':env['value']=json.dumps({'max_bytes':104857600,'max_pages':51,'max_page_pixels':20000000,'preflight_seconds':30,'child_seconds':540})
  if role=='activities':c['resources']={'limits':{'cpu':'4','memory':'5Gi'},'requests':{'cpu':'100m','memory':'256Mi'}}
  if role=='activities':c['env'] += [{'name':'DRAIN_SECONDS','value':'30'},{'name':'PARSER_BUDGETS','value':'{"startup_seconds":120,"no_progress_seconds":180,"terminate_seconds":5,"reap_seconds":5,"max_requests":20}'}]
 metadata={'name':role,'namespace':ns}
 if kind=='pod':obj={'apiVersion':'v1','kind':'Pod','metadata':metadata,'spec':spec}
 else:obj={'apiVersion':'apps/v1','kind':'Deployment','metadata':metadata,'spec':{'replicas':0 if role=='activities' else 1,'selector':{'matchLabels':{'app':'t09a-'+role}},'template':{'metadata':{'labels':{'app':'t09a-'+role}},'spec':spec}}}
 apply(obj)
