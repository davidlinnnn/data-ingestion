"""One native current-v3 Activity Pod-loss trial; controller owns the Pod transition."""

import argparse
import asyncio
import json
from pathlib import Path
import time

from candidate.process_drain_window_be import reviewed_drain_trial
from candidate.warm_pod_window_r import validate_contract
from candidate.warm_v3_reference import verify_v3_bundle
from consumer import canonical, require, sha
from contracts import validate_window
from pod_loss_bridge_bg import Host
from prepare import verify_bundle
from q04_runtime import Run, write


PHASE = 'pod-loss-pod-cgroup-bg'
SCOPE = {'fixtures': ['native'], 'modes': ['drain'], 'max_requests': 20,
         'automatic_retry': False,
         'measurement': 'in-flight owned Activity Pod loss and native recovery'}


def validate_scope(args):
    manifest = json.loads(args.integration_manifest.read_text())
    require(manifest['authorization_scope'] == SCOPE
            and manifest['authorization_scope_sha256'] == args.authorization_scope_sha256
            == sha(canonical(SCOPE).encode()), 'Pod-loss scope changed')
    require(manifest['identity'] == {'phase': args.name, 'run_id': args.expected_run_id,
                                    'prefix': args.expected_prefix}, 'Pod-loss identity changed')
    return manifest


def verify_drain(root: Path, manifest: dict) -> dict:
    target = root / 'drain-native'
    accepted = json.loads((target / 'accepted.json').read_text())
    result = accepted['result']
    drain = json.loads((target / 'drain.json').read_text())
    proof = json.loads((target / 'drain-proof.json').read_text())
    controller = json.loads((root.parents[1] / 'pod-loss-control/2-drain.reply.json').read_text())
    first = json.loads((root / 'worker-1/host.json').read_text())
    second = json.loads((root / 'worker-2/host.json').read_text())
    history = json.loads((target / 'history.json').read_text())['events']
    require(accepted['verified'] and result['status'] == 'complete'
            and result['processing_complete'] and result['registered_pages'] == 51
            and result['selected_components'] == result['registered_components'] == 7
            and accepted['accepted']['document_sha256'] == manifest['native_document_sha256']
            and accepted['accepted']['checks']['full_reference_graph_sha256']
            == manifest['native_graph_sha256'],
            'native Pod-loss output differs from accepted baseline')
    old_uid, new_uid = drain['old_pod_uid'], drain['new_pod_uid']
    require(drain['scope'] == 'owned_pod' and old_uid != new_uid
            and first['pod']['uid'] == old_uid and second['pod']['uid'] == new_uid,
            'Pod-loss identity or worker replacement unproven')
    require(controller['status'] == 'PASS' and controller['old_pod_uid'] == old_uid
            and controller['pod_uid'] == new_uid
            and controller['old_runtime_absent'] is True
            and controller['old_scratch_absent'] is True,
            'old Pod runtime/scratch absence unproven')
    require(proof['retried_range'] == [6, 10] and proof['attempt'] == 2
            and len(proof['retained']) == 1,
            'Pod-loss retry proof changed')
    require(history[-1]['eventType'] == 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED',
            'Pod-loss workflow did not complete')
    return {'pages': result['registered_pages'], 'old_pod_uid': old_uid,
            'new_pod_uid': new_uid, 'retried_range': proof['retried_range']}


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
    write(root / 'config.json', config)
    client = await Client.connect(config['temporal'])
    store = Store(boto3.client('s3', endpoint_url=config['endpoint']),
                  config['bucket'], config['prefix'])
    host = Host(root / 'config.json', root, config)
    run = Run(config, bundle, root, client, store, host)
    primary = None
    try:
        async with Worker(client, task_queue=config['workflow_queue'], workflows=[PDFProcessing]):
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
            await host.stop()
        except BaseException as error:
            primary = primary or error
    if primary is not None:
        write(root / 'phase-failure.json',
              {'type': type(primary).__name__, 'reason': str(primary)})
        raise primary
    write(root / 'phase-complete.json',
          {'status': 'PASS native in-flight Activity Pod-loss workflow/oracle'})


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'state', 'capacity', 'integration-manifest'):
        cli.add_argument('--' + name, type=Path, required=True)
    for name in ('name', 'expected-run-id', 'expected-prefix',
                 'authorization-scope-sha256'):
        cli.add_argument('--' + name, required=True)
    cli.add_argument('--capacity-approved', action='store_true')
    args = cli.parse_args(argv)
    asyncio.run(run_window(args))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
