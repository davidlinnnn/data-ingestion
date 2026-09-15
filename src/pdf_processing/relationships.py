"""Versioned, bounded method assertions over unchanged parsed text.

Coverage declarations are operator input, never inferred from emitted successes.
No source oracle, algorithm identity, or expected edge participates in discovery.
"""
import copy
import hashlib
import math

METHOD = 'local-function-block-v1'
POLICY = 'typed-source-relationships-v2'


def validate_policy(policy):
    if set(policy) != {'method', 'coverage', 'unresolved'} or policy['method'] != METHOD:
        raise ValueError('unsupported_relationship_method')
    if policy['unresolved'] not in ('reject', 'allow_unknown'):
        raise ValueError('unsupported_relationship_disposition')
    coverage = policy['coverage']
    if coverage == {'mode': 'unknown'}:
        if policy['unresolved'] != 'allow_unknown':
            raise ValueError('unknown_coverage_prohibited')
        return
    if set(coverage) != {'mode', 'source_sha256', 'regions'} or coverage['mode'] != 'selected_regions':
        raise ValueError('unsupported_relationship_coverage')
    sha = coverage['source_sha256']
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
        raise ValueError('invalid_coverage_source')
    regions = coverage['regions']
    if not isinstance(regions, list) or not regions:
        raise ValueError('missing_required_coverage')
    ids = set()
    for region in regions:
        if set(region) != {'id', 'page', 'box', 'required_count'}:
            raise ValueError('invalid_coverage_region')
        if not isinstance(region['id'], str) or not region['id'] or region['id'] in ids:
            raise ValueError('duplicate_coverage_id')
        ids.add(region['id'])
        if type(region['page']) is not int or region['page'] < 1:
            raise ValueError('invalid_coverage_page')
        box = region['box']
        if (not isinstance(box, list) or len(box) != 4 or
                any(type(x) not in (int, float) or not math.isfinite(x) for x in box) or
                not (0 <= box[0] < box[2] and 0 <= box[1] < box[3])):
            raise ValueError('invalid_coverage_box')
        if type(region['required_count']) is not int or region['required_count'] < 1:
            raise ValueError('invalid_required_count')
    for i, left in enumerate(regions):
        for right in regions[i+1:]:
            a, b = left['box'], right['box']
            if left['page'] == right['page'] and max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3]):
                raise ValueError('overlapping_coverage_regions')


def inside(member, region):
    a, b = member['box'], region['box']
    return member['page'] == region['page'] and b[0] <= a[0] <= a[2] <= b[2] and b[1] <= a[1] <= a[3] <= b[3]


def build(document, source, parsed_result, assembly, policy):
    from .relationship_method import derive, digest
    validate_policy(policy)
    declared = policy['coverage']
    if declared['mode'] == 'selected_regions' and declared['source_sha256'] != source['artifact']['sha256']:
        raise ValueError('relationship_coverage_source_mismatch')
    candidates = derive(document, source['artifact']['sha256'])
    resolved, unresolved, selections = [], [], []
    regions = declared.get('regions', [])
    for region in regions:
        size = document['pages'][str(region['page'])]['size']
        if region['box'][2] > size['width'] or region['box'][3] > size['height']:
            raise ValueError('coverage_region_outside_page')
        found = [r for r in candidates['relationships'] if inside(r['members'][0], region)]
        selections.append({'id': region['id'], 'required_count': region['required_count'],
                           'candidate_count': len(found)})
        if len(found) != region['required_count']:
            unresolved.append({'selection': region['id'], 'reason': 'required_count_mismatch', 'region': region})
        for relation in found:
            record = {**copy.deepcopy(relation), 'selection': region['id'], 'kind': 'algorithm', 'method': METHOD}
            record['id'] = digest({'selection': region['id'], 'members': relation['members']})
            if (relation['disposition'] != 'candidate' or relation.get('symbol_uncertainty') or
                    not all(inside(m, region) for m in relation['members'])):
                record['disposition'] = 'unresolved'
                record['reason'] = ('symbol_disposition_not_supported' if relation.get('symbol_uncertainty')
                                    else 'incomplete_or_outside_selected_region')
                unresolved.append(record)
            else:
                record['disposition'] = 'resolved'
                resolved.append(record)
    if declared['mode'] == 'unknown':
        unresolved.append({'reason': 'discovery_coverage_unknown', 'evidence': 'content_evidence_pages'})
    invalid = [m for m in candidates['unresolved_input_regions'] if any(inside(m, r) for r in regions)]
    if invalid:
        unresolved.append({'reason': 'invalid_source_ranges', 'members': invalid})
    return {'version': 1, 'policy': POLICY, 'method': METHOD, 'source': source,
            'parsed_result': parsed_result, 'assembly': assembly, 'document_sha256': digest(document),
            'coverage': {'declaration': declared, 'selections': selections, 'outside_selection': 'unknown'},
            'candidates': candidates, 'resolved': resolved, 'unresolved': unresolved,
            'source_review': {'status': 'not_performed'}, 'quality_accepted': False, 'canonical_accepted': False}


