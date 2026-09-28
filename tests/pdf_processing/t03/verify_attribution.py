"""Verify accepted plan and execution identities against mounted qualified code."""
import hashlib
import json
from pathlib import Path
import sys
import boto3
from pdf_processing.object_store import Store

store=Store(boto3.client('s3',endpoint_url='http://objects:9000'),'t03','final')
expected={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/app/pdf_processing').glob('*.py')}
def artifact(operation,name):
    saved=store.resolve(operation);assert saved is not None
    return json.loads(store.read_artifact(next(i for i in saved['files'] if i['name']==name)))
results=[]
for arg in sys.argv[1:]:
    value=json.loads(Path(arg).read_text())
    results.extend([value['result']] if 'result' in value else value.values())
count=0
for result in results:
    plan=artifact(result['plan'],'plan.json')
    assert plan['producer']==expected
    for step in result['steps']:
        assert artifact(step['operation'],'attribution.json')['producer']==expected
        count+=1
print(json.dumps({'producer':expected,'verified_plans':len(results),'verified_operations':count},indent=2))
