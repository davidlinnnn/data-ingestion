"""Test-only fault adapter at external Activity/publication seam, never shipped."""
import os,json
from temporalio import activity
from temporalio.exceptions import ApplicationError
from pdf_processing.object_store import Store
from pdf_processing.processing import Processing

original_publish=Store.publish
fired=set()
def publish(self,operation,files,*args,**kwargs):
    result=original_publish(self,operation,files,*args,**kwargs)
    marker=next((name for name in ('document.json','ocr.json','processing-result.json') if name in files),None)
    if marker == 'document.json' and json.loads(files.get('attribution.json', b'{}')).get('operation', {}).get('kind') != 'assembly':
        marker = None
    if os.environ.get('T04_FAULT')=='lost_ack' and marker and marker not in fired:
        fired.add(marker)
        raise TimeoutError('test-only acknowledgement loss after durable registration')
    return result
Store.publish=publish
original_run=Processing.run
@activity.defn(name='pdf_processing_step_v1')
async def run(self,value):
    if os.environ.get('T04_FAULT')=='component_failure' and value.get('stage')=='component_ocr' and value['component']=='#/pictures/1':
        raise ApplicationError('injected_ocr_failure',{'category':'parser','code':'injected_ocr_failure'},type='parser')
    return await original_run(self,value)
Processing.run=run

import asyncio
import worker
asyncio.run(worker.main())
