import hashlib,json,importlib.metadata
from pathlib import Path
import boto3
from pdf_processing.object_store import Store
root=Path('/tmp/t06-results');store=Store(boto3.client('s3',endpoint_url='http://objects:9000'),'t06','final')
case=json.loads((root/'summary.json').read_text())['09'];identity=case['result']['plan']
entry=next(f for f in store.resolve(identity)['files'] if f['name']=='plan.json');plan=json.loads(store.read_artifact(entry))
result={'producer':plan['producer'],'profile':plan['profile'],'limits':plan['limits'],
 'packages':{p:importlib.metadata.version(p) for p in ('docling','docling-core','pypdfium2','temporalio','boto3')},
 'package_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/app/pdf_processing').glob('*.py')},
 'baseline_sha256':{sid:hashlib.sha256((Path('/tmp/t06-fresh')/sid/'document.json').read_bytes()).hexdigest() for sid in ('06','07','08','09','10')}}
(root/'runtime.json').write_text(json.dumps(result,indent=2))
