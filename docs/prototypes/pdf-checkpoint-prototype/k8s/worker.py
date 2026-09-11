"""THROWAWAY: real Temporal worker using shared immutable S3 artifacts."""
import asyncio
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import uuid
import boto3
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Worker
from object_store import Store, digest

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT/'.venv/bin/python'
PDF = ROOT/'fixtures/llm-survey-2303.18223v1.pdf'
BUCKET = 'pdf-prototype'
PREFIX = os.environ.get('PDF_STORE_PREFIX', 'linux-v1')
CLIENT = boto3.client('s3', endpoint_url=os.environ.get('S3_ENDPOINT', 'http://objects:9000'))
STORE = Store(CLIENT, BUCKET, PREFIX)
POD = os.environ.get('HOSTNAME', 'outside-pod')
METHOD = STORE.get(PREFIX + '/baseline/method.json')


def record(event, **data):
    value = {'event': event, 'time': time.time(), 'pod': POD, **data}
    STORE.put_once(PREFIX + '/ledger/' + str(uuid.uuid4()) + '.json', json.dumps(value).encode())
    print(json.dumps(value), flush=True)


def materialize(operation, out):
    manifest = STORE.resolve(operation)
    assert manifest is not None
    for item in manifest['files']:
        name = item['name']
        assert not name.startswith('/') and '..' not in name.split('/')
        p = out/name
        p.parent.mkdir(parents=True, exist_ok=True)
        data = STORE.get(item['key'])
        assert digest(data) == item['sha256']
        p.write_bytes(data)
    return manifest


def verify_group(out, start, end):
    data = json.loads((out/'complete.json').read_text())
    assert data['source_sha256'] == digest(PDF.read_bytes())
    assert data['method_sha256'] == digest(METHOD) == digest((out/'method.json').read_bytes())
    pages = []
    for item in data['pages']:
        p = out/'checkpoints'/item['file']
        assert digest(p.read_bytes()) == item['sha256']
        page = json.loads(p.read_text())
        assert page['method_sha256'] == data['method_sha256']
        assert page['source_sha256'] == data['source_sha256']
        assert digest((p.parent/page['visual']['file']).read_bytes()) == page['visual']['sha256']
        pages.append(page['page_no'])
    assert pages == list(range(start, end+1))
    return data


async def child(args, out, fault, identity):
    marker = out/'fault-marker'
    with (out/'process.log').open('wb') as log:
        p = await asyncio.create_subprocess_exec(str(PYTHON), str(ROOT/'k8s/fault_entry.py'), *map(str,args),
            stdout=log, stderr=log, start_new_session=True,
            env={**os.environ, 'PDF_FAULT': fault, 'PDF_FAULT_MARKER': str(marker)})
        try:
            marked = False
            while p.returncode is None:
                activity.heartbeat({'identity': identity, 'pid': p.pid})
                if marker.exists() and not marked:
                    record('fault_ready', identity=identity, point=marker.read_text(),
                        events=(out/'events.jsonl').read_text() if (out/'events.jsonl').exists() else '')
                    marked = True
                try:
                    await asyncio.wait_for(p.wait(), timeout=1)
                except asyncio.TimeoutError:
                    pass
            if p.returncode:
                raise RuntimeError(f'child exit {p.returncode}: {(out/"process.log").read_text()[-2500:]}')
        finally:
            if p.returncode is None:
                os.killpg(p.pid, signal.SIGKILL)
                await p.wait()