def member_stream(members, document):
    """Compare exact ordered coverage while permitting adjacent range fragmentation."""
    from .relationship_method import segments
    parts = segments(document)
    items = {item['self_ref']: item for item in document['texts']}
    stream = []
    ranks = {'header': 0, 'body': 1, 'caption': 2}
    previous = -1
    seen = set()
    for i, member in enumerate(members):
        if type(member.get('order')) is not int or member['order'] != i:
            raise ValueError('invalid_relationship_order')
        role = member.get('role')
        if role not in ranks or ranks[role] < previous:
            raise ValueError('invalid_relationship_role')
        previous = ranks[role]
        start, end = member['range']
        item = items[member['ref']]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(item['text']):
            raise ValueError('invalid_relationship_range')
        if member['text_sha256'] != hashlib.sha256(item['text'][start:end].encode()).hexdigest():
            raise ValueError('relationship_text_mismatch')
        if not any(p['ref'] == member['ref'] and p['page'] == member['page'] and p['box'] == member['box']
                   and p['actual_type'] == member['actual_type'] and p['valid_range']
                   and p['range'][0] <= start < end <= p['range'][1] for p in parts):
            raise ValueError('relationship_region_mismatch')
        for offset in range(start, end):
            key = (member['ref'], offset)
            if key in seen:
                raise ValueError('duplicate_relationship_membership')
            seen.add(key)
            stream.append((member['ref'], member['page'], offset, role, tuple(member['box']), member['actual_type']))
    if {m['role'] for m in members} != set(ranks):
        raise ValueError('missing_relationship_role')
    return stream


def validate(report, document, source, parsed_result, assembly, policy):
    """Publication barrier: fresh independent discovery plus frozen required coverage.

    This validates method consistency, not source quality. Independent source
    oracles belong to qualification, not to this runtime validator.
    """
    expected = build(document, source, parsed_result, assembly, policy)
    try:
        if set(report) != set(expected):
            raise ValueError('relationship_fields_mismatch')
        for field in expected:
            if field != 'resolved' and report[field] != expected[field]:
                raise ValueError('relationship_mismatch_' + field)
        if len(report['resolved']) != len(expected['resolved']):
            raise ValueError('incomplete_required_relationships')
        for actual, required in zip(report['resolved'], expected['resolved']):
            if {k: v for k, v in actual.items() if k != 'members'} != {k: v for k, v in required.items() if k != 'members'}:
                raise ValueError('relationship_result_mismatch')
            if member_stream(actual['members'], document) != member_stream(required['members'], document):
                raise ValueError('relationship_membership_mismatch')
        if report['unresolved'] and policy['unresolved'] == 'reject':
            raise ValueError('required_relationship_unresolved')
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('invalid_relationship_output') from error
