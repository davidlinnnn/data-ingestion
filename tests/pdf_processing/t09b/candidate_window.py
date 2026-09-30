"""Group-10 T09b candidate using the retained warm-window implementation."""
import copy
import inspect
import math
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import baseline_window
from candidate_contract import IDENTITY, SCOPE

base = baseline_window.warm_pod_window_db.base
original_validate_contract = base.validate_contract


def candidate_profiles(profiles):
    result = copy.deepcopy(profiles)
    for profile in result.values():
        profile['group_pages'] = 10
        profile.pop('release', None)
        profile['release'] = 'q04-' + base.sha(base.canonical({
            'profile': profile, 'producer': base_config_producer,
        }).encode())
    return result


def configure_candidate(config, bundle):
    global base_config_producer
    original_validate_contract(config, bundle)
    base_config_producer = config['producer']
    config['profiles'] = candidate_profiles(config['profiles'])


def validate_contract(config, bundle):
    expected = base.q04_runtime.profiles(bundle, {
        fixture['id']: config['profiles'][fixture['id']]['content_evidence']
        ['reviews'][fixture['sha256']]['original_source']['artifact']
        for fixture in bundle['fixtures']
    })
    base.require(config['profiles'] == candidate_profiles(expected),
                 'group-10 profile contract changed')


def validate_scope(args):
    manifest = json.loads(args.integration_manifest.read_text())
    base.require(manifest['authorization_scope'] == SCOPE,
                 'group-10 authorization scope changed')
    base.require(base.sha(base.canonical(SCOPE).encode())
                 == args.authorization_scope_sha256
                 == manifest['authorization_scope_sha256'],
                 'group-10 scope digest changed')
    base.require(manifest['identity'] == IDENTITY == {
        'phase': args.name,
        'run_id': args.expected_run_id,
        'prefix': args.expected_prefix,
    }, 'group-10 runtime identity changed')
    return manifest


def mode_checks(mode, result, accepted, previous=None):
    base.require(mode == 'warm', 'group-10 candidate only supports warm trials')
    groups = [step for step in result['steps'] if step['stage'] == 'group']
    assembly = [step for step in result['steps'] if step['stage'] == 'assembly']
    base.require(len(groups) == math.ceil(result['pages'] / 10) and len(assembly) == 1,
                 'group-10 parse work mismatch')
    base.require(all(step['reused'] is False for step in groups + assembly),
                 'fresh group-10 work reused')
    ocr = [step for step in result['steps'] if step['stage'] == 'component_ocr']
    base.require(len(ocr) == result['selected_components'] == result['registered_components'],
                 'required OCR work coverage')
    base.require(all(step['reused'] is False for step in ocr), 'new request OCR was skipped')
    if previous is not None:
        base.require(accepted['document_sha256'] == previous['accepted']['document_sha256'],
                     'repeated fixture output differs')
        base.require(result['processing_result'] != previous['result']['processing_result'],
                     'new request reused complete identity')


def warm_checks(results):
    base.require([row['sid'] for row in results] == list(base.SEQUENCE),
                 'warm fixture sequence')
    groups = [step for row in results for step in row['result']['steps']
              if step['stage'] == 'group']
    base.require(len(groups) == 16, 'group-10 coverage')
    parser = [step['parser'] for step in groups]
    base.require(len({row['pid'] for row in parser}) == 1, 'unexpected parser replacement')
    base.require([row['restarts'] for row in parser] == [1] * 16,
                 'unexpected parser restart')
    base.require([row['recycles'] for row in parser] == [0] * 16,
                 'unexpected parser recycle')
    return {'groups': 16, 'pids': [parser[0]['pid']], 'recycles': 0}


def validate_process_evidence(summary, proof):
    result = base_validate_process_evidence(summary, proof)
    result['exits'] = len(proof['pids'])
    return result


def candidate_run_window():
    source = inspect.getsource(base.run_window)
    changes = (
        ('    config = json.loads(state_path.read_text())',
         '    config = json.loads(state_path.read_text())\n    configure_candidate(config, bundle)'),
        ('        "group_requests": 29,', '        "group_requests": 16,'),
        ('        "request_recycle": 20,', '        "request_recycle": None,'),
        ('        "parser_generations": 2,', '        "parser_generations": 1,'),
    )
    expected_counts = (1, 2, 1, 1)
    if tuple(source.count(old) for old, _ in changes) != expected_counts:
        raise RuntimeError('retained warm window contract changed')
    for old, new in changes:
        source = source.replace(old, new)
    namespace = dict(vars(base), configure_candidate=configure_candidate)
    exec(compile(source, __file__, 'exec'), namespace)
    return namespace['run_window']


base_config_producer = None
base_validate_process_evidence = base.validate_process_evidence
base.__doc__ = __doc__
base.validate_contract = validate_contract
base.validate_scope = validate_scope
base.warm_checks = warm_checks
base.validate_process_evidence = validate_process_evidence
base.q04_runtime.mode_checks = mode_checks
base.run_window = candidate_run_window()
main = base.main


if __name__ == '__main__':
    raise SystemExit(main())
