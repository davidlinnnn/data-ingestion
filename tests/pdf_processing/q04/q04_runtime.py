"""Q04 actual Activities/shared-storage matrix; requires a newly approved capacity file.

Only --help is a local dry run. Use prepare.py and test_adapter.py before capacity
coordination. No service scaling, historical pauses or source deletion is built in.
"""
import argparse
import asyncio
import copy
from datetime import timedelta
import fcntl
import json
import os
from pathlib import Path
import sys
import time
import uuid

from consumer import Consumer, ROOT, require, sha, canonical
from contracts import mode_checks, warm_checks, drain_checks, validate_window
from host import Host
from prepare import verify_bundle
from telemetry import sample, check_sample, check_coverage, read_rows


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def profiles(bundle, originals):
    result = {}
    for fixture in bundle['fixtures']:
        sid = fixture['id']
        profile = copy.deepcopy(bundle['base_profile'])
        review = copy.deepcopy(fixture['review'])
        review['original_source'] = {'artifact': originals[sid], 'source_revision': fixture['source_revision']}
        relation = {'method': 'local-function-block-v1', 'coverage': {'mode': 'unknown'}, 'unresolved': 'allow_unknown'}
        if sid == '08':
            relation = {'method': 'local-function-block-v1', 'unresolved': 'reject',
                'coverage': {'mode': 'selected_regions', 'source_sha256': fixture['sha256'], 'regions': [
                    {'id': f'page-{page}', 'page': page, 'box': box, 'required_count': 1} for page, box in
                    [(3, [100,75,500,290]), (5, [100,75,500,350]), (9, [100,75,500,285]), (10, [100,85,500,205])]]},
                'representation': bundle['representation']}
        profile['content_evidence'] = {'version': 'typed-source-relationships-v2',
            'reviews': {fixture['sha256']: review}, 'relationships': relation}
        result[sid] = profile
    result['native-evidence'] = copy.deepcopy(result['native'])
    result['native-evidence']['content_evidence']['reviews'][bundle['fixtures'][0]['sha256']]['scope'] += ' Q04 evidence-only metadata variant.'
    result['native-method'] = copy.deepcopy(result['native'])
    del result['native-method']['method']['continuation']
    for profile in result.values():
        profile.pop('release', None)
        profile['release'] = 'q04-'+sha(canonical({'profile': profile, 'producer': bundle['producer']}).encode())
    return result


def capture(store, path, name):
    data = path.read_bytes()
    key = store.prefix+'sources/'+name
    saved = store.client.put_object(Bucket=store.bucket, Key=key, Body=data)
    require(saved['VersionId'] != 'null', 'versioned source capture required')
    return {'name': name, 'key': key, 'version_id': saved['VersionId'], 'sha256': sha(data)}


