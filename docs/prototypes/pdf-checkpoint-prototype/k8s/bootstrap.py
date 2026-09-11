"""Establish new pinned Linux evidence; publish baseline references to real S3."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import boto3
from object_store import Store

ROOT=Path(__file__).resolve().parent.parent
CLIENT=boto3.client('s3',endpoint_url=os.environ.get('S3_ENDPOINT','http://objects:9000'))
BUCKET='pdf-prototype'
try:
    CLIENT.create_bucket(Bucket=BUCKET)
except CLIENT.exceptions.BucketAlreadyOwnedByYou:
    pass
prefix=os.environ.get('PDF_STORE_PREFIX','linux-v1')
store=Store(CLIENT,BUCKET,prefix)
base=ROOT/'PROTOTYPE-wipe-me'/'linux-baseline'
base.mkdir(parents=True,exist_ok=True)
for label,name,flags in [('native','llm-survey-2303.18223v1.pdf',[]),('scan','scan-pages-3-5.pdf',['--scan'])]:
    for mode in ('baseline','capture','restore'):
        out=base/f'{label}-{mode}'
        args=[sys.executable,str(ROOT/'experiment.py'),mode,str(ROOT/'fixtures'/name),'--out',str(out),*flags]
        if mode=='capture':
            args+=['--crash-before-assembly']
        if mode=='restore':
            args+=['--checkpoint',str(base/f'{label}-capture')]
        start=time.perf_counter()
        with (base/f'{label}-{mode}.log').open('w') as log:
            result=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT)
        assert result.returncode == (73 if mode=='capture' else 0), f'Inspect {label}-{mode}.log'
        print(json.dumps({'fixture':label,'mode':mode,'process_seconds':time.perf_counter()-start}),flush=True)
    subprocess.run([sys.executable,str(ROOT/'compare.py'),str(base/f'{label}-baseline'),str(base/f'{label}-restore'),'--out',str(base/f'{label}-comparison.json')],check=True)
for name in ('method.json','document.json'):
    assert store.put_once(prefix+'/baseline/'+name,(base/'native-baseline'/name).read_bytes())
print(json.dumps({'baseline':str(base),'io':store.io}),flush=True)
