"""Matched grouped direct/Temporal execution: same Activities, store and outputs; no OCR."""
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import time
import uuid
from types import SimpleNamespace
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.common import RetryPolicy
import worker as w
ROOT=Path(__file__).resolve().parent.parent

@workflow.defn(sandboxed=False)
class Performance:
    @workflow.run
    async def run(self,specs):
        groups=[]
        for spec in specs:
            groups.append(await workflow.execute_activity(w.produce,spec,start_to_close_timeout=timedelta(minutes=10),heartbeat_timeout=timedelta(seconds=15),retry_policy=RetryPolicy(maximum_attempts=1)))
        return await workflow.execute_activity(w.produce,{'kind':'assembly','groups':groups},start_to_close_timeout=timedelta(minutes=10),heartbeat_timeout=timedelta(seconds=15),retry_policy=RetryPolicy(maximum_attempts=1))

async def main():
    mode=sys.argv[1]
    out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
    size=int(os.environ.get('GROUP_SIZE','5'))
    specs=[{'kind':'group','start':n,'end':min(w.PAGE_COUNT,n+size-1)} for n in range(1,w.PAGE_COUNT+1,size)]
    warmup_s=0
    daemon=None
    original_child=w.child
    if os.environ.get('REUSE_MODE')=='warm':
        daemon=await asyncio.create_subprocess_exec(str(ROOT/'.venv/bin/python'),str(ROOT/'performance/entry.py'),'--daemon',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
        async def warm_child(args,output,fault,identity):
            if args[0]!='capture': return await original_child(args,output,fault,identity)
            argv=list(map(str,args))+(['--scan'] if w.SCAN else [])
            daemon.stdin.write((json.dumps(argv)+'\n').encode());await daemon.stdin.drain()
            with (output/'process.log').open('wb') as log:
                while True:
                    line=await daemon.stdout.readline()
                    if not line: raise RuntimeError('Warm converter exited before response; inspect process.log')
                    log.write(line)
                    if line.startswith(b'PERF_READY '): break
        w.child=warm_child
        warmout=Path('/tmp')/('perf-warmup-'+str(uuid.uuid4()));warmout.mkdir()
        started=time.perf_counter()
        await warm_child(['capture',w.PDF,'--out',warmout,'--start',1,'--end',min(w.PAGE_COUNT,size),'--checkpoint-only'],warmout,'','warmup')
        warmup_s=time.perf_counter()-started
    if mode=='direct':
        # Only SDK execution context differs. The actual Activity code/storage/child work is unchanged.
        w.activity.info=lambda:SimpleNamespace(attempt=1)
        w.activity.heartbeat=lambda *args:None
        began=time.perf_counter()
        groups=[await w.produce(spec) for spec in specs]
        result=await w.produce({'kind':'assembly','groups':groups})
    else:
        client=await Client.connect('temporal:7233')
        queue='perf-'+w.PREFIX
        async with Worker(client,task_queue=queue,workflows=[Performance],activities=[w.produce],max_concurrent_activities=1):
            began=time.perf_counter()
            handle=await client.start_workflow(Performance.run,specs,id=queue,task_queue=queue)
            result=await handle.result()
            (out/'history.json').write_text((await handle.fetch_history()).to_json())
    elapsed=time.perf_counter()-began
    if daemon:
        daemon.stdin.close();await daemon.wait()
        assert daemon.returncode==0
    ledger=[]
    for page in w.CLIENT.get_paginator('list_objects_v2').paginate(Bucket=w.BUCKET,Prefix=w.PREFIX+'/ledger/'):
        for item in page.get('Contents',[]):ledger.append(json.loads(w.CLIENT.get_object(Bucket=w.BUCKET,Key=item['Key'])['Body'].read()))
    (out/'ledger.json').write_text(json.dumps(sorted(ledger,key=lambda x:x['time']),indent=2))
    (out/'result.json').write_text(json.dumps({'mode':mode,'poll':w.POLL,'pages':w.PAGE_COUNT,'group_size':size,'scan':w.SCAN,'wall_s':elapsed,'warmup_s':warmup_s,'reuse_mode':os.environ.get('REUSE_MODE','cold'),'prefix':w.PREFIX,'result':result,'io':w.STORE.io},indent=2))
    print((out/'result.json').read_text(),flush=True)

if __name__=='__main__':asyncio.run(main())
