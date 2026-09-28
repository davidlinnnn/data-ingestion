"""Version private sources in the isolated store and freeze source reviews."""
import json
from pathlib import Path
import boto3
from pdf_processing.object_store import digest
s3 = boto3.client('s3', endpoint_url='http://objects:9000')
try: s3.create_bucket(Bucket='t09a')
except s3.exceptions.BucketAlreadyOwnedByYou: pass
s3.put_bucket_versioning(Bucket='t09a',VersioningConfiguration={'Status':'Enabled'})
profile = json.loads(Path('/driver/native-v1.json').read_text())
profile['group_pages'] = 5
profile['content_evidence'] = {'version':'typed-source-evidence-v1','reviews':{}}
for entry in json.loads(Path('/tmp/t09a-fixtures/manifest.json').read_text()):
    sid = entry['id']; data = Path('/tmp/t09a-originals',sid+'.pdf').read_bytes()
    assert digest(data) == entry['original_sha256']
    key = 'final/sources/original-'+sid+'.pdf'
    saved = s3.put_object(Bucket='t09a',Key=key,Body=data)
    review = entry['review']
    review['original_source'] = {'source_revision':entry['source_revision'],'artifact':{'key':key,'name':sid+'.pdf','version_id':saved['VersionId'],'sha256':digest(data)}}
    profile['content_evidence']['reviews'][review['source_sha256']] = review
Path('/tmp/t09a-profile.json').write_text(json.dumps(profile,indent=2))
