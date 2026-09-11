"""Reproducible matched matrix; real parsers, S3 and Temporal, sequential only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import boto3
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'k8s'))
from object_store import Store
S3=boto3.client('s3',endpoint_url='http://objects:9000')
BUCKET='pdf-prototype'
try:S3.create_bucket(Bucket=BUCKET)
except S3.exceptions.BucketAlreadyOwnedByYou:pass
OUT=ROOT/'PROTOTYPE-wipe-me'/'performance-matrix'
OUT.mkdir(parents=True,exist_ok=True)
REF=Path('/reference')
index=json.loads((OUT/'index.json').read_text()) if (OUT/'index.json').exists() else []

def run(args,out,env=None):
    out.mkdir(parents=True,exist_ok=True)
    began=time.perf_counter()
    with (out/'process.log').open('w') as f:
        p=subprocess.run([sys.executable,*map(str,args)],env={**os.environ,**(env or {})},stdout=f,stderr=subprocess.STDOUT)
    assert p.returncode==0, f'Failed trial: {out}/process.log'
    return time.perf_counter()-began

for label,pdf,count,size,flags in [('scan','scan-pages-3-5.pdf',2,1,['--scan']),('native','llm-survey-2303.18223v1.pdf',51,5,[])]:
    baseline=json.loads((REF/(label+'-baseline')/'document.json').read_text())
    # Cache warmup is excluded; timed cold means fresh process/converter, not cold disk.
    if not (OUT/(label+'-warmup')/'perf.json').exists(): run([ROOT/'performance/entry.py','baseline',ROOT/'fixtures'/pdf,'--out',OUT/(label+'-warmup'),'--end',min(count,10),*flags],OUT/(label+'-warmup'))
    for repetition,order in enumerate([['whole','direct','temporal','warm'],['warm','temporal','direct','whole'],['whole','temporal','warm','direct']]):
        for mode in order:
            name=f'{label}-{repetition}-{mode}'
            out=OUT/name
            if any(x['fixture']==label and x['repetition']==repetition and x.get('variant',Path(x['out']).name.rsplit('-',1)[1])==mode for x in index): continue
            if mode=='whole':
                elapsed=run([ROOT/'performance/entry.py','baseline',ROOT/'fixtures'/pdf,'--out',out,*flags],out)
                assert json.loads((out/'document.json').read_text())==baseline
                info={'wall_s':elapsed,'scope':'whole parsing+assembly+JSON/Markdown export; no enrichment'}
            else:
                prefix='perf-'+name+'-'+uuid.uuid4().hex[:8]
                store=Store(S3,BUCKET,prefix)
                for file in ('method.json','document.json'):
                    assert store.put_once(prefix+'/baseline/'+file,(REF/(label+'-baseline')/file).read_bytes())
                env={'PDF_STORE_PREFIX':prefix,'PDF_NAME':pdf,'PAGE_COUNT':str(count),'PDF_SCAN':'1' if label=='scan' else '0','GROUP_SIZE':str(size),'REUSE_MODE':'warm' if mode=='warm' else 'cold','POLL_MODE':'legacy'}
                elapsed=run([ROOT/'performance/grouped.py','temporal' if mode=='temporal' else 'direct',out],out,env)
                info=json.loads((out/'result.json').read_text());info['launcher_wall_s']=elapsed
                # Preserve only small accepted diagnostics; large source artifacts stay in the store for this disposable test.
                diagnostics=[]
                for page in S3.get_paginator('list_objects_v2').paginate(Bucket=BUCKET,Prefix=prefix+'/registered/'):
                    for obj in page.get('Contents',[]):
                        reg=json.loads(S3.get_object(Bucket=BUCKET,Key=obj['Key'])['Body'].read())
                        data={'operation':reg['operation']}
                        for file in reg['files']:
                            if file['name'] in ('perf.json','metrics.json'):
                                raw=S3.get_object(Bucket=BUCKET,Key=file['key'])['Body'].read()
                                assert hashlib.sha256(raw).hexdigest()==file['sha256']
                                data[file['name']]=json.loads(raw)
                        diagnostics.append(data)
                (out/'child-diagnostics.json').write_text(json.dumps(diagnostics,indent=2))
                # Test fixtures are complete after evidence; remove only this trial's prefix to bound PVC use.
                keys=[]
                for page in S3.get_paginator('list_objects_v2').paginate(Bucket=BUCKET,Prefix=prefix+'/'):
                    keys += [{'Key':o['Key']} for o in page.get('Contents',[])]
                for offset in range(0,len(keys),1000):S3.delete_objects(Bucket=BUCKET,Delete={'Objects':keys[offset:offset+1000]})
            row={**info,'fixture':label,'repetition':repetition,'variant':mode,'out':str(out)}
            index.append(row);(OUT/'index.json').write_text(json.dumps(index,indent=2))
            print(json.dumps(row),flush=True)
print('MATRIX_COMPLETE',flush=True)
