"""Prove active worker-telemetry loss aborts one owned native workflow."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import time

from candidate.warm_pod_window_r import validate_contract
from candidate.warm_v3_reference import verify_v3_bundle
from candidate.yolo_candidate_measure import AttributedCandidateRun
from candidate.yolo_reviewed_window import evaluate_resource_gate
from consumer import canonical, require, sha
from contracts import validate_window
from host_an import Host
from prepare import verify_bundle
from sentinel.aima_attribution_telemetry_q import StrictAttributionCollector
import q04_runtime


PHASE = 'telemetry-loss-pod-cgroup-at'
SCOPE = {'fixtures': ['native'], 'modes': ['guard'], 'max_requests': 20,
         'automatic_retry': False, 'measurement': 'active worker telemetry-loss abort and owned cleanup'}


def validate_scope(args):
    manifest = json.loads(args.integration_manifest.read_text())
    require(manifest['authorization_scope'] == SCOPE
            and manifest['authorization_scope_sha256'] == args.authorization_scope_sha256
            == sha(canonical(SCOPE).encode()), 'telemetry-loss scope changed')
    require(manifest['identity'] == {'phase': args.name, 'run_id': args.expected_run_id,
                                    'prefix': args.expected_prefix}, 'telemetry-loss identity changed')
    return manifest


def verify_abort(root):
    target = root / 'guard-native'
    failure = json.loads((target / 'failure.json').read_text())
    accepted = json.loads((target / 'guard-accepted.json').read_text())
    cleanup = json.loads((target / 'cleanup.json').read_text())
    history = json.loads((target / 'failure-history.json').read_text())['events']
    stopped = json.loads((root / 'worker-1/stopped.json').read_text())
    progress = [json.loads(line) for line in (target / 'progress.jsonl').read_text().splitlines()]
    samples = [json.loads(line) for line in (root / 'worker-1/samples.jsonl').read_text().splitlines()]
    window = json.loads((root / 'config.json').read_text())['window']
    injected_at = failure['injection']['time']
    before = [row for row in samples if row['time'] <= injected_at]
    active = [row for row in progress if row['time'] <= injected_at]
    require(before and active, 'missing pre-injection observations')
    sample = before[-1]
    current = sample['parser']
    status = active[-1]['progress']
    completed = [step for step in status['steps'] if step['stage'] == 'group']
    maximum_gap = window['max_sample_gap_seconds']
    observed_gap = (target / 'failure.json').stat().st_mtime - samples[-1]['time']
    require(status['registered_pages'] == 5 and status['status'] == 'parsing'
            and completed and current.get('ready')
            and current.get('request_id') != completed[0].get('parser', {}).get('request_id')
            and 0 <= injected_at - sample['time'] <= maximum_gap
            and samples[-1]['time'] <= injected_at + .5
            and observed_gap > maximum_gap
            and (root / 'worker-1/stop-sampling').stat().st_mtime <=
                (target / 'failure.json').stat().st_mtime,
            'injected telemetry loss not proven by active progress and sample gap')
    require(failure['reason'] == accepted['expected_failure'] == 'resource telemetry lost'
            and failure['injection']['kind'] == 'telemetry_loss'
            and accepted['owned_runtime_stopped'] and accepted['complete_registration_absent']
            and (root / 'worker-1/stop-sampling').exists()
            and json.loads((target / 'publication-outcome.json').read_text())['ok']
            and not (target / 'accepted.json').exists(), 'active telemetry loss did not fail closed')
    require(all(value['ok'] for value in cleanup.values())
            and stopped['parser_absent'] and stopped['scratch_absent'], 'owned cleanup incomplete')
    require(not any(e['eventType'] == 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED'
                    for e in history), 'interrupted workflow completed')
    return {'injection': failure['injection'], 'history_events': len(history),
            'last_sample_time': samples[-1]['time'], 'observed_gap_seconds': observed_gap,
            'registered_pages_at_injection': status['registered_pages'],
            'active_parser_request_id': current['request_id']}


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
    validate_scope(args)
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
            result = await run.trial('native', 'guard', 'guard-native')
            require(result == {'verified': True, 'expected_failure': 'resource telemetry lost'},
                    'guard trial did not return expected failure')
            verify_abort(root)
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
                await collector.process_transition('failure_worker_shutdown', host.stop)
            else:
                await host.stop()
        except BaseException as error:
            primary = primary or error
        try:
            if collector.started:
                collector.observe('owned_cleanup_finished', source='telemetry_loss_window_at',
                                  meaning='worker_returned_after_owned_cleanup')
                outcome = collector.stop(expect_cancel=True,
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
        'workload': 'active worker telemetry-loss abort', 'workload_succeeded': True,
        'business_workflow_succeeded': False, 'expected_abort_verified': True,
        'qualification_complete': outcome.qualification_complete,
        'process_attribution_complete': summary['process_attribution_complete'],
        'cgroup_resource_complete': outcome.cgroup_resource_complete,
        'resource_gate': gate, 'automatic_retry': False})
    q04_runtime.write(root / 'reviewed-window-contract.json', {
        'status': 'PASS active worker telemetry-loss abort', 'fixtures': ['native'],
        'modes': ['guard']})
    q04_runtime.write(root / 'phase-complete.json',
                      {'status': 'PASS active worker telemetry-loss abort'})


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
