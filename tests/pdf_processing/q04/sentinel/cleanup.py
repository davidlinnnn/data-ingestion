# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""Remote cleanup constrained to the approved run root and frozen workflow IDs."""
import asyncio
import json
import hashlib
import signal
import sys
import time
from pathlib import Path


def is_owned_controller(args, root, controller_scripts):
    """Match only a reviewed controller entrypoint bound to this run's state."""
    return (
        len(args)>1
        and args[0]=='/experiment/.venv/bin/python'
        and any(args[1].endswith(script) for script in controller_scripts)
        and str(root/'state') in args
    )


async def main(location, controller_scripts=('q04/q04_runtime.py',)):
    import psutil
    root=Path(location)
    evidence=root/('owner-cleanup-'+str(time.time_ns()));evidence.mkdir()
    errors=[];report={'started':time.time(),'controllers':[],'workflows':[],'workers':[],'orphans':[]}
    # Never treat loss of kubectl as proof of remote exit.
    for p in psutil.process_iter():
        try:
            args=p.cmdline()
            if is_owned_controller(args, root, controller_scripts):
                created=p.create_time();p.send_signal(signal.SIGINT)
                try:await asyncio.to_thread(p.wait,30)
                except psutil.TimeoutExpired:
                    assert p.create_time()==created;p.terminate()
                    try:await asyncio.to_thread(p.wait,5)
                    except psutil.TimeoutExpired:p.kill()
                    errors.append('controller needed forced termination')
                report['controllers'].append({'pid':p.pid,'created':created})
        except psutil.NoSuchProcess:pass
    config=None
    config_path=root/'state/config.json'
    if config_path.exists():
        config=json.loads(config_path.read_text())
        sys.path[:0]=[str(root/'code/src'),str(root/'code/tests/pdf_processing/q04'),str(root/'code/tests/pdf_processing/q02'),str(root/'code/tests/pdf_processing/q03')]
        try:
            from temporalio.client import Client
            client=await asyncio.wait_for(Client.connect(config['temporal']),10)
            async def workflow_status(handle):
                description=await asyncio.wait_for(handle.describe(),10)
                assert description.status is not None
                return description.status.name
            ids={json.loads(path.read_text())['workflow_id'] for path in (root/'state').glob('*/*/workflow.json')}
            async def running_owned():
                async with asyncio.timeout(15):
                    return [w.id async for w in client.list_workflows(query='ExecutionStatus="Running"') if w.id.startswith(config['run_id']+'-')]
            # Cover the submit/record gap; recorded IDs are not the authority.
            async with asyncio.timeout(15):
                discovered=[w.id async for w in client.list_workflows() if w.id.startswith(config['run_id']+'-')]
            report['discovered_executions']=discovered
            ids.update(discovered)
            for wid in ids:
                assert wid.startswith(config['run_id']+'-')
                h=client.get_workflow_handle(wid)
                try:
                    if await workflow_status(h)=='RUNNING':
                        await h.cancel()
                        try:await asyncio.wait_for(h.result(),20)
                        except BaseException:
                            if await workflow_status(h)=='RUNNING':await h.terminate(reason='approved Q04 sentinel cleanup')
                    status=await workflow_status(h)
                    assert status!='RUNNING'
                    report['workflows'].append({'workflow_id':wid,'status':status})
                    history=await asyncio.wait_for(h.fetch_history(),10)
                    (evidence/(hashlib.sha256(wid.encode()).hexdigest()+'.history.json')).open('x').write(history.to_json())
                except Exception as e:errors.append({'workflow':wid,'error':str(e)})
            await asyncio.sleep(2)
            report['running_after_cleanup']=await running_owned()
            assert not report['running_after_cleanup'],'owned workflow still running'
        except Exception as e:errors.append({'workflow_transport':str(e)})
    for path in (root/'state').glob('*/worker-*/ownership.json'):
        owner=json.loads(path.read_text());row={'pid':owner['pid'],'generation':owner['generation']}
        try:
            p=psutil.Process(owner['pid'])
            if p.is_running() and p.status()!=psutil.STATUS_ZOMBIE:
                assert p.create_time()==owner['created'] and any(str(root/'code/tests/pdf_processing/q04/worker.py')==arg for arg in p.cmdline())
                children=p.children(recursive=True)
                p.send_signal(signal.SIGTERM)
                gone,alive=await asyncio.to_thread(psutil.wait_procs,children+[p],75)
                alive=[x for x in alive if x.status()!=psutil.STATUS_ZOMBIE]
                if alive:
                    for child in alive:child.kill()
                    _,alive=await asyncio.to_thread(psutil.wait_procs,alive,5)
                    assert not [x for x in alive if x.status()!=psutil.STATUS_ZOMBIE]
                    row['forced']=True;errors.append({'worker':p.pid,'forced':True})
        except psutil.NoSuchProcess:pass
        except Exception as e:errors.append({'worker':owner['pid'],'error':str(e)})
        row['scratch_absent']=not (path.parent/'scratch').exists()
        proof=path.parent/'stopped.json'
        row['stopped']=json.loads(proof.read_text()) if proof.exists() else None
        report['workers'].append(row)
    # A unique staged cwd plus a known child module identifies only this run's
    # orphan. Unknown processes are reported, never broadly signaled.
    for p in psutil.process_iter():
        try:
            args=p.cmdline()
            if any(a in args for a in ('pdf_processing.warm_child','pdf_processing.parse','pdf_processing.ocr','pdf_processing.evidence')):
                row={'pid':p.pid,'created':p.create_time(),'cwd':p.cwd()}
                if p.cwd()==str(root/'code'):
                    p.terminate()
                    try:await asyncio.to_thread(p.wait,5)
                    except psutil.TimeoutExpired:p.kill()
                    row['owned_orphan_stopped']=True
                    errors.append({'orphan_required_cleanup':p.pid})
                else:row['unresolved']=True;errors.append({'unidentified_parser':p.pid})
                report['orphans'].append(row)
        except psutil.NoSuchProcess:pass
    remaining=[]
    for p in psutil.process_iter():
        try:
            if p.status()!=psutil.STATUS_ZOMBIE and p.cwd()==str(root/'code'):remaining.append(p.pid)
        except psutil.NoSuchProcess:pass
    report['remaining_owned_cwd_pids']=remaining
    if remaining:errors.append({'remaining_owned':remaining})
    if config is not None:
        try:
            import boto3
            from pdf_processing.object_store import Store
            from q04_runtime import Run
            store=Store(boto3.client('s3',endpoint_url=config['endpoint']),config['bucket'],config['prefix'])
            run=Run(config,{},root,None,store,None)
            for path in (root/'state').glob('*/*/admission.json'):
                admission=json.loads(path.read_text());result_path=path.with_name('result.json')
                result=json.loads(result_path.read_text()) if result_path.exists() else None
                if admission['mode']!='replay' and (result is None or result.get('status')!='complete'):
                    await asyncio.to_thread(run.no_complete,admission['request'])
                    report.setdefault('incomplete_publication_absent',[]).append(admission['request']['request_id'])
        except Exception as e:errors.append({'publication_audit':str(e)})
    # Keep historical scratch/errors; remove only this run's verified scratch,
    # after all matching processes are absent, and record it separately.
    if not remaining and not any(r.get('unresolved') for r in report['orphans']):
        import shutil
        for path in (root/'state').glob('*/worker-*/scratch'):
            shutil.rmtree(path)
            report.setdefault('removed_owned_scratch',[]).append(str(path))
    report['scratch_remaining']=[str(p) for p in (root/'state').glob('*/worker-*/scratch')]
    report['errors']=errors;report['finished']=time.time()
    (evidence/'report.json').open('x').write(json.dumps(report,indent=2))
    print(json.dumps(report))
    assert not remaining and not report['scratch_remaining'] and not any(r.get('unresolved') for r in report['orphans']), 'cleanup incomplete'
    assert all(row['status']!='RUNNING' for row in report['workflows'])
    assert not any(isinstance(e,dict) and ('workflow_transport' in e or 'publication_audit' in e or 'workflow' in e or ('worker' in e and 'error' in e)) for e in errors), 'cleanup verification failed'
