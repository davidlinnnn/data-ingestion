"""Publish immutable release ConfigMaps and isolated stage Deployments, initially paused."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from pdf_processing.routing import fingerprint, release, release_binding, STAGES
NS = 'pdf-t08-validation'
IMAGE = 'docker.io/library/pdf-t08-runtime@sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0'

def k(*args):
    return subprocess.check_output(['kubectl','-n',NS,*args], text=True)

def apply(obj):
    subprocess.run(['kubectl','apply','-f','-'], input=json.dumps(obj), text=True, check=True)

def main():
    package = {p.name:p.read_text() for p in (ROOT/'src/pdf_processing').glob('*.py')}
    producer = {n:hashlib.sha256(s.encode()).hexdigest() for n,s in package.items()}
    name = 'package-'+fingerprint(producer)[:20]
    apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':name,'namespace':NS},'immutable':True,'data':package})
    base = json.loads(k('get','deployment','activities','-o','json'))['spec']['template']['spec']
    limits = {'max_bytes':104857600,'max_pages':100,'max_page_pixels':20000000,'preflight_seconds':30,'child_seconds':540}
    routes = {}
    for version,scale in (('v1',3),('v2',4)):
        profile = json.loads((ROOT/'deploy/pdf-processing/profiles/native-v1.json').read_text())
        profile['picture_ocr'] = {'render_scale':scale}
        binding = release_binding(profile, producer, limits, 't08', 'rollout/')
        route = release(binding, {s:IMAGE for s in ('workflow',*STAGES)}, 't08-'+version)
        routes[version] = route
        config = 'release-'+route['id'][:20]
        apply({'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':config,'namespace':NS},'immutable':True,
            'data':{'route.json':json.dumps(route),'native-v1.json':json.dumps(profile),
                    'worker.py':(ROOT/'deploy/pdf-processing/worker.py').read_text()}})
        for stage in ('workflow',*STAGES):
            spec = copy.deepcopy(base)
            for v in spec['volumes']:
                if v.get('configMap',{}).get('name') == 't08-package':v['configMap']['name']=name
                if v.get('configMap',{}).get('name') == 't08-driver':v['configMap']['name']=config
            c = spec['containers'][0]
            c['image'] = IMAGE
            # Qualification scheduling reservations; not calibrated production bounds.
            # Only group workers retain a native converter between Activities.
            c['resources']['requests']['memory'] = '256Mi' if stage=='group' else '64Mi'
            env = {e['name']:e for e in c['env']}
            values = {'TASK_QUEUE':route['queues'][stage], 'WORKER_ROLE':'workflow' if stage=='workflow' else 'activity',
                'WORKER_STAGE':stage,'WORKER_IMAGE':IMAGE,'ROUTING_FILE':'/driver/route.json',
                'OBJECT_BUCKET':'t08','OBJECT_PREFIX':'rollout','LIMITS':json.dumps(limits),
                'PARSER_MODE':'warm','DRAIN_SECONDS':'30','PARSER_BUDGETS':'{"terminate_seconds":5,"reap_seconds":5}'}
            env.update({n:{'name':n,'value':v} for n,v in values.items()});c['env']=list(env.values())
            dep = 't08-'+version+'-'+stage.replace('_','-')
            apply({'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':dep,'namespace':NS},
                'spec':{'replicas':0,'selector':{'matchLabels':{'app':dep}},
                    'template':{'metadata':{'labels':{'app':dep}},'spec':spec}}})
    (ROOT/'tests/pdf_processing/t08/evidence/routes.json').write_text(json.dumps(routes,indent=2))
    k('cp',str(ROOT/'tests/pdf_processing/t08/evidence/routes.json'),'coordinator:/tmp/t08-routes.json')
    k('scale','deployment/activities','--replicas=0')
    k('scale','deployment/workflows','--replicas=0')

if __name__=='__main__':main()
