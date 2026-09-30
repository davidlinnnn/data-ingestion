"""One measured native recovery trial at the declared 10-page durable boundary."""
import copy
from datetime import datetime
import inspect
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from recovery_trial import Run
import q04_runtime

from candidate import process_drain_window_be as base
from candidate.warm_v3_reference_db import reviewed_reference_checker, verify_v3_bundle
from t09b_host import Host


class AttributedRecoveryRun(base.AttributedCandidateRun, Run):
    """Keep existing attribution/cancellation hooks around the recovery trial."""


def scope(group_pages):
    base.require(group_pages in (5, 10), 'unreviewed recovery group size')
    return {'fixtures': ['native'], 'modes': ['drain'], 'group_pages': group_pages,
            'durable_pages': 10, 'max_requests': 20, 'automatic_retry': False,
            'measurement': 'owned worker-process drain and matched native recovery'}


def validate_scope(args):
    manifest = json.loads(args.integration_manifest.read_text())
    expected = scope(manifest['authorization_scope']['group_pages'])
    base.require(manifest['authorization_scope'] == expected
                 and manifest['authorization_scope_sha256'] == args.authorization_scope_sha256
                 == base.sha(base.canonical(expected).encode()), 'recovery scope changed')
    base.require(manifest['identity'] == {'phase': args.name, 'run_id': args.expected_run_id,
                                         'prefix': args.expected_prefix}, 'recovery identity changed')
    return manifest


def configure_profiles(config, manifest):
    size = manifest['authorization_scope']['group_pages']
    if size == 10:
        profile = copy.deepcopy(config['profiles']['native'])
        profile['group_pages'] = size
        profile.pop('release')
        profile['release'] = 'q04-' + base.sha(base.canonical({
            'profile': profile, 'producer': config['producer']}).encode())
        config['profiles']['native'] = profile


def verify_drain(root, manifest):
    target = root / 'drain-native'
    load = lambda path: json.loads(path.read_text())
    accepted = load(target / 'accepted.json')
    result = accepted['result']
    base.require(accepted['verified'] and result['status'] == 'complete'
                 and result['processing_complete'] and result['registered_pages'] == 51
                 and accepted['accepted']['document_sha256'] == manifest['native_document_sha256']
                 and load(target / 'checks.json') == manifest['native_checks'],
                 'recovery output differs from full uninterrupted reference')
    old = load(root / 'worker-1/stopped.json')
    first = load(root / 'worker-1/host.json')
    second = load(root / 'worker-2/host.json')
    drain = load(target / 'drain.json')
    base.require(drain['scope'] == 'owned_worker_process'
                 and drain['old_generation'] == 1 and drain['new_generation'] == 2
                 and first['pod'] is None and second['pod'] is None
                 and first['ready']['pid'] != second['ready']['pid']
                 and old['parser_absent'] and old['scratch_absent'], 'recovery worker cleanup failed')
    proof = load(target / 'drain-proof.json')
    size = manifest['authorization_scope']['group_pages']
    base.require(proof['durable_pages'] == 10 and proof['retried_range'] == [11, 10 + size]
                 and proof['attempt'] == 2 and len(proof['retained']) == 10 // size,
                 'matched recovery proof changed')
    history = load(target / 'history.json')['events']
    base.require(history[-1]['eventType'] == 'EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED',
                 'recovery workflow not complete')
    terminal = datetime.fromisoformat(history[-1]['eventTime'].replace('Z', '+00:00')).timestamp()
    before = load(target / 'before-drain.json')
    stopped = load(root / 'worker-1/drain-signal.json')
    base.require(before['time'] <= stopped['signal_requested_at']
                 <= stopped['stopped_observed_at'] <= terminal,
                 'recovery signal timing is not ordered')
    q04_runtime.write(target / 'recovery-cost.json', {
        'durable_pages': 10, 'retried_range': proof['retried_range'],
        'repeated_pages': size, 'retained_groups': len(proof['retained']),
        'drain_request_to_business_complete_seconds': terminal - before['time'],
        'loss_to_business_complete_seconds_bounds': [
            terminal - stopped['stopped_observed_at'],
            terminal - stopped['signal_requested_at']],
        'signal_timing': stopped,
        'scope': 'one measured worker-process drain; not a recovery distribution'})


source = inspect.getsource(base.run_window)
old = '    validate_contract(config, bundle)'
if source.count(old) != 1:
    raise RuntimeError('retained recovery profile seam changed')
namespace = dict(vars(base), Host=Host, validate_scope=validate_scope,
                 verify_drain=verify_drain, configure_profiles=configure_profiles,
                 AttributedCandidateRun=AttributedRecoveryRun,
                 reviewed_reference_checker=reviewed_reference_checker,
                 verify_v3_bundle=verify_v3_bundle)
exec(compile(source.replace(old, old + '\n    configure_profiles(config, manifest)'),
             __file__, 'exec'), namespace)
base.run_window = namespace['run_window']

if __name__ == '__main__':
    raise SystemExit(base.main())
