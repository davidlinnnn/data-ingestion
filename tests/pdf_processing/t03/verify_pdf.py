"""Versioned PDF request to real workers; external runner kills marked fault Pod."""
import argparse
import asyncio
import json
from pathlib import Path
import uuid

import boto3
from temporalio.client import Client
from pdf_processing.object_store import Store, digest
from pdf_processing.processing_workflow import PDFProcessing

async def main(args):
    s3=boto3.client('s3',endpoint_url='http://objects:9000')
    store=Store(s3,'t03','final')
    client=await Client.connect('temporal:7233')
    c={'case':args.case,'mode':args.mode}
    s3.put_object(Bucket='t03',Key='final/control.json',Body=json.dumps(c).encode())
    s3.put_bucket_versioning(Bucket='t03',VersioningConfiguration={'Status':'Enabled'})
    data=Path('/tmp/native-ten.pdf').read_bytes()
    key='final/sources/native-ten.pdf'
    saved=s3.put_object(Bucket='t03',Key=key,Body=data)
    request={'version':1,'request_id':args.case,'profile':'native-v1','source_revision':'t03-ten:v1',
        'artifact':{'key':key,'version_id':saved['VersionId'],'sha256':digest(data),'name':'native-ten.pdf'}}
    async def run():
        handle=await client.start_workflow(PDFProcessing.run,{'request':request,'activity_queue':'t03-pdf'},
            id='t03-'+args.case+'-'+uuid.uuid4().hex,task_queue='t03-workflows')
        result=await handle.result()
        assert result['status']=='parsed_ready' and result['registered_pages']==10,result
        assert await handle.query(PDFProcessing.progress)==result
        return handle.id,result
    wid,result=await run()
    def artifact(operation,name):
        registered=store.resolve(operation); assert registered is not None
        return store.read_artifact(next(i for i in registered['files'] if i['name']==name))
    delivery=json.loads(artifact(result['parsed_result'],'parsed-result.json'))
    document=json.loads(artifact(delivery['assembly'],'document.json'))
    text=' '.join(item.get('text','') for item in document['texts'])
    for page in range(1,11): assert f'T03 recovery fixture page {page}' in text
    metrics=json.loads(artifact(delivery['assembly'],'metrics.json'))
    assert not any(v for k,v in metrics['page_stage_inputs'].items() if k.endswith('Model'))
    again,reused=await run()
    assert reused['parsed_result']==result['parsed_result']
    assert all(s['reused'] and s['storage']['put_bytes']==0 for s in reused['steps'])
    listing=s3.list_objects_v2(Bucket='t03',Prefix='final/faults/'+args.case+'/').get('Contents',[])
    markers=[]
    for item in listing:
        raw=store.get(item['Key']); assert raw is not None
        markers.append(json.loads(raw))
    starts=[m for m in markers if m['event'].startswith('capture-')]
    assert len([m for m in starts if m['start']==1])==1,starts
    assert len([m for m in starts if m['start']==6])==(1 if args.mode=='ack' else 2),starts
    print(json.dumps({'case':args.case,'mode':args.mode,'workflow':wid,'result':result,
        'reuse_workflow':again,'reuse':reused,'markers':markers,'inventory':store.inventory()},indent=2,default=str))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True);parser.add_argument('--mode',required=True)
    asyncio.run(main(parser.parse_args()))
