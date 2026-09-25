"""Read-only Q04 preparation audit. No inference, services or release acceptance."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from pdf_processing.compatibility import dependencies

STAGES = ('group', 'assembly', 'selection', 'ocr', 'evidence', 'finalize')
BASE = ROOT / 'tests/pdf_processing'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_files(root, inventory):
    for name, expected in inventory.items():
        require(sha(root / name) == expected, f'hash mismatch: {root / name}')
    return len(inventory)


def impact(profile, producer, other_profile, other_producer):
    return {stage: dependencies(stage, profile, producer) !=
            dependencies(stage, other_profile, other_producer) for stage in STAGES}


def audit(fixtures, private_matrix, private_full):
    producer = {p.name: sha(p) for p in (ROOT / 'src/pdf_processing').glob('*.py')}
    q03 = read(BASE / 'q03/evidence/runtime-20260916/d-manifest.json')
    full = read(BASE / 'q03/evidence/runtime-20260916/manifest.json')
    require(producer == q03['producer'] == full['producer'], 'Q03 producer drift')
    require(sha(BASE / 'q03/runtime.py') == q03['driver_sha256'], 'Q03 driver drift')
    require(len(q03['cases']) == 22 and all(c['verified'] for c in q03['cases'].values()),
            'incomplete Q03 matrix')
    require(set(full['full_cases']) == {'fresh', 'reuse', 'exact', 'evidence'}
            and all(c['verified'] for c in full['full_cases'].values()), 'incomplete Q03 full cases')
    seal = read(BASE / 't09a_r3/evidence/seal.json')
    sealed = checked_files(BASE / 't09a_r3', seal['sha256'])
    prior = read(BASE / 't09a_r3/evidence/20260914-0b537d0-c/release-details.json')
    profile = copy.deepcopy(prior['profile'])
    profile['method']['continuation'] = {'version': 'column-edge-continuation-v1',
                                        'sha256': producer['continuation.py']}
    profile['content_evidence'] = {'version': 'typed-source-relationships-v2',
        'reviews': {}, 'relationships': {'method': 'local-function-block-v1',
        'coverage': {'mode': 'unknown'}, 'unresolved': 'allow_unknown'}}
    # This is a dependency probe, NOT a frozen executable request/profile.
    matrix = {'r3_to_integrated': impact(prior['profile'], prior['producer'], profile, producer)}
    policy = copy.deepcopy(profile)
    policy['content_evidence']['reviews'] = {'probe': 'evidence-only change'}
    matrix['evidence_policy'] = impact(profile, producer, policy, producer)
    for name in ('continuation.py', 'relationship_method.py'):
        changed = dict(producer)
        changed[name] = '0' * 64
        matrix[name] = impact(profile, producer, profile, changed)
    require(all(matrix['r3_to_integrated'].values()), 'unexpected R3 compatibility')
    require(matrix['evidence_policy'] == dict.fromkeys(STAGES[:4], False) |
            dict.fromkeys(STAGES[4:], True), 'evidence-only reuse contract changed')
    require(matrix['continuation.py'] == dict.fromkeys(STAGES[:2], True) |
            dict.fromkeys(STAGES[2:], False), 'continuation projection changed')
    require(matrix['relationship_method.py'] == matrix['evidence_policy'],
            'relationship method projection changed')
    pinned = read(BASE / 'q04/fixtures.json')
    fixture_checks = []
    for item in pinned:
        path = fixtures / (item['id'] + '.pdf')
        require(sha(path) == item['sha256'], f'fixture drift: {path}')
        if item['id'] != 'native':
            review = prior['profile']['content_evidence']['reviews'][item['sha256']]
            require([review['original_pages'][str(n)] for n in range(1, len(item['original_pages']) + 1)] == item['original_pages'],
                    f'page mapping differs from R3: {item["id"]}')
        fixture_checks.append({'id': item['id'], 'sha256': item['sha256']})
    private_count = checked_files(private_matrix, q03['private_files']) if private_matrix else None
    full_count = checked_files(private_full,
        full['private_evidence']['/private/tmp/q03-results-20260916-a']) if private_full else None
    return {'status': 'PREPARATION_ONLY', 'q04_accepted': False,
        'base_commit': '6d929e101a865f9e4bf887ace9dbb2866617dcae',
        'producer': producer, 'r3_sealed_files_checked': sealed,
        'q03_full_cases': len(full['full_cases']), 'q03_full_private_files_checked': full_count,
        'q03_matrix_cases': len(q03['cases']), 'q03_private_files_checked': private_count,
        'direct_stage_dependency_changes': matrix, 'fixtures_checked': fixture_checks,
        'note': 'False direct projection does not authorize reuse after upstream input identity changes.',
        'bindings': {str(p.relative_to(ROOT)): sha(p) for p in [
            BASE / 'q04/fixtures.json', BASE / 'q04/audit.py',
            BASE / 'q03/runtime.py', BASE / 'q03/reviewed-representation.json',
            BASE / 'q03/evidence/runtime-20260916/manifest.json',
            BASE / 'q03/evidence/runtime-20260916/d-manifest.json',
            BASE / 'q01_q02/evidence/runtime-20260916/summary.json',
            BASE / 't09a_r3/evidence/seal.json']}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--private-matrix', type=Path)
    parser.add_argument('--private-full', type=Path)
    parser.add_argument('--out', type=Path, required=True, help='New JSON file; never overwrite evidence')
    args = parser.parse_args()
    result = audit(args.fixtures, args.private_matrix, args.private_full)
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print('Preparation audit PASS; Q04 runtime remains unqualified.')


if __name__ == '__main__':
    main()
