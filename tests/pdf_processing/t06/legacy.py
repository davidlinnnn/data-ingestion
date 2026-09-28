"""Versioned request -> real Temporal/store -> attributable complete result."""
import asyncio,json,uuid,os
from pathlib import Path
import boto3
from temporalio.client import Client
from pdf_processing.object_store import Store,digest
from pdf_processing.processing_workflow import PDFProcessing

async def main():
    s3=boto3.client('s3',endpoint_url='http://objects:9000')
    if not any(x['Name']=='t06' for x in s3.list_buckets()['Buckets']): s3.create_bucket(Bucket='t06')
    s3.put_bucket_versioning(Bucket='t06',VersioningConfiguration={'Status':'Enabled'})
    store=Store(s3,'t06','final');client=await Client.connect('temporal:7233')
    out=Path('/tmp/t06-legacy');out.mkdir(exist_ok=True)
    def read(operation,name):
        m=store.resolve(operation)
        return json.loads(store.get(next(i['key'] for i in m['files'] if i['name']==name)))
    reports={}
    for path in sorted(Path(os.environ.get('T04_FIXTURES','/fixtures')).glob('*.pdf')):
        data=path.read_bytes();key='final/sources/'+path.name
        saved=s3.put_object(Bucket='t06',Key=key,Body=data)
        req={'version':2,'completion':'required_picture_ocr_v1','request_id':'t04:'+uuid.uuid4().hex,
             'source_revision':'captured:'+path.name,'profile':'native-v1',
             'artifact':{'key':key,'name':path.name,'version_id':saved['VersionId'],'sha256':digest(data)}}
        results=[]
        for repeat in range(2):
            handle=await client.start_workflow(PDFProcessing.run,{'request':req,'activity_queue':'t06-pdf'},
                       id='t04-'+uuid.uuid4().hex,task_queue='t06-workflows')
            result=await handle.result();results.append(result)
            (out/(path.stem+'.json')).write_text(json.dumps({'request':req,'results':results},indent=2))
            if path.stem=='rotated':
                assert result['status']=='failed' and not result['processing_complete'], result
                assert result['error']=={'category':'integrity','code':'invalid_component_crop'},result
                reports[path.name]={'result':result}
                break
            assert result['status']=='complete',result
            assert result['processing_complete'] and not result['canonical_accepted']
            final=read(result['processing_result'],'processing-result.json')
            selection=read(final['selection'],'selection.json')
            ocr=[read(x['operation'],'ocr.json') for x in final['enrichments']]
            assert all(x['source']==req and x['parsed_result']==final['parsed_result'] for x in ocr)
            if path.stem=='none': assert not ocr
            if path.stem=='multiple':
                assert len(ocr)>=2,selection
                joined=' '.join(t for x in ocr for t in x['texts'])
                assert 'ALPHA' in joined and '12345' in joined and 'BETA' in joined and '67890' in joined,joined
            if path.stem=='blank': assert ocr and all(x['outcome']=='no_text_detected' for x in ocr),ocr
            if path.stem=='nccu-page3':
                joined=''.join(t for x in ocr for t in x['texts'])
                assert '我的專區' in joined and '最新公告' in joined,joined
            reports[path.name]={'result':result,'final':final,'selection':selection,'ocr':ocr}
        if path.stem=='rotated': continue
        assert results[0]['processing_result']==results[1]['processing_result']
        assert all(x['reused'] for x in results[1]['steps'])
    legacy = {**req, 'version':1, 'request_id':'legacy:'+uuid.uuid4().hex}
    legacy.pop('completion')
    legacy_result = await client.execute_workflow(PDFProcessing.run, {'request':legacy,'activity_queue':'t06-pdf'},
                        id='legacy-'+uuid.uuid4().hex,task_queue='t06-workflows')
    assert legacy_result['status']=='parsed_ready' and not legacy_result['processing_complete'], legacy_result
    reports['legacy'] = legacy_result
    (out/'results.json').write_text(json.dumps(reports,indent=2))
    print('complete result, attribution, empty selection/no-text, multiple images and reuse passed',flush=True)

asyncio.run(main())
