"""Prove native Activity recovery after one owned worker-process drain."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import time

import consumer
from candidate.warm_pod_window_r import validate_contract
from candidate.warm_v3_reference import reviewed_reference_checker, verify_v3_bundle
from candidate.yolo_candidate_measure import AttributedCandidateRun
from candidate.yolo_reviewed_window import evaluate_resource_gate
from consumer import canonical, require, sha
from contracts import validate_window
from host_an import Host
from prepare import verify_bundle
import q04_runtime
from sentinel.aima_attribution_telemetry_q import StrictAttributionCollector


PHASE = 'process-drain-pod-cgroup-ba'
SCOPE = {'fixtures': ['native'], 'modes': ['drain'], 'max_requests': 20,
         'automatic_retry': False, 'measurement': 'owned worker-process drain and native recovery'}


def validate_scope(args):
    manifest = json.loads(args.integration_manifest.read_text())
    require(manifest['authorization_scope'] == SCOPE
            and manifest['authorization_scope_sha256'] == args.authorization_scope_sha256
            == sha(canonical(SCOPE).encode()), 'process-drain scope changed')
    require(manifest['identity'] == {'phase': args.name, 'run_id': args.expected_run_id,
                                    'prefix': args.expected_prefix}, 'process-drain identity changed')
    return manifest


def verify_drain(root, manifest):
    target = root / 'drain-native'
    accepted = json.loads((target / 'accepted.json').read_text())
    drain = json.loads((target / 'drain.json').read_text())
    proof = json.loads((target / 'drain-proof.json').read_text())
    old = json.loads((root / 'worker-1/stopped.json').read_text())
    first = json.loads((root / 'worker-1/host.json').read_text())
    second = json.loads((root / 'worker-2/host.json').read_text())
    history = json.loads((target / 'history.json').read_text())['events']
    result = accepted['result']
    require(accepted['verified'] and result['status'] == 'complete'
            and result['processing_complete'] and result['registered_pages'] == 51
            and accepted['accepted']['document_sha256'] == manifest['native_document_sha256'],
            'native drain output differs from accepted baseline')
    require(drain['scope'] == 'owned_worker_process'
            and drain['old_generation'] == 1 and drain['new_generation'] == 2
            and first['pod'] is None and second['pod'] is None
            and first['ready']['pid'] != second['ready']['pid']
            and old['parser_absent'] and old['scratch_absent'],
            'local process drain left old work or failed to replace worker')
    require(proof['retried_range'] == [6, 10] and proof['attempt'] == 2
            and len(proof['retained']) == 1,
            'process drain retry proof changed')
    require(history[-1]['eventType'] == 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED',
            'process drain workflow did not complete')
    return {'pages': result['registered_pages'],
            'history_events': len(history), 'retried_range': proof['retried_range']}


async def reviewed_drain_trial(run, bundle):
    original = consumer.check_reference
    consumer.check_reference = reviewed_reference_checker(bundle, original)
    try:
        return await run.trial('native', 'drain', 'drain-native')
    finally:
        consumer.check_reference = original


async def run_window(args):
    import boto3
    from temporalio.client import Client
    from temporalio.worker import Worker
    from pdf_processing.object_store import Store
    from pdf_processing.processing_workflow import PDFProcessing

    bundle = verify_bundle(args.bundle)
    verify_v3_bundle(args.bundle)
    window = json.loads(args.capacity.read_text())
    validate_window(window, time.time())
    require(args.capacity_approved, 'capacity approval required')
    manifest = validate_scope(args)
    config = json.loads((args.state / 'config.json').read_text())
    require(config['window'] == window and config['run_id'] == args.expected_run_id
            and config['prefix'] == args.expected_prefix
            and config['bundle'] == str(args.bundle.resolve())
            and config['bundle_sha256'] == sha((args.bundle / 'inputs.json').read_bytes())
            and config['producer'] == bundle['producer'], 'initialized runtime changed')
    validate_contract(config, bundle)
    root = args.state / args.name
    root.mkdir(exist_ok=False)
    measurement = args.state / (args.name + '-measurement')
    measurement.mkdir(exist_ok=False)
    q04_runtime.write(root / 'config.json', config)
    collector = StrictAttributionCollector(
        measurement / 'resource-attribution.jsonl',
        measurement / 'resource-attribution-summary.json',
        observation_root=root, interval_seconds=args.attribution_interval_seconds,
        attribution_gap_seconds=args.attribution_gap_seconds,
        lifecycle_lock_path=measurement / 'process-lifecycle.lock')
    client = await Client.connect(config['temporal'])
    store = Store(boto3.client('s3', endpoint_url=config['endpoint']),
                  config['bucket'], config['prefix'])
    host = Host(root / 'config.json', root, config)
    run = AttributedCandidateRun(config, bundle, root, client, store, host,
                                 collector=collector)
    previous_lock = os.environ.get('PDF_PROCESS_LIFECYCLE_LOCK')
    previous_timeout = os.environ.get('PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS')
    primary = None
    outcome = None
    try:
        os.environ['PDF_PROCESS_LIFECYCLE_LOCK'] = str(collector.lifecycle_lock_path)
        os.environ['PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS'] = str(args.attribution_gap_seconds)
        async with Worker(client, task_queue=config['workflow_queue'], workflows=[PDFProcessing]):
            collector.start()
            await host.start()
            await run.admission()
            await reviewed_drain_trial(run, args.bundle)
            verify_drain(root, manifest)
    except BaseException as error:
        primary = error
    finally:
        if run.active:
            try:
                await asyncio.wait_for(run.cancel_owned(run.active), 30)
            except BaseException:
                pass
        try:
            if collector.started and host.process is not None:
                await collector.process_transition('controlled_worker_shutdown', host.stop)
            else:
                await host.stop()
        except BaseException as error:
            primary = primary or error
        try:
            if collector.started:
                collector.observe('owned_cleanup_finished', source='process_drain_window_ba',
                                  meaning='worker_returned_after_owned_cleanup')
                outcome = collector.stop(expect_cancel=False,
                    require_no_warm_fresh_overlap=True)
        finally:
            for key, previous in (('PDF_PROCESS_LIFECYCLE_LOCK', previous_lock),
                                  ('PDF_PROCESS_LIFECYCLE_LOCK_TIMEOUT_SECONDS', previous_timeout)):
                if previous is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous
    if primary is not None:
        q04_runtime.write(root / 'phase-failure.json',
                          {'type': type(primary).__name__, 'reason': str(primary)})
        raise primary
    require(outcome is not None and outcome.attribution_complete,
            'independent process attribution incomplete')
    summary = json.loads((measurement / 'resource-attribution-summary.json').read_text())
    samples = [json.loads(line) for line in
               (measurement / 'resource-attribution.jsonl').read_text().splitlines()]
    gate = evaluate_resource_gate(samples, summary)
    q04_runtime.write(measurement / 'all-sample-resource-gate.json', gate)
    require(gate['status'] == 'PASS', 'independent resource gate failed')
    q04_runtime.write(measurement / 'measurement-contract.json', {
        'workload': 'native owned worker-process drain/recovery', 'workload_succeeded': True,
        'qualification_complete': outcome.qualification_complete,
        'process_attribution_complete': summary['process_attribution_complete'],
        'cgroup_resource_complete': outcome.cgroup_resource_complete,
        'resource_gate': gate, 'automatic_retry': False})
    q04_runtime.write(root / 'reviewed-window-contract.json', {
        'status': 'PASS native owned worker-process drain/recovery',
        'fixtures': ['native'], 'modes': ['drain']})
    q04_runtime.write(root / 'phase-complete.json',
                      {'status': 'PASS native owned worker-process drain/recovery'})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'state', 'capacity', 'integration-manifest'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('name', 'expected-run-id', 'expected-prefix', 'authorization-scope-sha256'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--attribution-interval-seconds', type=float, default=.25)
    parser.add_argument('--attribution-gap-seconds', type=float, default=1)
    parser.add_argument('--capacity-approved', action='store_true')
    args = parser.parse_args(argv)
    if args.attribution_interval_seconds != .25 or args.attribution_gap_seconds != 1:
        parser.error('reviewed attribution cadence changed')
    asyncio.run(run_window(args))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
