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


def is_temporal_not_found(error):
    """Recognize only the SDK's typed NOT_FOUND transport result."""
    from temporalio.service import RPCError, RPCStatusCode

    return isinstance(error, RPCError) and error.status == RPCStatusCode.NOT_FOUND


def recorded_workflow_ids(root, current_phase):
    """Separate the exact current phase records from immutable history."""
    entries = []
    invalid = []
    invalid_ids = set()
    trials = {}
    paths=list((root/'state').glob('*/*/workflow-intent.json'))
    paths.extend((root/'state').glob('*/*/workflow.json'))
    for path in paths:
        record=json.loads(path.read_text())
        workflow_id=record['workflow_id']
        relative=path.relative_to(root/'state')
        phase, trial=relative.parts[:2]
        trials.setdefault(path.parent,{})[path.name]=workflow_id
        entries.append((phase,workflow_id))
        if path.name=='workflow-intent.json' and (
                record.get('phase') != phase or record.get('trial') != trial):
            invalid.append({'path':str(path),'workflow_id':workflow_id,
                            'reason':'phase_or_trial_mismatch'})
            invalid_ids.add(workflow_id)
    for directory, records in trials.items():
        if len(set(records.values())) > 1:
            mismatched=sorted(set(records.values()))
            invalid.append({'path':str(directory),'workflow_ids':mismatched,
                            'reason':'intent_record_id_mismatch'})
            invalid_ids.update(mismatched)
    current={workflow_id for phase,workflow_id in entries
             if phase == current_phase and workflow_id not in invalid_ids}
    historical={workflow_id for phase,workflow_id in entries
                if phase != current_phase and workflow_id not in invalid_ids}
    return current, historical, invalid, invalid_ids


async def cleanup_workflows(client, root, run_id, current_phase, evidence,
                            report, errors, not_found=is_temporal_not_found):
    """Stop exact current records; audit history and unowned discoveries.

    A pre-submit workflow intent closes the submit-before-record crash gap. An
    unrecorded running workflow has no exact phase ownership, so it is surfaced
    as unexpected active work and fails cleanup without being signalled.
    """
    prefix=run_id+'-'
    current, historical, invalid, invalid_ids=recorded_workflow_ids(
        root,current_phase)
    invalid.extend({'workflow_id':wid,'reason':'run_prefix_mismatch'}
                   for wid in sorted(current|historical) if not wid.startswith(prefix))
    if invalid:
        errors.append({'workflow_ownership_invalid':invalid})
    current={wid for wid in current if wid.startswith(prefix)}
    historical={wid for wid in historical if wid.startswith(prefix)}
    async with asyncio.timeout(15):
        discovered={w.id async for w in client.list_workflows()
                    if w.id.startswith(prefix)}
    report['workflow_ownership']={
        'phase':current_phase,
        'current_recorded':sorted(current),
        'historical_recorded':sorted(historical),
        'discovered':sorted(discovered),
        'invalid_unowned':sorted(invalid_ids),
    }
    report['historical_workflows']=[]
    report['historical_missing']=[]
    report['unexpected_active_workflows']=[]

    async def status(handle):
        description=await asyncio.wait_for(handle.describe(),10)
        assert description.status is not None
        return description.status.name

    async def retain_history(workflow_id, handle, scope):
        history=await asyncio.wait_for(handle.fetch_history(),10)
        name=hashlib.sha256(workflow_id.encode()).hexdigest()+'.history.json'
        with (evidence/name).open('x') as output:
            output.write(history.to_json())
        if scope=='historical':
            report['historical_workflows'].append(workflow_id)

    for workflow_id in sorted(current):
        handle=client.get_workflow_handle(workflow_id)
        try:
            if await status(handle)=='RUNNING':
                await handle.cancel()
                try:await asyncio.wait_for(handle.result(),20)
                except BaseException:
                    if await status(handle)=='RUNNING':
                        await handle.terminate(reason='approved Q04 sentinel cleanup')
            current_status=await status(handle)
            if current_status=='RUNNING':
                errors.append({'current_workflow_still_running':workflow_id})
            report['workflows'].append({
                'workflow_id':workflow_id,'status':current_status,'scope':'current'})
            await retain_history(workflow_id,handle,'current')
        except Exception as error:
            if not_found(error):
                errors.append({'current_owned_missing':workflow_id})
            else:
                errors.append({'workflow':workflow_id,'error':str(error)})

    for workflow_id in sorted(historical):
        handle=client.get_workflow_handle(workflow_id)
        try:
            historical_status=await status(handle)
            if historical_status=='RUNNING':
                report['unexpected_active_workflows'].append({
                    'workflow_id':workflow_id,'source':'historical_record'})
                errors.append({'unexpected_active_workflow':workflow_id})
            report['workflows'].append({
                'workflow_id':workflow_id,'status':historical_status,'scope':'historical'})
            await retain_history(workflow_id,handle,'historical')
        except Exception as error:
            if not_found(error):
                report['historical_missing'].append(workflow_id)
            else:
                errors.append({'workflow':workflow_id,'error':str(error)})

    for workflow_id in sorted(discovered-current-historical):
        handle=client.get_workflow_handle(workflow_id)
        try:
            discovered_status=await status(handle)
            row={'workflow_id':workflow_id,'status':discovered_status,
                 'scope':'unrecorded'}
            report['workflows'].append(row)
            if discovered_status=='RUNNING':
                report['unexpected_active_workflows'].append({
                    'workflow_id':workflow_id,
                    'source':('invalid_ownership' if workflow_id in invalid_ids
                              else 'unregistered_unexpected')})
                errors.append({'unexpected_active_workflow':workflow_id})
        except Exception as error:
            if not_found(error):
                report.setdefault('discovered_missing',[]).append(workflow_id)
            else:
                errors.append({'workflow':workflow_id,'error':str(error)})

    async with asyncio.timeout(15):
        report['running_after_cleanup']=[
            w.id async for w in client.list_workflows(
                query='ExecutionStatus="Running"') if w.id.startswith(prefix)]
    if report['running_after_cleanup']:
        errors.append({'running_after_cleanup':report['running_after_cleanup']})


async def main(location, controller_scripts=('q04/q04_runtime.py',), current_phase=None):
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
            if not current_phase:
                errors.append({'workflow_ownership':'current phase is required'})
            else:
                await cleanup_workflows(client,root,config['run_id'],current_phase,
                                        evidence,report,errors)
                await asyncio.sleep(2)
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
    workflow_failures={
        'workflow_transport','workflow','workflow_ownership',
        'workflow_ownership_invalid','current_owned_missing',
        'current_workflow_still_running','unexpected_active_workflow',
        'running_after_cleanup','publication_audit',
    }
    assert not any(isinstance(e,dict) and (
        workflow_failures.intersection(e) or ('worker' in e and 'error' in e)
    ) for e in errors), 'cleanup verification failed'
