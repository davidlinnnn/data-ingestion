# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""Remote cleanup constrained to the approved run root and frozen workflow IDs."""
import asyncio
import json
import hashlib
import signal
import sys
import time
from pathlib import Path


def argument_value(args, name):
    """Return one unambiguous CLI option value, or None."""
    values=[]
    for index, value in enumerate(args):
        if value == name and index+1 < len(args):
            values.append(args[index+1])
        elif value.startswith(name+'='):
            values.append(value.split('=',1)[1])
    return values[0] if len(values)==1 else None


def approved_controller_paths(root, controller_scripts):
    """Resolve reviewed relative entrypoints to exact paths in this run root."""
    result=set()
    for script in controller_scripts:
        if script.startswith('q04/'):
            result.add(str(root/'code/tests/pdf_processing'/script))
        else:
            result.add(str(root/script))
    return result


def controller_scope(args, root):
    """Discover a process claiming this state root without granting authority."""
    if argument_value(args,'--state') != str(root/'state'):
        return None
    return argument_value(args,'--name')


def is_controller_candidate(args, root, controller_scripts, cwd=None):
    """Recognize an exact reviewed controller entrypoint and state root."""
    if len(args)<=1:
        return False
    entrypoint=Path(args[1])
    if not entrypoint.is_absolute():
        if cwd is None:
            return False
        entrypoint=(Path(cwd)/entrypoint).absolute()
    return (len(args)>1
            and args[0]=='/experiment/.venv/bin/python'
            and str(entrypoint) in approved_controller_paths(root,controller_scripts)
            and argument_value(args,'--state') == str(root/'state'))


