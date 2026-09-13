"""Seal metadata-only acceptance files against the exact tested package."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
producer={p.name:sha(p) for p in (ROOT/'src/pdf_processing').glob('*.py')}
records={name:json.loads((OUT/'results'/f'{name}.json').read_text()) for name in ('queued','loss','new','mixed','drain')}
for r in records.values():assert r['producer']==producer
pods=json.loads((OUT/'pods.json').read_text())
loss=json.loads((OUT/'loss-controller.json').read_text())
assert loss['runtime_container_stopped']
assert next(p['uid'] for p in pods if p['name'].startswith('t08-v1-workflow-'))!=loss['workflow_pod_uid']
summary={name:{'workflow_id':r['workflow_id'],'run_id':r['run_id'],'request_id':r['request']['request_id'],
    'routing_id':r['result']['routing_id'],'status':r['result']['status'],
    'processing_result':r['result']['processing_result'],
    'steps':[{k:s[k] for k in ('stage','operation','attempt','reused','task_queue')} for s in r['result']['steps']]}
    for name,r in records.items()}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2))
(OUT/'runtime.json').write_text(json.dumps({'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    'producer':producer,'entrypoint_sha256':sha(ROOT/'deploy/pdf-processing/worker.py'),
    'routes':json.loads((OUT/'routes.json').read_text()),'pods':pods,
    'profile':records['queued']['profile'],'limits':{'max_bytes':104857600,'max_pages':100,'max_page_pixels':20000000,'preflight_seconds':30,'child_seconds':540},
    'scope':'local synthetic native fixture; no image/model package upgrade or capacity qualification'},indent=2))
files={str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json'}
(OUT/'manifest.json').write_text(json.dumps({'producer':producer,'files':files},indent=2))
