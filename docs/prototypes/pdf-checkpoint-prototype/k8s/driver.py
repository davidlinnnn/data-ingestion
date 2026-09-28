"""Start an actual Temporal trial and save history/evidence in the coordinator Pod."""
import asyncio
import json
import os
from pathlib import Path
import sys
import time
from temporalio.client import Client
from worker import Recovery, CLIENT, BUCKET, PREFIX

async def main():
    mode=sys.argv[1]
    client=await Client.connect(os.environ.get('TEMPORAL_ADDRESS','temporal:7233'))
    run_id=PREFIX+'-'+mode+'-'+str(time.time_ns())
    started=time.perf_counter()
    handle=await client.start_workflow(Recovery.run,mode=='fault',id=run_id,task_queue=os.environ.get('PDF_TASK_QUEUE','pdf-linux'))
    print(json.dumps({'workflow_id':run_id,'started':time.time()}),flush=True)
    result=await handle.result()
    out=Path('/experiment/PROTOTYPE-wipe-me')/('distributed-'+mode)
    out.mkdir(exist_ok=True)
    (out/'result.json').write_text(json.dumps({'mode':mode,'workflow_id':run_id,'wall_seconds':time.perf_counter()-started,'result':result},indent=2))
    (out/'history.json').write_text((await handle.fetch_history()).to_json())
    events=[]
    for page in CLIENT.get_paginator('list_objects_v2').paginate(Bucket=BUCKET,Prefix=PREFIX+'/ledger/'):
        for item in page.get('Contents',[]):
            events.append(json.loads(CLIENT.get_object(Bucket=BUCKET,Key=item['Key'])['Body'].read()))
    (out/'ledger.json').write_text(json.dumps(sorted(events,key=lambda v:v['time']),indent=2))
    print((out/'result.json').read_text(),flush=True)

if __name__=='__main__':
    asyncio.run(main())
