import json,hashlib
from pathlib import Path
import boto3
from pdf_processing.object_store import Store
s=Store(boto3.client('s3',endpoint_url='http://objects:9000'),'t02','qualified')
reports=json.loads(Path('/tmp/t02-qualified/native.json').read_text())
local={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/app/pdf_processing').glob('*.py')}
checks={}
for name,report in reports.items():
    manifest=s.resolve(report['plan']); ref=next(f for f in manifest['files'] if f['name']=='plan.json')
    plan=json.loads(s.get(ref['key'])); assert plan['producer']==local
    checks[name]={'producer_hashes_match':True,'producer':plan['producer'],'profile_id':plan['profile']['id'], 'pages':plan['pages']}
Path('/tmp/t02-qualified/attribution.json').write_text(json.dumps(checks,indent=2))
print('Stored producer attribution matches the final mounted code')