class Run:
    def __init__(self, config, bundle, root, client, store, host):
        self.config, self.bundle, self.root, self.client, self.store, self.host = config, bundle, root, client, store, host
        self.initial = None
        self.active = None
        self.vm_oom = None
        self.sample_counts = {}

    async def guard(self):
        validate_window(self.config['window'], time.time())
        require(time.time() < self.config['window']['ends_at']-self.config['window']['cleanup_seconds'], 'cleanup reserve reached')
        require(self.host.process is not None and self.host.process.poll() is None, 'worker exited')
        path = self.host.current/'samples.jsonl'
        rows = read_rows(path)
        require(rows and 0 <= time.time()-rows[-1]['time'] <= self.config['window']['max_sample_gap_seconds'], 'resource telemetry lost')
        if self.initial is None:
            self.initial = rows[0]
        if self.vm_oom is None:
            self.vm_oom = rows[0]['vm_oom_kill']
        require(rows[-1]['vm_oom_kill'] == self.vm_oom, 'VM OOM across worker generations')
        count = self.sample_counts.get(str(path), 0)
        for observed in rows[count:]:
            check_sample(observed, self.initial, self.config['window'])
        self.sample_counts[str(path)] = len(rows)
        if self.host.pod:
            pod = await asyncio.to_thread(self.host.inventory)
            require(pod['metadata']['uid'] == self.host.pod['metadata']['uid'], 'unexpected Pod replacement')
        return rows[-1]

    async def admission(self):
        start = time.monotonic()
        while time.monotonic()-start < self.config['window']['admission_seconds']:
            row = await self.guard()
            require(row['available'] >= self.config['window']['admission_available_bytes'] and row['psi_full_avg10'] == 0, 'capacity admission rejected')
            await asyncio.sleep(.5)

    async def cancel_owned(self, handle):
        try:
            await handle.cancel()
            await asyncio.wait_for(handle.result(), 20)
        except BaseException:
            description = await handle.describe()
            if description.status.name == 'RUNNING':
                await handle.terminate(reason='Q04 owned trial abort; preserve partial evidence')
        require((await handle.describe()).status.name != 'RUNNING', 'owned workflow not stopped')

    def no_complete(self, request):
        from pdf_processing.processing import encoded
        plan = 'pdf-plan-v1:'+sha(encoded(request['request_id']))
        paginator = self.store.client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=self.store.bucket, Prefix=self.store.prefix+'registered/'):
            for entry in page.get('Contents', []):
                registration = json.loads(self.store.get(entry['Key']))
                for file in registration['files']:
                    if file['name'] == 'processing-result.json':
                        final = json.loads(self.store.read_artifact(file))
                        require(final['plan'] != plan, 'failed work left a complete registration')

    async def retain_failure(self, target, error, injection, handle, task, request, audit_publication):
        # Durable original cause precedes every fallible cleanup/evidence operation.
        write(target/'failure.json', {'type': type(error).__name__, 'reason': str(error), 'injection': injection})
        outcomes = {}
        async def attempt(name, operation):
            try:
                await operation()
                outcomes[name] = {'ok': True}
            except BaseException as failure:
                outcomes[name] = {'ok': False, 'type': type(failure).__name__, 'reason': str(failure)}
            write(target/(name+'-outcome.json'), outcomes[name])
        async def cancel():
            await asyncio.wait_for(self.cancel_owned(handle), 30)
            self.active = None
        async def settle():
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        async def publication():
            if audit_publication:
                await asyncio.to_thread(self.no_complete, request)
        async def history():
            (target/'failure-history.json').write_text((await asyncio.wait_for(handle.fetch_history(), 20)).to_json())
        await attempt('cancel', cancel)
        await attempt('result-task', settle)
        await attempt('worker-stop', self.host.stop)
        await attempt('publication', publication)
        await attempt('history', history)
        write(target/'cleanup.json', outcomes)
        return outcomes

    async def trial(self, sid, mode, label, previous=None):
        from pdf_processing.processing_workflow import PDFProcessing
        from temporalio.converter import DataConverter
        fixture = next(x for x in self.bundle['fixtures'] if x['id'] == sid)
        target = self.root/label
        target.mkdir(exist_ok=False)
        profile_key = 'native-method' if mode == 'invalidation' else 'native-evidence' if mode in ('evidence', 'old-request') else sid
        profile = self.config['profiles'][profile_key]
        request = {'version': 3, 'completion': 'required_evidence_v1', 'profile': profile['id'],
            'request_id': 'q04-'+uuid.uuid4().hex, 'source_revision': fixture['source_revision']}
        if mode in ('replay', 'old-request'):
            if previous is None:
                raise ValueError('prior accepted request required')
            request = previous['request']
        elif previous and mode in ('restored', 'evidence', 'invalidation'):
            request['artifact'] = previous['request']['artifact']
        else:
            request['artifact'] = await asyncio.to_thread(capture, self.store, Path(self.config['bundle'])/'fixtures'/(sid+'.pdf'), sid+'.pdf')
        metadata = {'sid': sid, 'mode': mode, 'profile_key': profile_key, 'request': request,
            'profile': profile, 'producer': self.config['producer'], 'worker_generation': self.host.generation,
            'window': self.config['window'], 'config_sha256': sha(self.host.config_path.read_bytes())}
        write(target/'admission.json', metadata)
        await self.guard()
        started = time.time()
        workflow_id = self.config['run_id']+'-'+label+'-'+uuid.uuid4().hex
        # Persist exact phase ownership before submission so outer cleanup can
        # recover the start-workflow / workflow.json crash gap without guessing
        # from a run-wide prefix.
        write(target/'workflow-intent.json', {
            'workflow_id': workflow_id,
            'phase': self.root.name,
            'trial': label,
            'created': started,
        })
        handle = await self.client.start_workflow(PDFProcessing.run,
            {'request': request, 'activity_queue': self.config['queues'][profile_key]},
            id=workflow_id, task_queue=self.config['workflow_queue'],
            execution_timeout=timedelta(seconds=min(self.config['trial_seconds'], self.config['window']['ends_at']-self.config['window']['cleanup_seconds']-time.time())))
        self.active = handle
        write(target/'workflow.json', {'workflow_id': workflow_id, 'started': started})
        task = asyncio.create_task(handle.result())
        result = None
        injection = None
        retained = []
        worker_directory = self.host.current
        try:
            with (target/'progress.jsonl').open('x', buffering=1) as progress_log:
                while not task.done():
                    row = await self.guard()
                    progress = await handle.query(PDFProcessing.progress)
                    progress_log.write(json.dumps({'time': time.time(), 'progress': progress})+'\n')
                    if mode in ('drain', 'guard') and injection is None and progress['registered_pages'] == 5:
                        completed = [s for s in progress['steps'] if s['stage'] == 'group']
                        current = row.get('parser', {})
                        if completed and current.get('ready') and current.get('request_id') != completed[0].get('parser', {}).get('request_id'):
                            retained = [s['operation'] for s in completed]
                            if mode == 'guard':
                                (self.host.current/'stop-sampling').touch(exist_ok=False)
                                injection = {'kind': 'telemetry_loss', 'time': time.time()}
                            else:
                                write(target/'before-drain.json', {'time': time.time(), 'retained': retained, 'sample': row, 'progress': progress})
                                drained_at = time.time()
                                draining = asyncio.create_task(self.host.drain(current['pid']))
                                vm_rows = []
                                try:
                                    while not draining.done():
                                        validate_window(self.config['window'], time.time())
                                        observed = sample()
                                        require(observed['vm_oom_kill'] == row['vm_oom_kill'], 'OOM during replacement')
                                        require(observed['available'] >= self.config['window']['min_available_bytes'] and observed['psi_full_avg10'] <= self.config['window']['max_full_psi'], 'pressure during replacement')
                                        require(time.time()-drained_at <= self.config['window']['max_replacement_seconds'], 'replacement exceeded approved bound')
                                        vm_rows.append(observed)
                                        await asyncio.sleep(.5)
                                    injection = await draining
                                finally:
                                    if not draining.done():
                                        draining.cancel()
                                    await asyncio.gather(draining, return_exceptions=True)
                                    write(target/'replacement-vm.json', vm_rows)
                                check_coverage(read_rows(worker_directory/'samples.jsonl'), started, drained_at, self.config['window']['max_sample_gap_seconds'])
                                self.initial = None  # cgroup differs after Pod replacement; VM OOM must not change.
                                replacement = await self.guard()
                                require(replacement['vm_oom_kill'] == row['vm_oom_kill'], 'OOM across drain')
                                write(target/'drain.json', injection)
                    await asyncio.sleep(.5)
            result = await task
            write(target/'result.json', result)
            require(mode != 'guard', 'telemetry-loss guard did not interrupt active work')
            if mode == 'old-request':
                require(result['status'] == 'failed' and result['error']['code'] == 'worker_method_mismatch', 'old request reinterpreted')
                # Existing complete result belongs to original accepted plan and must remain unchanged.
                if previous is None:
                    raise ValueError('missing old accepted result')
                old_plan = self.store.resolve(previous['result']['plan'])
                require(old_plan is not None, 'old accepted plan disappeared')
                retained_plan = json.loads(self.store.read_artifact(next(f for f in old_plan['files'] if f['name'] == 'plan.json')))
                require(retained_plan['profile'] == previous['profile'], 'old profile mutated')
                (target/'history.json').write_text((await handle.fetch_history()).to_json())
                self.active = None
                metadata.update(result=result, verified=True)
                write(target/'accepted.json', metadata)
                return metadata
            accepted = await asyncio.to_thread(Consumer(self.store, target).verify, result, request, profile, fixture, Path(self.config['bundle'])/'oracles')
            mode_checks(mode, result, accepted, previous)
            if previous and mode != 'invalidation':
                require(json.loads((Path(previous['directory'])/'document.json').read_text()) == json.loads((target/'document.json').read_text()), 'full typed document differs')
            history = await handle.fetch_history()
            (target/'history.json').write_text(history.to_json())
            if mode == 'drain':
                require(injection is not None, 'drain injection missed')
                scheduled, attempts = {}, []
                for event in history.events:
                    if event.HasField('activity_task_scheduled_event_attributes'):
                        payload = (await DataConverter.default.decode(event.activity_task_scheduled_event_attributes.input.payloads))[0]
                        if payload.get('operation', {}).get('kind') == 'group':
                            scheduled[event.event_id] = payload['operation']
                    if event.HasField('activity_task_started_event_attributes'):
                        attr = event.activity_task_started_event_attributes
                        if attr.scheduled_event_id in scheduled:
                            operation = scheduled[attr.scheduled_event_id]
                            attempts.append({'range': [operation['start'], operation['end']], 'attempt': attr.attempt})
                write(target/'drain-proof.json', drain_checks(attempts, retained, result))
            finished = time.time()
            await asyncio.sleep(.6)
            await self.guard()
            coverage = check_coverage(read_rows(self.host.current/'samples.jsonl'), started if worker_directory == self.host.current else json.loads((self.host.current/'ready.json').read_text())['time'], finished, self.config['window']['max_sample_gap_seconds'])
            metadata.update(result=result, accepted=accepted, resource=coverage, verified=True,
                directory=str(target), workflow_id=workflow_id)
            write(target/'accepted.json', metadata)
            self.active = None
            return metadata
        except BaseException as error:
            outcomes = await self.retain_failure(target, error, injection, handle, task, request,
                mode != 'old-request' and (result is None or result.get('status') != 'complete'))
            failures = [name for name, outcome in outcomes.items() if not outcome['ok']]
            if failures:
                raise RuntimeError(f'{type(error).__name__}: {error}; cleanup/evidence failures: {", ".join(failures)}') from error
            if mode == 'guard' and injection and str(error) == 'resource telemetry lost':
                write(target/'guard-accepted.json', {'expected_failure': str(error), 'owned_runtime_stopped': True, 'complete_registration_absent': True})
                return {'verified': True, 'expected_failure': str(error)}
            raise


