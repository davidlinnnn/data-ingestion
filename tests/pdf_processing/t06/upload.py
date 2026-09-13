"""Local verification bootstrap: version sources and freeze operator review policy."""
import json,hashlib
from pathlib import Path
import boto3
s3=boto3.client('s3',endpoint_url='http://objects:9000')
profile=json.loads(Path('/driver/native-v1.json').read_text())
profile['content_evidence']={'version':'typed-source-evidence-v1','reviews':{}}
items=json.loads(Path('/tmp/t06-fixtures/manifest.json').read_text())
for x in items:
    sid=x['id'];original=Path('/tmp/t06-originals')/(sid+'.pdf')
    assert hashlib.sha256(original.read_bytes()).hexdigest()==x['original_sha256']
    key='final/sources/original-'+sid+'.pdf';saved=s3.put_object(Bucket='t06',Key=key,Body=original.read_bytes())
    x['review']['original_source']={'source_revision':x['source_revision'],'artifact':{'key':key,'name':sid+'.pdf',
        'version_id':saved['VersionId'],'sha256':x['original_sha256']}}
    profile['content_evidence']['reviews'][x['review']['source_sha256']]=x['review']
Path('/tmp/t06-profile.json').write_text(json.dumps(profile,indent=2))
print('Frozen five reviewed source policies with versioned originals')
