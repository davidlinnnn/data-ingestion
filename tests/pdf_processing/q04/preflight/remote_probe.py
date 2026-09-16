"""Read-only coordinator probe. EXPECTED is supplied over stdin by the caller."""
import asyncio
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import time
import urllib.request
from typing import Any


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def fields(path):
    return {s.split()[0].rstrip(':'):int(s.split()[1]) for s in Path(path).read_text().splitlines()}


def sample():
    return {'time':time.time(),'meminfo':fields('/proc/meminfo'),'oom_kill':fields('/proc/vmstat')['oom_kill'],
        'memory_current':int(Path('/sys/fs/cgroup/memory.current').read_text()),
        'memory_events':fields('/sys/fs/cgroup/memory.events'),
        'memory_pressure':Path('/proc/pressure/memory').read_text(),'cpu_pressure':Path('/proc/pressure/cpu').read_text(),
        'loadavg':os.getloadavg()}


def inventory(expected):
    cache=Path('/experiment/PROTOTYPE-wipe-me/hf')
    packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
    models={str(p.relative_to(cache)):digest(p) for p in cache.glob('hub/models--*/snapshots/**/*') if p.is_file()}
    rapid=Path(str(importlib.metadata.distribution('rapidocr').locate_file('rapidocr/models')))
    models.update({'rapidocr/'+p.name:digest(p) for p in rapid.glob('*.onnx')})
    method=expected['profile']['method']
    def diff(a,b):return {k:{'expected':a.get(k),'actual':b.get(k)} for k in a.keys()|b.keys() if a.get(k)!=b.get(k)}
    roots=['/app/pdf_processing','/tmp/q03-20260916-d/src/pdf_processing']
    profile=Path('/tmp/q03-20260916-d/inputs/profile.json')
    prior=json.loads(profile.read_text())
    import psutil
    processes=[]
    for p in psutil.process_iter(['pid','ppid','name','memory_info','create_time']):
        args=p.cmdline()
        category=next((s for s in ('pdf_processing.warm_child','pdf_processing.parse','q04','q03','supervise.py') if any(s in a for a in args)),None)
        if category:processes.append({'pid':p.pid,'ppid':p.ppid(),'category':category,'rss':p.memory_info().rss,'created':p.create_time()})
    return {'time':time.time(),'python':platform.python_version(),'platform':platform.platform(),
        'python_matches':platform.python_version()==method['python'],'platform_matches':platform.platform()==method['platform'],
        'packages':packages,'package_differences':diff(method['packages'],packages),
        'models':models,'model_differences':diff(method['model_artifacts'],models),'model_cache':str(cache),
        'producer_differences':{root:diff(expected['producer'],{p.name:digest(p) for p in Path(root).glob('*.py')}) for root in roots},
        'retained_profile':{'path':str(profile),'sha256':digest(profile),'method_matches':prior['method']==method,
            'group_pages':prior['group_pages'],'release':prior.get('release')},
        'cgroup':{p:Path('/sys/fs/cgroup',p).read_text() for p in ('memory.max','memory.high','memory.swap.max','cpu.max','cpu.stat')},
        'proc_cgroup':Path('/proc/self/cgroup').read_text(),'disk':dict(zip(('total','used','free'),shutil.disk_usage('/tmp'))),
        'processes':processes,'proposed_path_exists':Path(expected['run_root']).exists(),
        'safe_environment':{k:os.environ.get(k) for k in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','OMP_NUM_THREADS','PYTHONDONTWRITEBYTECODE')},
        'tools':{k:shutil.which(k) for k in ('kubectl','docker','timeout','git')}}


async def services(expected):
    from temporalio.client import Client
    import boto3
    result=[]
    names=['pdf-integration-0913','pdf-s1-warm-lifecycle']+[f'pdf-t{n:02}-validation' for n in range(1,9)]+['pdf-t09a-validation']
    for ns in names:
        row={'namespace':ns,'time':time.time()}
        try:
            async with asyncio.timeout(15):
                client=await Client.connect('temporal.'+ns+'.svc.cluster.local:7233')
                row['temporal_health']=await client.service_client.check_health()
                row['running']=[{'id':w.id,'run_id':w.run_id} async for w in client.list_workflows(query='ExecutionStatus="Running"')]
                row['query_status']='complete'
        except Exception as e:row['error']=type(e).__name__+': '+str(e)
        try:
            with urllib.request.urlopen('http://objects.'+ns+'.svc.cluster.local:9000/minio/health/ready',timeout=5) as response:
                row['object_ready']=response.status
        except Exception as e:row['object_error']=type(e).__name__
        result.append(row)
    s3=boto3.client('s3',endpoint_url='http://objects:9000')
    return {'namespaces':result,'bucket':'t09a','versioning':s3.get_bucket_versioning(Bucket='t09a').get('Status'),
        'proposed_prefix':expected['prefix'],'proposed_prefix_objects':s3.list_objects_v2(Bucket='t09a',Prefix=expected['prefix'],MaxKeys=1).get('KeyCount',0)}


async def main(expected):
    result: dict[str, Any]={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'READ_ONLY_NO_WORKFLOW_NO_INFERENCE_NO_MUTATION'}
    result['runtime']=inventory(expected)
    result['services']=await services(expected)
    result['samples']=[]
    for _ in range(31):
        result['samples'].append(sample())
        await asyncio.sleep(1)
    print(json.dumps(result))
