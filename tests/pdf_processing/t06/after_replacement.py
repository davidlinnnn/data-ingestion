"""Fresh consumer and replayed accepted requests after external Activity Pod replacement."""
import asyncio,io,json,uuid
from pathlib import Path
import boto3
from PIL import Image
from temporalio.client import Client
from pdf_processing.object_store import Store,digest
from pdf_processing.processing_workflow import PDFProcessing
async def main():
 s3=boto3.client('s3',endpoint_url='http://objects:9000');store=Store(s3,'t06','final');client=await Client.connect('temporal:7233');root=Path('/tmp/t06-results');results={}
 def read(op,name):return store.read_artifact(next(f for f in store.resolve(op)['files'] if f['name']==name))
 for sid,case in json.loads((root/'summary.json').read_text()).items():
  final=json.loads(read(case['result']['processing_result'],'processing-result.json'));report=json.loads(read(final['content_evidence'],'content-evidence.json'))
  assert digest(read(final['assembly'],'document.json'))==report['document_sha256']
  for file in store.resolve(final['content_evidence'])['files']:store.read_artifact(file)
  crops=0
  for region in [g for x in report['formula_occurrences']+report['representation_observations'] for g in x['regions']]:
   raw=read(final['content_evidence'],region['page_artifact']);assert digest(raw)==region['page_sha256']
   with Image.open(io.BytesIO(raw)) as page:
    image=page.crop(region['crop_recipe']['box_pixels']);assert min(image.size)>0
    assert image.convert('L').getextrema()[0]<240 # actual nonblank readable pixels retained
    image.close();crops+=1
  handle=await client.start_workflow(PDFProcessing.run,{'request':case['request'],'activity_queue':'t06-pdf'},id=uuid.uuid4().hex,task_queue='t06-workflows')
  result=await handle.result();assert result['status']=='complete',result
  assert result['processing_result']==case['result']['processing_result']
  assert all(s['reused'] for s in result['steps']),result
  results[sid]={'workflow_id':handle.id,'identical_final_registration':True,'all_group_assembly_ocr_reused':True,'readable_evidence_crops':crops,'checked_artifacts':len(store.resolve(final['content_evidence'])['files'])}
  print(sid,'replacement retrieval and complete reuse passed',flush=True)
 (root/'replacement.json').write_text(json.dumps(results,indent=2))
asyncio.run(main())
