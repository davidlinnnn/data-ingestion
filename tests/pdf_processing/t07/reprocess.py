"""Real request seam: deliberate reprocessing must reuse registered parse/assembly."""
import asyncio,json,uuid
from pathlib import Path
import boto3
from temporalio.client import Client
from pdf_processing.object_store import Store,digest
from pdf_processing.processing_workflow import PDFProcessing

async def main():
    s3=boto3.client('s3',endpoint_url='http://objects:9000')
    if not any(b['Name']=='t07' for b in s3.list_buckets()['Buckets']):s3.create_bucket(Bucket='t07')
    s3.put_bucket_versioning(Bucket='t07',VersioningConfiguration={'Status':'Enabled'})
    store=Store(s3,'t07','final')
    client=await Client.connect('temporal:7233')
    saved_path=Path('/tmp/t07-request.json')
    if saved_path.exists():
        request=json.loads(saved_path.read_text())
    else:
        data=Path('/fixtures/multiple.pdf').read_bytes();key='final/sources/multiple.pdf'
        saved=s3.put_object(Bucket='t07',Key=key,Body=data)
        request={'version':3,'completion':'required_evidence_v1','profile':'native-v1',
            'request_id':uuid.uuid4().hex,'source_revision':'synthetic:multiple',
            'artifact':{'key':key,'name':'multiple.pdf','sha256':digest(data),'version_id':saved['VersionId']}}
        saved_path.write_text(json.dumps(request))
    def read(identity,name):
        return json.loads(store.read_artifact(next(f for f in store.resolve(identity)['files'] if f['name']==name)))
    results=[]
    for _ in range(2):
        request={**request,'request_id':uuid.uuid4().hex}
        result=await client.execute_workflow(PDFProcessing.run,{'request':request,'activity_queue':'t07-pdf'},id=uuid.uuid4().hex,task_queue='t07-workflows')
        assert result['status']=='complete',result
        final=read(result['processing_result'],'processing-result.json')
        assert final['source']==request and not final['canonical_accepted']
        results.append(result)
    Path('/tmp/t07-reprocess.json').write_text(json.dumps(results,indent=2))
    assert all(s['reused'] for s in results[1]['steps'] if s['stage'] in ('group','assembly')),results[1]
    assert results[0]['parsed_result']!=results[1]['parsed_result']
    assert results[0]['processing_result']!=results[1]['processing_result']
    print('Distinct request bindings, reused actual parsing and assembly: PASS')

if __name__=='__main__':asyncio.run(main())
