"""One bounded existing TC screenshot fixture, no broad language qualification."""
import asyncio,json,uuid
from pathlib import Path
import boto3
from temporalio.client import Client
from pdf_processing.object_store import Store,digest
from pdf_processing.processing_workflow import PDFProcessing
async def main():
 s3=boto3.client('s3',endpoint_url='http://objects:9000');store=Store(s3,'t06','final');client=await Client.connect('temporal:7233')
 def read(op,name):return store.read_artifact(next(f for f in store.resolve(op)['files'] if f['name']==name))
 data=Path('/tmp/nccu-page3.pdf').read_bytes();key='final/sources/nccu-page3.pdf';saved=s3.put_object(Bucket='t06',Key=key,Body=data)
 request={'version':3,'completion':'required_evidence_v1','profile':'native-v1','request_id':uuid.uuid4().hex,'source_revision':'prior-S2-NCCU-physical-page-3','artifact':{'key':key,'name':'nccu-page3.pdf','sha256':digest(data),'version_id':saved['VersionId']}}
 result=await client.execute_workflow(PDFProcessing.run,{'request':request,'activity_queue':'t06-pdf'},id=uuid.uuid4().hex,task_queue='t06-workflows')
 assert result['status']=='complete',result
 final=json.loads(read(result['processing_result'],'processing-result.json'));evidence=json.loads(read(final['content_evidence'],'content-evidence.json'))
 ocr=[json.loads(read(x['operation'],'ocr.json')) for x in final['enrichments']]
 joined=''.join(t for x in ocr for t in x['texts'])
 assert '我的專區' in joined and '最新公告' in joined
 assert all(x['source']==request and x['parsed_result']==final['parsed_result'] for x in ocr)
 assert evidence['formula_coverage']=='unreviewed' and evidence['retained_original'] is None
 assert digest(read(final['content_evidence'],'source.pdf'))==digest(data)
 Path('/tmp/t06-results/tc-supplement.json').write_text(json.dumps({'request':request,'result':result,'checks':{'two_reviewed_anchors':True,'durable_source':True,'ocr_attribution':True},'scope':'NCCU physical page 3 only; other historical TC evidence unchanged'} ,indent=2))
 print('TC NCCU page 3: required real OCR anchors and durable v3 source handoff passed',flush=True)
asyncio.run(main())