@activity.defn
async def produce(spec):
    attempt = activity.info().attempt
    core = {k:v for k,v in spec.items() if k != 'fault'}
    producer = {p: digest((ROOT/p).read_bytes()) for p in ['experiment.py', 'k8s/ocr_component.py', 'k8s/worker.py', 'k8s/fault_entry.py', 'k8s/object_store.py']}
    identity = digest(json.dumps({'spec':core, 'source':digest(PDF.read_bytes()), 'method':digest(METHOD), 'producer':producer}, sort_keys=True).encode())
    kind = spec['kind']
    began = time.perf_counter()
    io_before = dict(STORE.io)
    activity.heartbeat(identity)
    existing = await asyncio.to_thread(STORE.resolve, identity)
    if existing:
        record('reused', identity=identity, kind=kind, attempt=attempt, seconds=time.perf_counter()-began)
        return identity
    out = Path('/tmp')/('pdf-' + str(uuid.uuid4()))
    out.mkdir()
    record('started', identity=identity, kind=kind, attempt=attempt, spec=core)
    fault = spec.get('fault','') if attempt == 1 else ''
    if kind == 'group':
        await child(['capture',PDF,'--out',out,'--start',spec['start'],'--end',spec['end'],'--checkpoint-only'], out, fault, identity)
        verify_group(out,spec['start'],spec['end'])
    elif kind == 'assembly':
        merged=out/'merged'
        (merged/'checkpoints').mkdir(parents=True)
        manifest=None
        for group_id in spec['groups']:
            group=out/'inputs'/group_id
            await asyncio.to_thread(materialize,group_id,group)
            m=json.loads((group/'complete.json').read_text())
            if manifest is None:
                manifest={**m,'pages':[], 'confidence':{**m['confidence'],'pages':{}}}
            manifest['pages'] += m['pages']
            manifest['confidence']['pages'].update(m['confidence']['pages'])
            for p in (group/'checkpoints').iterdir():
                (merged/'checkpoints'/p.name).write_bytes(p.read_bytes())
        (merged/'complete.json').write_text(json.dumps(manifest))
        (merged/'method.json').write_bytes(METHOD)
        verify_group(merged,1,51)
        await child(['restore',PDF,'--checkpoint',merged,'--out',out],out,fault,identity)
        baseline=json.loads(STORE.get(PREFIX+'/baseline/document.json'))
        assert json.loads((out/'document.json').read_text()) == baseline, 'Linux baseline fidelity failed'
    elif kind == 'ocr':
        parsed=out/'inputs'/'parsed'
        await asyncio.to_thread(materialize,spec['parsed'],parsed)
        await child(['ocr',parsed/'document.json',PDF,out],out,fault,identity)
    else:
        raise ValueError(kind)
    files={str(p.relative_to(out)):p.read_bytes() for p in out.rglob('*') if p.is_file() and p.relative_to(out).parts[0] not in ('merged','inputs')}
    if fault == 'upload':
        def interrupted(key):
            record('fault_ready',identity=identity,point='after_one_shared_object_before_registration',
                   events=(out/'events.jsonl').read_text() if (out/'events.jsonl').exists() else '')
            # Main coroutine keeps heartbeating while this upload thread waits for Pod loss.
            while True:
                time.sleep(1)
        publish_task=asyncio.create_task(asyncio.to_thread(STORE.publish,identity,files,interrupted))
    else:
        publish_task=asyncio.create_task(asyncio.to_thread(STORE.publish,identity,files))
    upload_start=time.perf_counter()
    while not publish_task.done():
        activity.heartbeat(identity)
        await asyncio.sleep(1)
    await publish_task
    record('registered',identity=identity,kind=kind,attempt=attempt,
           seconds=time.perf_counter()-began,upload_seconds=time.perf_counter()-upload_start,
           payload_bytes=sum(map(len,files.values())),
           io_delta={k:STORE.io[k]-io_before[k] for k in io_before},
           events=(out/'events.jsonl').read_text() if (out/'events.jsonl').exists() else '',
           ocr=json.loads((out/'ocr.json').read_text()) if kind=='ocr' else None)
    if fault == 'ack':
        record('fault_ready',identity=identity,point='registered_before_activity_ack')
        while True:
            activity.heartbeat(identity)
            await asyncio.sleep(1)
    return identity


@workflow.defn(sandboxed=False)
class Recovery:
    @workflow.run
    async def run(self, faults):
        async def call(spec):
            return await workflow.execute_activity(produce,spec,
                start_to_close_timeout=timedelta(minutes=10),heartbeat_timeout=timedelta(seconds=15),
                retry_policy=RetryPolicy(initial_interval=timedelta(seconds=1),maximum_interval=timedelta(seconds=2),maximum_attempts=4))
        groups=[]
        for start in range(1,52,5):
            groups.append(await call({'kind':'group','start':start,'end':min(51,start+4),
                'fault': ('ack' if start==1 else 'parse' if start==6 else 'upload' if start==11 else '') if faults else ''}))
        parsed=await call({'kind':'assembly','groups':groups,'fault':'assembly' if faults else ''})
        ocr=await call({'kind':'ocr','parsed':parsed,'fault':'ocr' if faults else ''})
        return {'groups':groups,'parsed':parsed,'ocr':ocr}


async def main():
    assert METHOD, 'Run Linux bootstrap first'
    client=await Client.connect(os.environ.get('TEMPORAL_ADDRESS','temporal:7233'))
    async with Worker(client, task_queue=os.environ.get('PDF_TASK_QUEUE','pdf-linux'), workflows=[Recovery], activities=[produce],max_concurrent_activities=1):
        await asyncio.Event().wait()

if __name__=='__main__':
    asyncio.run(main())
