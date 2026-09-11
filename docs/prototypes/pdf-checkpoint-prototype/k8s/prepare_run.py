"""Create a fresh run prefix from an existing baseline; task queue must be isolated."""
import os
import sys
import boto3
from object_store import Store
source, target = sys.argv[1:3]
assert source != target and target
client=boto3.client('s3',endpoint_url=os.environ.get('S3_ENDPOINT','http://objects:9000'))
existing=client.list_objects_v2(Bucket='pdf-prototype',Prefix=target.rstrip('/')+'/',MaxKeys=1)
assert not existing.get('Contents'), 'Refuse to contaminate an existing trial prefix'
store=Store(client,'pdf-prototype',target)
for name in ('method.json','document.json'):
    data=client.get_object(Bucket='pdf-prototype',Key=source.rstrip('/')+'/baseline/'+name)['Body'].read()
    assert store.put_once(target.rstrip('/')+'/baseline/'+name,data)
print('Prepared',target,'Use a dedicated task queue and matched worker/client environment.')
