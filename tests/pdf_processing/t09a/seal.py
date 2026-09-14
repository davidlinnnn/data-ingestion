"""Seal metadata-only exports and observational attribution; never copy source payloads."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'evidence'
RAW=Path('/private/tmp/t09a-controller')
PUBLIC=Path('/private/tmp/t09a-public-final')

def write(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2)+'\n')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

trials=[]
for path in PUBLIC.glob('*.json'):
    value=json.loads(path.read_text())
    # The export deliberately excludes PDF/document/crop/OCR text payloads.
    (OUT/path.name).write_text(json.dumps(value,separators=(',',':'))+'\n')
    if value.get('checks'):
        trials.append({'trial':value['trial'],'workflow_id':value['workflow_id'],
            'seconds':value['finished']-value['started'],'checks':value['checks']})
write('trial-summary.json',trials)
shutil.copyfile('/private/tmp/t09a-measurements.json',OUT/'measurements.json')
for name in ('geometry-negatives.json','evidence-fix-checks.json','drain-native-controller.json'):
    shutil.copyfile(RAW/name,OUT/name)

pods={}
for path in RAW.glob('*-worker.json'):
    value=json.loads(path.read_text())
    pods[path.name.removesuffix('-worker.json')]={
        'name':value['metadata']['name'],'uid':value['metadata']['uid'],
        'node':value['spec']['nodeName'],'resources':[c['resources'] for c in value['spec']['containers']],
        'scratch':[v for v in value['spec']['volumes'] if v['name']=='scratch'],
        'containers':value['status']['containerStatuses']}
drain=json.loads((RAW/'drain-current-pods.json').read_text())
for value in drain['items']:
    pods['drain-replacement']={'name':value['metadata']['name'],'uid':value['metadata']['uid'],
        'node':value['spec']['nodeName'],'resources':[c['resources'] for c in value['spec']['containers']],
        'containers':value['status']['containerStatuses']}
write('pod-attribution.json',pods)
image=json.loads((RAW/'node-image-inspect.json').read_text())
write('image-attribution.json',{'cri_status':image['status'],
    'platform':{k:image['info']['imageSpec'].get(k) for k in ('architecture','os')},
    'chain_id':image['info']['chainID'],
    'interpretation':'Observed repo digest and earlier sha256 content ID resolve to this same retained CRI image. Mutable spec tag is not the identity. Per-trial actual method and producer remain separately retained.'})

kernel=(RAW/'kernel-dmesg.txt').read_text().splitlines()
uids={p['uid'].replace('-','_') for p in pods.values()}
oom=[line for line in kernel if 'oom-kill:' in line and any(uid in line for uid in uids)]
write('oom-attribution.json',{'events':oom,
    'classification':'global_oom / CONSTRAINT_NONE for matched warm and drain-replacement containers',
    'not_established':['5Gi container limit exhaustion','memory leak','sole contributing workload','stable warm resource envelope'],
    'kernel_snapshot_sha256':sha(RAW/'kernel-dmesg.txt')})

profile=json.loads((PUBLIC/'profile4-06.json').read_text())
assert {x['render_scale'] for x in profile['ocr_execution_metadata']}=={4}
assert all(s['reused'] for s in profile['result']['steps'] if s['stage'] in ('group','assembly'))
assert profile['checks']['fresh_full_document_equal']
write('profile-transition-checks.json',{'render_scale':4,'actual_ocr_reports':len(profile['ocr_execution_metadata']),
    'native_group_assembly_reused':True,'full_document_equal':True,
    'measurement_qualification':'bounded observation only; no combined stable warm envelope'})

absent=json.loads((RAW/'quiescence-pods.json').read_text())
running=json.loads((RAW/'quiescence-containers.json').read_text())
owned=[c for c in running['containers'] if c.get('labels',{}).get('io.kubernetes.pod.namespace')=='pdf-t09a-validation'
       and c.get('labels',{}).get('io.kubernetes.pod.name','').startswith('activities-')]
assert not absent['items'] and not owned
write('quiescence.json',{'owned_activity_pods':0,'owned_running_activity_containers':0,
    'controller_retained_flock_until_pod_absence':True,
    'workflow_state':'retained queued work; never restore workers without reconciliation'})

manifest=[]
for path in sorted(RAW.rglob('*')):
    if path.is_file():manifest.append({'private_path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)})
write('private-observation-hashes.json',manifest)
print('Sealed metadata; qualification remains partial/open.')
