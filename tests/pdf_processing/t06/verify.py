"""Observe versioned PDF processing only through durable final-result references."""
import asyncio,json,uuid
from pathlib import Path
import boto3
from temporalio.client import Client
from pdf_processing.object_store import Store,digest
from pdf_processing.processing_workflow import PDFProcessing

async def main():
    s3=boto3.client('s3',endpoint_url='http://objects:9000')
    if not any(b['Name']=='t06' for b in s3.list_buckets()['Buckets']):s3.create_bucket(Bucket='t06')
    s3.put_bucket_versioning(Bucket='t06',VersioningConfiguration={'Status':'Enabled'})
    data=Path('/fixtures/multiple.pdf').read_bytes();key='final/sources/multiple.pdf'
    saved=s3.put_object(Bucket='t06',Key=key,Body=data)
    request={'version':3,'completion':'required_evidence_v1','profile':'native-v1',
        'request_id':uuid.uuid4().hex,'source_revision':'synthetic:multiple',
        'artifact':{'key':key,'name':'multiple.pdf','sha256':digest(data),'version_id':saved['VersionId']}}
    client=await Client.connect('temporal:7233')
    result=await client.execute_workflow(PDFProcessing.run,{'request':request,'activity_queue':'t06-pdf'},id=uuid.uuid4().hex,task_queue='t06-workflows')
    assert result['status']=='complete',result
    store=Store(s3,'t06','final')
    def read(identity,name):
        manifest=store.resolve(identity)
        return json.loads(store.read_artifact(next(f for f in manifest['files'] if f['name']==name)))
    final=read(result['processing_result'],'processing-result.json')
    handoff=read(final['content_evidence'],'content-evidence.json')
    assert handoff['source']==request and handoff['parsed_result']==final['parsed_result']
    assert len([n for n in handoff['items'] if n['actual_type']=='picture'])>=2
    assert handoff['formula_coverage']=='unreviewed'
    assert not final['canonical_accepted']
    print('v3 durable typed-content references passed')
if __name__=='__main__':asyncio.run(main())
