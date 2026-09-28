"""Create only run-specific immutable configs/deployments; caller holds admission lock."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
NS='pdf-t09a-validation'
RUN_ID=os.environ['T09A_R2_RUN']
OUT=Path('/private/tmp/t09a-r2-20260914')/RUN_ID
PREFIX='t09a-r2-'+RUN_ID

def k(*args):return subprocess.check_output(['kubectl','--request-timeout=15s','-n',NS,*args],text=True,timeout=40)
def apply(value):subprocess.run(['kubectl','apply','-f','-'],input=json.dumps(value),text=True,check=True,timeout=40)

def setup():
    specs={role:json.loads(k('get','deployment',role,'-o','json'))['spec']['template']['spec'] for role in ('activities','workflows')}
    code={p.name:p.read_text() for p in (ROOT/'src/pdf_processing').glob('*.py')}
    profile=Path('/private/tmp/t09a-profile.json').read_text()
    driver={'worker.py':(ROOT/'deploy/pdf-processing/worker.py').read_text(),'native-v1.json':profile}
    activity=specs['activities']['containers'][0]
    driver['activity-command.json']=json.dumps(activity['command']+activity.get('args',[]))
    driver['gate.py']='''import json,os,time
from pathlib import Path
while not Path('/tmp/r2-enable-polling').exists():time.sleep(.1)
command=json.loads(Path('/driver/activity-command.json').read_text())
os.execv(command[0],command)
'''
    OUT.mkdir(parents=True,exist_ok=True)
    names={};objects=[];images={}
    for role,data in [('code',code),('driver',driver)]:
        name='t09a-r2-'+role+'-'+hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()[:16]
        objects.append({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':name,'namespace':NS},'immutable':True,'data':data});names[role]=name
    for role in ('activities','workflows'):
        spec=specs[role]
        for volume in spec['volumes']:
            if volume['name'] in names:volume['configMap']['name']=names[volume['name']]
        for container in spec['containers']:
            image=json.loads(subprocess.check_output(['docker','exec','internal-a2a-vs6-local-worker2','crictl','inspecti',container['image']],text=True,timeout=20))
            assert image['status']['repoDigests'],'Pinned image digest unavailable'
            container['image']=sorted(image['status']['repoDigests'])[0]
            images[role]={'content_id':image['status']['id'],'repo_digest':container['image'],
                'platform':{key:image['info']['imageSpec'][key] for key in ('architecture','os')}}
            if role=='activities':
                container['command']=['/experiment/.venv/bin/python','/driver/gate.py'];container.pop('args',None)
            for env in container['env']:
                if env['name']=='TASK_QUEUE':env['value']=PREFIX+('-pdf' if role=='activities' else '-workflows')
        name='r2-'+role+'-'+RUN_ID
        objects.append({'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':name,'namespace':NS},
            'spec':{'replicas':0,'selector':{'matchLabels':{'app':PREFIX+'-'+role}},
            'template':{'metadata':{'labels':{'app':PREFIX+'-'+role}},'spec':spec}}})
    frozen={'verifier':hashlib.sha256((ROOT/'tests/pdf_processing/t09a_r3/verify.py').read_bytes()).hexdigest(),'run_id':RUN_ID,'producer':hashlib.sha256(json.dumps(code,sort_keys=True).encode()).hexdigest(),
        'driver':hashlib.sha256(json.dumps(driver,sort_keys=True).encode()).hexdigest(),'effective_specs':specs,'images':images}
    binding=OUT/'frozen-release.json'
    if binding.exists():assert json.loads(binding.read_text())==frozen,'Changed effective release requires a new run ID and queues'
    else:binding.write_text(json.dumps(frozen,indent=2))
    for value in objects:apply(value)
    base='/tmp/'+PREFIX
    k('exec','coordinator','--','mkdir','-p',base+'-code',base+'-test',base+'-results')
    k('cp',str(ROOT/'src/pdf_processing'),f'coordinator:{base}-code/pdf_processing')
    k('cp',str(ROOT/'tests/pdf_processing/t09a_r3/verify.py'),f'coordinator:{base}-test/verify.py')
    k('cp',str(ROOT/'tests/pdf_processing/t09a_r2/evidence/old-workflow-result.json'),'coordinator:/tmp/t09a-r2-old-workflow-result.json')
    return names
