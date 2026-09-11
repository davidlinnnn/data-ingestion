"""Causal polling ablation over actual frozen parser outputs; no parsing/Temporal."""
import asyncio
import json
from pathlib import Path
import sys
import time
import uuid
import boto3
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'k8s'))
from object_store import Store
S3=boto3.client('s3',endpoint_url='http://objects:9000')
FIX=Path('/pub-fixture')
OUT=ROOT/'PROTOTYPE-wipe-me/performance-publication'
OUT.mkdir(parents=True,exist_ok=True)

async def main():
    trials=[]
    for rep,order in enumerate([['legacy','immediate'],['immediate','legacy'],['legacy','immediate']]):
        for mode in order:
            prefix='publication-'+uuid.uuid4().hex
            store=Store(S3,'pdf-prototype',prefix)
            rows=[];began=time.perf_counter()
            for folder in sorted(FIX.iterdir()):
                started=time.perf_counter()
                files={str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob('*') if p.is_file()}
                read_s=time.perf_counter()-started
                async def publish():
                    before=time.perf_counter()
                    result=await asyncio.to_thread(store.publish,folder.name,files)
                    return time.perf_counter()-before,time.perf_counter(),result
                task=asyncio.create_task(publish())
                while not task.done():
                    if mode=='legacy':await asyncio.sleep(1)
                    else:await asyncio.wait({task},timeout=1)
                work_s,completed,result=await task
                rows.append({'read_payload_s':read_s,'publish_until_complete_s':work_s,'completion_to_observation_s':time.perf_counter()-completed,'bytes':sum(map(len,files.values())),'files':len(result['files'])})
            trial={'repetition':rep,'mode':mode,'wall_s':time.perf_counter()-began,'io':dict(store.io),'operations':rows}
            trials.append(trial)
            (OUT/'results.json').write_text(json.dumps(trials,indent=2));print(json.dumps({k:v for k,v in trial.items() if k!='operations'}),flush=True)
            keys=[]
            for page in S3.get_paginator('list_objects_v2').paginate(Bucket='pdf-prototype',Prefix=prefix+'/'):
                keys += [{'Key':o['Key']} for o in page.get('Contents',[])]
            S3.delete_objects(Bucket='pdf-prototype',Delete={'Objects':keys})
asyncio.run(main())
