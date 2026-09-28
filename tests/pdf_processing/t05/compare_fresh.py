"""Read-only comparison with retained T02 fresh-interpreter output, not a new oracle."""
import hashlib,json
from pathlib import Path
import boto3
from pdf_processing.object_store import Store

old=Store(boto3.client('s3',endpoint_url='http://objects.pdf-t02-validation.svc.cluster.local:9000'),'t02','qualified')
new=Store(boto3.client('s3',endpoint_url='http://objects:9000'),'t05','qualified-v3')
prior_operation='7f545f76f78d3681d9c51cbc7928d48b9bcb5597bc5984dd7d98a4d53ea2174d'
current=json.loads(Path('/tmp/t05-run/native.json').read_text())['native-review.pdf']['steps'][-1]['operation']
def document(store,operation):
    manifest=store.resolve(operation)
    assert manifest is not None
    item=next(f for f in manifest['files'] if f['name']=='document.json')
    return store.get(item['key'])
a,b=document(old,prior_operation),document(new,current)
assert json.loads(a)==json.loads(b)
record={'fresh_baseline':'T02 e09f23e retained qualified registration','fresh_operation':prior_operation,'warm_operation':current,'full_json_equal':True,'fresh_sha256':hashlib.sha256(a).hexdigest(),'warm_sha256':hashlib.sha256(b).hexdigest()}
Path('/tmp/t05-run/distinct-fresh-comparison.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record))