async def main(args):
    import boto3
    from temporalio.client import Client
    from temporalio.worker import Worker
    from pdf_processing.object_store import Store
    from pdf_processing.processing_workflow import PDFProcessing
    bundle = verify_bundle(args.bundle)
    window = json.loads(args.capacity.read_text())
    validate_window(window, time.time())
    require(args.capacity_approved, 'new capacity approval must be acknowledged')
    args.state.mkdir(exist_ok=True)
    state_path = args.state/'config.json'
    if args.phase == 'init':
        require(not state_path.exists(), 'new state required')
        s3 = boto3.client('s3', endpoint_url=args.endpoint)
        require(s3.get_bucket_versioning(Bucket=args.bucket).get('Status') == 'Enabled', 'versioned bucket required')
        store = Store(s3, args.bucket, args.prefix)
        require(not s3.list_objects_v2(Bucket=args.bucket, Prefix=store.prefix, MaxKeys=1).get('Contents'), 'unused object prefix required')
        originals = {e['id']: capture(store, args.bundle/'originals'/(e['id']+'.pdf'), 'original-'+e['id']+'.pdf') for e in bundle['fixtures']}
        profs = profiles(bundle, originals)
        run_id = 'q04-'+uuid.uuid4().hex
        config = {'run_id': run_id, 'profiles': profs, 'producer': bundle['producer'], 'bundle': str(args.bundle.resolve()),
            'state': str(args.state.resolve()), 'temporal': args.temporal, 'endpoint': args.endpoint, 'bucket': args.bucket,
            'prefix': args.prefix, 'window': window, 'model_cache': str(args.model_cache), 'python': sys.executable,
            'pod_namespace': args.pod_namespace, 'trial_seconds': args.trial_seconds,
            'workflow_queue': run_id+'-workflows', 'queues': {k: run_id+'-'+k for k in profs},
            'limits': {'max_bytes': 100*1024*1024, 'max_pages': 51, 'max_page_pixels': 20_000_000, 'preflight_seconds': 30, 'child_seconds': 540},
            'parser_budgets': {'startup_seconds': 120, 'no_progress_seconds': 180, 'terminate_seconds': 5, 'reap_seconds': 5, 'max_requests': 20},
            'drain_seconds': 30, 'bundle_sha256': sha((args.bundle/'inputs.json').read_bytes())}
        write(state_path, config)
        print('Immutable runtime state captured. Provision only a newly approved owned Pod if Pod mode is selected:', run_id)
        return
    config = json.loads(state_path.read_text())
    require(config['bundle_sha256'] == sha((args.bundle/'inputs.json').read_bytes()), 'input bundle differs from frozen run')
    # A renewed window is a new immutable controller config; never mutate accepted profiles.
    require(str(args.bundle.resolve()) == config['bundle'], 'runtime bundle path changed')
    config['window'] = window
    trial_root = args.state/args.name
    trial_root.mkdir(exist_ok=False)
    config_path = trial_root/'config.json'
    write(config_path, config)
    os.environ['Q02_SOURCE_ORACLE'] = str(args.bundle/'oracles/aima-code.json')
    client = await Client.connect(config['temporal'])
    store = Store(boto3.client('s3', endpoint_url=config['endpoint']), config['bucket'], config['prefix'])
    host = Host(config_path, trial_root, config)
    run = Run(config, bundle, trial_root, client, store, host)
    def previous(sid):
        require(args.fresh is not None, '--fresh matrix directory required')
        location = (Path(json.loads(args.fresh.read_text())[sid]) if args.fresh.is_file() else args.fresh/('fresh-'+sid))
        record = json.loads((location/'accepted.json').read_text())
        require(record['verified'] and record['sid'] == sid and record['mode'] == 'fresh' and record['producer'] == config['producer'] and record['profile'] == config['profiles'][sid], 'fresh baseline binding mismatch')
        require(record['request']['artifact']['key'].startswith(store.prefix+'sources/'), 'fresh baseline outside frozen namespace')
        return record
    try:
        async with Worker(client, task_queue=config['workflow_queue'], workflows=[PDFProcessing]):
            if args.phase == 'matrix':
                fresh = {}
                for entry in bundle['fixtures']:
                    sid = entry['id']
                    if args.fixture and sid not in args.fixture:
                        continue
                    for mode in ('fresh', 'restored', 'replay'):
                        await host.start()
                        run.initial = None
                        await run.admission()
                        record = await run.trial(sid, mode, mode+'-'+sid, fresh.get(sid))
                        if mode == 'fresh':
                            fresh[sid] = record
                        await host.stop()
                write(trial_root/'fresh-index.json', {sid: record['directory'] for sid, record in fresh.items()})
                if 'native' in fresh:
                    for mode in ('evidence', 'invalidation', 'old-request'):
                        await host.start()
                        run.initial = None
                        await run.admission()
                        await run.trial('native', mode, mode+'-native', fresh['native'])
                        await host.stop()
                    # Retained original accepted request still replays after the rejected reinterpretation.
                    await host.start()
                    run.initial = None
                    await run.admission()
                    await run.trial('native', 'replay', 'original-replay-after-rejection', fresh['native'])
            else:
                await host.start()
                await run.admission()
                if args.phase == 'warm':
                    results = [await run.trial(sid, 'warm', f'warm-{i}-{sid}', previous(sid)) for i, sid in enumerate(('06','07','08','native','06'))]
                    write(trial_root/'warm-proof.json', warm_checks(results))
                else:
                    await run.trial('native', args.phase, args.phase+'-native', previous('native'))
        await host.stop()
        write(trial_root/'phase-complete.json', {'phase': args.phase, 'fixtures': args.fixture, 'status': 'PASS bounded phase only', 'time': time.time()})
    except BaseException as error:
        write(trial_root/'phase-failure.json', {'type': type(error).__name__, 'reason': str(error)})
        raise
    finally:
        # A failed cancellation must never prevent the independent owned-host stop.
        errors = {}
        if run.active:
            try:
                await asyncio.wait_for(run.cancel_owned(run.active), 30)
            except BaseException as error:
                errors['cancel'] = str(error)
        try:
            await host.stop()
        except BaseException as error:
            errors['worker-stop'] = str(error)
        write(trial_root/'phase-cleanup.json', {'errors': errors})
        if errors and sys.exc_info()[0] is None:
            raise RuntimeError('phase cleanup failed: '+str(errors))


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--phase', choices=['init', 'matrix', 'warm', 'drain', 'guard'], required=True)
    for name in ('bundle', 'state', 'capacity'):
        cli.add_argument('--'+name, type=Path, required=True)
    cli.add_argument('--name', default='trial-'+uuid.uuid4().hex)
    cli.add_argument('--fresh', type=Path, help='Fresh matrix directory or JSON mapping fixture IDs to immutable fresh case directories')
    cli.add_argument('--fixture', action='append', choices=['native','06','07','08','09','10'], help='Subset for matrix only; allows separately coordinated windows')
    cli.add_argument('--model-cache', type=Path)
    for name in ('temporal', 'endpoint', 'bucket', 'prefix', 'pod-namespace'):
        cli.add_argument('--'+name)
    cli.add_argument('--trial-seconds', type=int, default=1800)
    cli.add_argument('--capacity-approved', action='store_true')
    args = cli.parse_args()
    if args.phase == 'init' and not all((args.temporal, args.endpoint, args.bucket, args.prefix, args.model_cache)):
        cli.error('init requires endpoints, new prefix, bucket and model cache')
    if not args.capacity_approved or args.trial_seconds <= 0:
        cli.error('new capacity approval and positive trial timeout required')
    if args.fixture and args.phase != 'matrix':
        cli.error('--fixture is only valid for matrix; warm order is fixed')
    if args.phase in ('warm', 'drain', 'guard') and args.fresh is None:
        cli.error('--fresh is required for warm/drain/guard')
    if sys.flags.optimize:
        cli.error('independent historical source oracles require assertions; do not use -O')
    with open(os.environ.get('PDF_QUALIFICATION_LOCK', '/tmp/data-ingestion-pdf-qualification.lock'), 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(main(args))
