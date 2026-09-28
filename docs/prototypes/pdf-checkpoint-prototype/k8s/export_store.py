"""Preserve all isolated object-store artifacts to coordinator scratch before cleanup."""
import json
import os
from pathlib import Path
import boto3
client=boto3.client('s3',endpoint_url='http://objects:9000')
out=Path('/experiment/PROTOTYPE-wipe-me/shared-store-export')
index=[]
for page in client.get_paginator('list_objects_v2').paginate(Bucket='pdf-prototype'):
    for item in page.get('Contents',[]):
        key=item['Key']
        assert not key.startswith('/') and '..' not in key.split('/')
        target=out/key
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(client.get_object(Bucket='pdf-prototype',Key=key)['Body'].read())
        index.append({'key':key,'bytes':item['Size']})
(out/'index.json').write_text(json.dumps(index,indent=2))
print(json.dumps({'objects':len(index),'bytes':sum(x['bytes'] for x in index),'path':str(out)}))
