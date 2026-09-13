"""Test-only faults around real Processing, Docling and S3; never deployment code."""
import asyncio
import json
import os
from pathlib import Path
import runpy
import time

from pdf_processing.execution import Execution
from pdf_processing.object_store import Store

original_publish=Store.publish
original_child=Execution.child

def control(store):
    raw=store.get(store.prefix+'control.json')
    return json.loads(raw) if raw else {}

def marker(store,case,event,**extra):
    return store.put_once(store.prefix+'faults/'+case+'/'+event+'.json',
        json.dumps({'event':event,'pod':os.environ.get('HOSTNAME'),'at':time.time(),**extra}).encode())

async def child(self,module,request,out):
    c=await asyncio.to_thread(control,self.store)
    capture=module=='pdf_processing.parse' and request.get('mode')=='capture'
    if capture:
        await asyncio.to_thread(marker,self.store,c.get('case','normal'),
            'capture-'+str(request['start'])+'-'+os.environ.get('HOSTNAME','local'),start=request['start'])
    if capture and request['start']==6 and c.get('mode')=='processing' and await asyncio.to_thread(
            marker,self.store,c['case'],'claimed'):
        # Start real native processing; record an observed completed page stage
        # before requesting Pod kill. Do not substitute a stage-entry-only pause.
        task=asyncio.create_task(original_child(self,module,request,out))
        while not task.done():
            log=out/'process.log'
            if log.exists() and 'PagePreprocessingModel' in log.read_text(errors='replace'):
                await asyncio.to_thread(marker,self.store,c['case'],'ready',kind='native_stage_observed')
                break
            await asyncio.sleep(.02)
        await task
        # Prevent publication if tiny fixture finished before the external killer.
        while True: await asyncio.sleep(1)
    return await original_child(self,module,request,out)

def publish(self,operation,files,after_upload=None,after_register=None):
    c=control(self)
    attribution=json.loads(files.get('attribution.json',b'{}'))
    op=attribution.get('operation',{})
    target=op.get('kind')=='group' and op.get('start')==6 and c.get('mode') in ('upload','ack')
    claimed=target and marker(self,c['case'],'claimed')
    def pause(event):
        marker(self,c['case'],'ready',kind=event)
        while True: time.sleep(1)
    if claimed:
        if c['mode']=='upload': after_upload=lambda _:pause('payload_uploaded_before_registration')
        else: after_register=lambda:pause('registered_before_activity_ack')
    return original_publish(self,operation,files,after_upload,after_register)

Execution.child=child
Store.publish=publish
runpy.run_path('/driver/worker.py',run_name='__main__')
