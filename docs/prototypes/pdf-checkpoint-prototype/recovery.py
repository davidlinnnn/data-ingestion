"""THROWAWAY local Temporal experiment. Filesystem store is NOT distributed storage."""
import asyncio
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Worker

ROOT = Path(__file__).resolve().parent
STORE = Path(os.environ.get('PDF_PROTOTYPE_STORE', str(ROOT/'PROTOTYPE-wipe-me/temporal-store')))
RUN_PREFIX = os.environ.get('PDF_PROTOTYPE_RUN', 'pdf-checkpoint-trial')
PYTHON = ROOT/'.venv/bin/python'
PDF = ROOT/'fixtures/llm-survey-2303.18223v1.pdf'
METHOD = ROOT/'PROTOTYPE-wipe-me/native-capture-v2/method.json'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def record(event_name, **data):
    STORE.mkdir(parents=True, exist_ok=True)
    with (STORE/'ledger.jsonl').open('a') as f:
        f.write(json.dumps({'event':event_name, 'time':time.time(), **data})+'\n')
        f.flush()
        os.fsync(f.fileno())


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.incomplete')
    with tmp.open('w') as f:
        json.dump(value, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    # No overwrite: only one accepted registration per identity.
    try:
        os.link(tmp, path)
        record('registered', operation=path.stem)
    except FileExistsError:
        pass
    tmp.unlink()
    fd=os.open(path.parent,os.O_RDONLY)
    os.fsync(fd)
    os.close(fd)


def verify_checkpoint(path, start, end):
    data=json.loads((path/'complete.json').read_text())
    assert data['source_sha256']==sha(PDF)
    assert data['method_sha256']==sha(METHOD)==sha(path/'method.json')
    pages=[]
    for item in data['pages']:
        p=path/'checkpoints'/item['file']
        assert sha(p)==item['sha256']
        page=json.loads(p.read_text())
        assert page['source_sha256']==data['source_sha256']
        assert page['method_sha256']==data['method_sha256']
        assert sha(p.parent/page['visual']['file'])==page['visual']['sha256']
        pages.append(page['page_no'])
    assert pages==list(range(start,end+1))
    return data


async def child(args, out):
    out.mkdir(parents=True, exist_ok=True)
    with (out/'process.log').open('w') as log:
        p=await asyncio.create_subprocess_exec(str(PYTHON), *map(str,args),
             stdout=log, stderr=subprocess.STDOUT, env={**os.environ,'HF_HUB_OFFLINE':'1'})
        code=await p.wait()
    record('child_exit', directory=str(out), code=code)
    if code:
        raise RuntimeError(f'Injected or real child failure {code}: {out}')


@activity.defn
async def produce(spec: dict) -> str:
    kind=spec['kind']
    producer = {'adapter': sha(ROOT/'experiment.py'), 'orchestrator': sha(Path(__file__))}
    if kind == 'ocr':
        producer.update(ocr_code=sha(ROOT/'ocr_component.py'), reference=sha(ROOT/'ocr-reference.json'), parsed_result=sha(Path(spec['parsed'])/'document.json'))
    identity=hashlib.sha256(json.dumps({**spec,'source':sha(PDF),'method':sha(METHOD),'producer':producer},sort_keys=True).encode()).hexdigest()
    reg=STORE/'registered'/f'{identity}.json'
    attempt=activity.info().attempt
    if reg.exists():
        saved=json.loads(reg.read_text())
        result=Path(saved['result'])
        assert sha(result/saved['artifact'])==saved['sha256']
        if kind=='group':
            verify_checkpoint(result,spec['start'],spec['end'])
        if kind == 'ocr':
            ocr = json.loads((result/'ocr.json').read_text())
            assert sha(result/'figure.png') == ocr['crop_sha256']
            assert ocr['parsed_result_sha256'] == producer['parsed_result']
        record('reused', kind=kind, identity=identity, attempt=attempt)
        return str(result)
    out=STORE/'attempts'/identity/f'{activity.info().workflow_id}-{attempt}'
    record('started', kind=kind, identity=identity, attempt=attempt, spec=spec)
    t=time.perf_counter()
    if kind=='group':
        args=[ROOT/'experiment.py','capture',PDF,'--out',out,'--start',spec['start'],'--end',spec['end'],'--checkpoint-only']
        if spec.get('failure')=='mid-group' and attempt==1:
            args += ['--crash-after-page',spec['start']+1]
        await child(args,out)
        verify_checkpoint(out,spec['start'],spec['end'])
        artifact='complete.json'
    elif kind=='assembly':
        merged=out/'merged'
        merged.mkdir(parents=True,exist_ok=True)
        (merged/'checkpoints').mkdir(exist_ok=True)
        manifest=None
        for group in spec['groups']:
            group=Path(group)
            m=json.loads((group/'complete.json').read_text())
            if manifest is None:
                manifest={**m,'pages':[], 'confidence':{**m['confidence'],'pages':{}}}
            manifest['pages'] += m['pages']
            manifest['confidence']['pages'].update(m['confidence']['pages'])
            for p in (group/'checkpoints').iterdir():
                shutil.copyfile(p,merged/'checkpoints'/p.name)
        (merged/'complete.json').write_text(json.dumps(manifest))
        shutil.copyfile(METHOD,merged/'method.json')
        verify_checkpoint(merged,1,51)
        args=[ROOT/'experiment.py','restore',PDF,'--checkpoint',merged,'--out',out]
        if attempt==1:
            args+=['--crash-before-assembly']
        await child(args,out)
        # Gate OCR on grouped-versus-uninterrupted fidelity, not Workflow success.
        await child([ROOT/'compare.py',ROOT/'PROTOTYPE-wipe-me/native-baseline',out,'--out',out/'comparison.json'],out/'comparison-process')
        artifact='document.json'
    elif kind=='ocr':
        args=[ROOT/'ocr_component.py',Path(spec['parsed'])/'document.json',PDF,out]
        await child(args,out)
        artifact='ocr.json'
        if attempt==1:
            record('injected_ocr_failure_before_registration', identity=identity)
            raise RuntimeError('OCR completed but output not registered; retry independently')
    else:
        raise ValueError(kind)
    atomic(reg,{'result':str(out),'artifact':artifact,'sha256':sha(out/artifact)})
    record('completed',kind=kind,identity=identity,attempt=attempt,seconds=time.perf_counter()-t)
    if spec.get('failure')=='lost-ack' and attempt==1:
        record('injected_completion_loss',identity=identity)
        raise RuntimeError('Persistence succeeded; Activity completion acknowledgement deliberately withheld')
    return str(out)


@workflow.defn(sandboxed=False)
class Recovery:
    @workflow.run
    async def run(self, size: int) -> dict:
        retry=RetryPolicy(initial_interval=timedelta(seconds=1),maximum_interval=timedelta(seconds=2),maximum_attempts=3)
        async def call(spec):
            return await workflow.execute_activity(produce,spec,start_to_close_timeout=timedelta(minutes=5),retry_policy=retry)
        groups=[]
        for start in range(1,52,size):
            spec={'kind':'group','start':start,'end':min(51,start+size-1)}
            if start==1:
                spec['failure']='lost-ack'
            if start==1+size:
                spec['failure']='mid-group'
            groups.append(await call(spec))
        parsed=await call({'kind':'assembly','groups':groups})
        ocr=await call({'kind':'ocr','parsed':parsed})
        return {'groups':groups,'parsed':parsed,'ocr':ocr}


async def main():
    client=await Client.connect('127.0.0.1:7239')
    async with Worker(client,task_queue='pdf-checkpoint-prototype',workflows=[Recovery],activities=[produce]):
        for n in (1,2):
            t=time.perf_counter()
            handle=await client.start_workflow(Recovery.run,5,id=f'{RUN_PREFIX}-{n}',task_queue='pdf-checkpoint-prototype')
            result=await handle.result()
            (STORE/f'workflow-{n}.json').write_text(json.dumps({'seconds':time.perf_counter()-t,**result},indent=2))
            history=await handle.fetch_history()
            (STORE/f'history-{n}.json').write_text(history.to_json())
            print(json.dumps(result,indent=2))

if __name__=='__main__':
    asyncio.run(main())