def is_owned_controller(args, root, controller_scripts, current_phase=None,
                        cwd=None):
    """Match a reviewed controller bound to the exact current phase."""
    if not is_controller_candidate(args,root,controller_scripts,cwd):
        return False
    phase=controller_scope(args,root)
    return phase is not None and (current_phase is None or phase == current_phase)


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
        entries.append((phase,trial,workflow_id))
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
    owners={}
    for phase,trial,workflow_id in entries:
        owners.setdefault(workflow_id,set()).add((phase,trial))
    for workflow_id, workflow_owners in owners.items():
        if len(workflow_owners)>1:
            invalid.append({
                'workflow_id':workflow_id,
                'owners':[{'phase':phase,'trial':trial}
                          for phase,trial in sorted(workflow_owners)],
                'reason':'workflow_id_owner_collision',
            })
            invalid_ids.add(workflow_id)
    current={workflow_id for phase,trial,workflow_id in entries
             if phase == current_phase and workflow_id not in invalid_ids}
    historical={workflow_id for phase,trial,workflow_id in entries
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


def process_snapshot(process):
    """Capture the identity fields that must remain stable before signalling."""
    return {
        'pid':process.pid,
        'created':process.create_time(),
        'command':process.cmdline(),
        'cwd':process.cwd(),
    }


def identity_is_stable(process, snapshot):
    return (process.pid == snapshot['pid']
            and process.create_time() == snapshot['created']
            and process.cmdline() == snapshot['command'])


def worker_command_matches(args, root, phase, worker_directory, owner):
    """Bind a worker PID record to its exact phase, directory and generation."""
    return (
        str(root/'code/tests/pdf_processing/q04/worker.py') in args
        and argument_value(args,'--config') == str(root/'state'/phase/'config.json')
        and argument_value(args,'--out') == str(worker_directory)
        and argument_value(args,'--generation') == str(owner['generation'])
    )


def parser_module(args):
    modules=('pdf_processing.warm_child','pdf_processing.parse',
             'pdf_processing.ocr','pdf_processing.evidence')
    return next((module for module in modules if module in args),None)


def live(process, psutil):
    try:
        return process.is_running() and process.status()!=psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


async def cleanup_processes(psutil, root, current_phase, controller_scripts,
                            report, errors):
    """Mutate only processes and scratch with exact current-phase ownership.

    Shared cwd, module names and a run-wide state root are discovery signals,
    never authority to signal or delete. Historical and ambiguous live work is
    retained and makes cleanup fail closed.
    """
    report.setdefault('controllers',[])
    report.setdefault('workers',[])
    report.setdefault('orphans',[])
    report.setdefault('unexpected_active_processes',[])
    verified_worker_directories=set()
    tracked_descendants={}

    # Controller ownership is the reviewed entrypoint plus exact --state and
    # --name. More than one live exact match is ambiguous and grants no mutation.
    controller_candidates=[]
    for process in psutil.process_iter():
        try:
            snapshot=process_snapshot(process)
            phase=controller_scope(snapshot['command'],root)
            if (argument_value(snapshot['command'],'--state') != str(root/'state')
                    or not live(process,psutil)):
                continue
            approved=is_controller_candidate(snapshot['command'],root,
                                               controller_scripts,snapshot['cwd'])
            controller_candidates.append((process,snapshot,phase,approved))
        except psutil.NoSuchProcess:
            pass
        except Exception as error:
            errors.append({'controller_process_audit':str(error)})
    current_controllers=[candidate for candidate in controller_candidates
                         if candidate[2] == current_phase and candidate[3]]
    ambiguous_current=len(current_controllers)>1
    for process,snapshot,phase,approved in controller_candidates:
        try:
            row={**snapshot,'phase':phase}
            if phase is None:
                row['scope']='ambiguous_phase'
                report['unexpected_active_processes'].append(row)
                errors.append({'process_ownership_invalid':row})
                continue
            if not approved:
                row['scope']='unapproved_entrypoint'
                report['unexpected_active_processes'].append(row)
                errors.append({'process_ownership_invalid':row})
                continue
            if phase != current_phase:
                row['scope']='historical_or_unowned'
                report['unexpected_active_processes'].append(row)
                errors.append({'unexpected_active_process':row})
                continue
            if ambiguous_current:
                row['scope']='current_ambiguous_duplicate'
                report['unexpected_active_processes'].append(row)
                errors.append({'process_ownership_invalid':row})
                continue
            if not identity_is_stable(process,snapshot):
                row['scope']='current_ambiguous'
                report['unexpected_active_processes'].append(row)
                errors.append({'process_ownership_invalid':row})
                continue
            process.send_signal(signal.SIGINT)
            try:
                await asyncio.to_thread(process.wait,30)
            except psutil.TimeoutExpired:
                if not identity_is_stable(process,snapshot):
                    row['scope']='current_pid_reused'
                    report['unexpected_active_processes'].append(row)
                    errors.append({'process_ownership_invalid':row})
                    continue
                process.terminate()
                try:
                    await asyncio.to_thread(process.wait,5)
                except psutil.TimeoutExpired:
                    if not identity_is_stable(process,snapshot):
                        row['scope']='current_pid_reused'
                        report['unexpected_active_processes'].append(row)
                        errors.append({'process_ownership_invalid':row})
                        continue
                    process.kill()
                    try:
                        await asyncio.to_thread(process.wait,5)
                    except psutil.TimeoutExpired:
                        if live(process,psutil):
                            if identity_is_stable(process,snapshot):
                                row['scope']='current_still_running_after_kill'
                                errors.append({'controller_still_running':process.pid})
                            else:
                                row['scope']='current_pid_reused_after_kill'
                                errors.append({'process_ownership_invalid':row})
                            report['unexpected_active_processes'].append(row)
                            continue
                row['forced']=True
                errors.append({'controller_forced':process.pid})
            if live(process,psutil):
                row['scope']='current_still_running'
                report['unexpected_active_processes'].append(row)
                errors.append({'controller_still_running':process.pid})
                continue
            row['scope']='current'
            report['controllers'].append(row)
        except psutil.NoSuchProcess:
            pass
        except Exception as error:
            errors.append({'controller_process_audit':str(error)})

    ownership_paths=sorted((root/'state').glob('*/worker-*/ownership.json'))
    ownership_records=[]
    for path in ownership_paths:
        phase=path.relative_to(root/'state').parts[0]
        try:
            owner=json.loads(path.read_text())
            owner['pid'];owner['created'];owner['generation'];owner['config_sha256']
            config_path=root/'state'/phase/'config.json'
            if (not config_path.is_file()
                    or hashlib.sha256(config_path.read_bytes()).hexdigest()
                    != owner['config_sha256']):
                raise ValueError('worker config identity mismatch')
            ownership_records.append((path,phase,owner))
        except (KeyError,ValueError,json.JSONDecodeError) as error:
            errors.append({'process_ownership_invalid':{
                'path':str(path),'reason':str(error)}})
    owner_paths={}
    for path,phase,owner in ownership_records:
        owner_paths.setdefault(owner['pid'],[]).append((path,phase,owner))
    conflicting_worker_pids={pid for pid,records in owner_paths.items()
                             if len(records)>1}
    audited_worker_pids=set()
    for path,phase,owner in ownership_records:
        try:
            audited_worker_pids.add(owner['pid'])
            row={'pid':owner['pid'],'created':owner['created'],
                 'generation':owner['generation'],'phase':phase,
                 'ownership_path':str(path)}
            try:
                process=psutil.Process(owner['pid'])
            except psutil.NoSuchProcess:
                if phase == current_phase:
                    row['scope']='current';row['already_absent']=True
                    verified_worker_directories.add(path.parent)
                    report['workers'].append(row)
                continue
            if not live(process,psutil):
                if phase == current_phase:
                    row['scope']='current';row['already_absent']=True
                    verified_worker_directories.add(path.parent)
                    report['workers'].append(row)
                continue
            snapshot=process_snapshot(process)
            if owner['pid'] in conflicting_worker_pids:
                row.update(command=snapshot['command'],cwd=snapshot['cwd'],
                           scope='ambiguous_multiple_records')
                report['unexpected_active_processes'].append(row)
                errors.append({'process_ownership_invalid':row})
                continue
            exact=(snapshot['created']==owner['created']
                   and worker_command_matches(snapshot['command'],root,phase,
                                              path.parent,owner))
            row.update(command=snapshot['command'],cwd=snapshot['cwd'])
            if phase != current_phase:
                row['scope']='historical_or_unowned'
                report['unexpected_active_processes'].append(row)
                errors.append({'unexpected_active_process':row})
                continue
            if not exact or not identity_is_stable(process,snapshot):
                row['scope']='current_ambiguous'
                report['unexpected_active_processes'].append(row)
                errors.append({'process_ownership_invalid':row})
                continue
            children=[]
            for child in process.children(recursive=True):
                child_snapshot=process_snapshot(child)
                parents=[parent.pid for parent in child.parents()]
                if owner['pid'] not in parents:
                    errors.append({'process_ownership_invalid':{
                        **child_snapshot,'reason':'worker_child_parentage_mismatch'}})
                    continue
                child_snapshot['parentage']=parents
                children.append((child,child_snapshot))
                tracked_descendants[child.pid]=child_snapshot
            process.send_signal(signal.SIGTERM)
            _,alive_processes=await asyncio.to_thread(
                psutil.wait_procs,[child for child,_ in children]+[process],75)
            alive_processes=[candidate for candidate in alive_processes
                             if live(candidate,psutil)]
            if alive_processes:
                snapshots={candidate.pid:snapshot for candidate,snapshot in children}
                snapshots[process.pid]=snapshot
                safe=[]
                for candidate in alive_processes:
                    candidate_snapshot=snapshots.get(candidate.pid)
                    if candidate_snapshot and identity_is_stable(candidate,candidate_snapshot):
                        safe.append(candidate)
                    else:
                        errors.append({'process_ownership_invalid':{
                            'pid':candidate.pid,'reason':'identity_changed_before_kill'}})
                for candidate in reversed(safe):
                    candidate.kill()
                _,still_alive=await asyncio.to_thread(psutil.wait_procs,safe,5)
                still_alive=[candidate for candidate in still_alive
                             if live(candidate,psutil)]
                if still_alive:
                    errors.append({'worker_processes_still_running':
                                   [candidate.pid for candidate in still_alive]})
                row['forced']=True
                errors.append({'worker_forced':process.pid})
            if not any(live(candidate,psutil) for candidate in [process]+[c for c,_ in children]):
                verified_worker_directories.add(path.parent)
            row['scope']='current'
            proof=path.parent/'stopped.json'
            row['stopped']=json.loads(proof.read_text()) if proof.exists() else None
            report['workers'].append(row)
        except psutil.NoSuchProcess:
            errors.append({'worker_process_audit':{
                'path':str(path),'error':'process disappeared during identity audit'}})
        except Exception as error:
            errors.append({'worker_process_audit':{'path':str(path),'error':str(error)}})

    worker_script=str(root/'code/tests/pdf_processing/q04/worker.py')
    for process in psutil.process_iter():
        try:
            if (process.pid in audited_worker_pids or not live(process,psutil)):
                continue
            snapshot=process_snapshot(process)
            if worker_script not in snapshot['command']:
                continue
            snapshot['scope']='unrecorded_worker'
            report['unexpected_active_processes'].append(snapshot)
            errors.append({'unexpected_active_process':snapshot})
        except psutil.NoSuchProcess:
            pass
        except Exception as error:
            errors.append({'worker_process_audit':{'error':str(error)}})

    # Discover parser-like processes after owned worker cleanup. A module name
    # and cwd alone cannot establish current ownership. Only a descendant
    # snapshot captured from an exact current worker is sufficient.
    for process in psutil.process_iter():
        try:
            if not live(process,psutil):
                continue
            snapshot=process_snapshot(process)
            module=parser_module(snapshot['command'])
            if module is None:
                continue
            snapshot['module']=module
            known=tracked_descendants.get(process.pid)
            if known and identity_is_stable(process,known):
                snapshot['scope']='current_descendant_still_running'
            else:
                snapshot['scope']='historical_or_unowned'
            report['orphans'].append(snapshot)
            report['unexpected_active_processes'].append(snapshot)
            errors.append({'unexpected_active_process':snapshot})
        except psutil.NoSuchProcess:
            pass
        except Exception as error:
            errors.append({'parser_process_audit':str(error)})

    import shutil
    current_scratch=[]
    for scratch in sorted((root/'state'/current_phase).glob('worker-*/scratch')):
        if scratch.parent in verified_worker_directories:
            shutil.rmtree(scratch)
            report.setdefault('removed_owned_scratch',[]).append(str(scratch))
        else:
            current_scratch.append(str(scratch))
            errors.append({'current_scratch_ownership_ambiguous':str(scratch)})
    report['current_scratch_remaining']=current_scratch
    report['historical_scratch_retained']=[
        str(path) for path in sorted((root/'state').glob('*/worker-*/scratch'))
        if path.relative_to(root/'state').parts[0] != current_phase]


async def main(location, controller_scripts=('q04/q04_runtime.py',), current_phase=None):
    import psutil
    root=Path(location)
    evidence=root/('owner-cleanup-'+str(time.time_ns()));evidence.mkdir()
    errors=[];report={'started':time.time(),'controllers':[],'workflows':[],
                      'workers':[],'orphans':[]}
    if not current_phase:
        errors.append({'workflow_ownership':'current phase is required'})
    else:
        await cleanup_processes(psutil,root,current_phase,controller_scripts,
                                report,errors)
    config=None
    config_path=root/'state/config.json'
    if config_path.exists():
        config=json.loads(config_path.read_text())
        sys.path[:0]=[str(root/'code/src'),str(root/'code/tests/pdf_processing/q04'),str(root/'code/tests/pdf_processing/q02'),str(root/'code/tests/pdf_processing/q03')]
        try:
            from temporalio.client import Client
            client=await asyncio.wait_for(Client.connect(config['temporal']),10)
            if current_phase:
                await cleanup_workflows(client,root,config['run_id'],current_phase,
                                        evidence,report,errors)
                await asyncio.sleep(2)
        except Exception as e:errors.append({'workflow_transport':str(e)})
    if config is not None:
        try:
            import boto3
            from pdf_processing.object_store import Store
            from q04_runtime import Run
            store=Store(boto3.client('s3',endpoint_url=config['endpoint']),config['bucket'],config['prefix'])
            run=Run(config,{},root,None,store,None)
            for path in ((root/'state'/current_phase).glob('*/admission.json')
                         if current_phase else []):
                admission=json.loads(path.read_text());result_path=path.with_name('result.json')
                result=json.loads(result_path.read_text()) if result_path.exists() else None
                if admission['mode']!='replay' and (result is None or result.get('status')!='complete'):
                    await asyncio.to_thread(run.no_complete,admission['request'])
                    report.setdefault('incomplete_publication_absent',[]).append(admission['request']['request_id'])
        except Exception as e:errors.append({'publication_audit':str(e)})
    report['errors']=errors;report['finished']=time.time()
    (evidence/'report.json').open('x').write(json.dumps(report,indent=2))
    print(json.dumps(report))
    assert not report.get('current_scratch_remaining'), 'cleanup incomplete'
    assert all(row['status']!='RUNNING' for row in report['workflows']
               if row['scope']=='current')
    workflow_failures={
        'workflow_transport','workflow','workflow_ownership',
        'workflow_ownership_invalid','current_owned_missing',
        'current_workflow_still_running','unexpected_active_workflow',
        'running_after_cleanup','publication_audit','unexpected_active_process',
        'process_ownership_invalid','current_scratch_ownership_ambiguous',
        'worker_processes_still_running','controller_process_audit',
        'worker_process_audit','parser_process_audit','controller_still_running',
        'controller_forced','worker_forced',
    }
    assert not any(isinstance(e,dict) and (
        workflow_failures.intersection(e) or ('worker' in e and 'error' in e)
    ) for e in errors), 'cleanup verification failed'
