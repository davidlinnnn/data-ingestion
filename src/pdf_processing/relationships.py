"""Versioned, bounded method assertions over unchanged parsed text.

Coverage declarations are operator input, never inferred from emitted successes.
No source oracle, algorithm identity, or expected edge participates in discovery.
"""
import copy
import hashlib
import math

METHOD = 'local-function-block-v1'
POLICY = 'typed-source-relationships-v2'
REPRESENTATION = 'source-reviewed-representation-v1'


def validate_policy(policy):
    if set(policy) not in ({'method', 'coverage', 'unresolved'},
                           {'method', 'coverage', 'unresolved', 'representation'}) or policy['method'] != METHOD:
        raise ValueError('unsupported_relationship_method')
    if policy['unresolved'] not in ('reject', 'allow_unknown'):
        raise ValueError('unsupported_relationship_disposition')
    coverage = policy['coverage']
    if 'representation' in policy:
        review = policy['representation']
        if (set(review) != {'version', 'reviews'} or review['version'] != REPRESENTATION
                or not isinstance(review['reviews'], list)):
            raise ValueError('unsupported_representation_policy')
        if coverage.get('mode') != 'selected_regions' or policy['unresolved'] != 'reject':
            raise ValueError('reviewed_representation_requires_structure')
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
    if 'representation' in policy:
        validate_representation_policy(policy)


def validate_representation_policy(policy):
    """Closed, opt-in review contract; unreviewed content never inherits an allowance."""
    import unicodedata
    try:
        reviews = policy['representation']['reviews']
        regions = {r['id']: r for r in policy['coverage']['regions']}
        selections = [r['selection'] for r in reviews]
        if len(selections) != len(set(selections)) or set(selections) != set(regions):
            raise ValueError('incomplete_representation_reviews')
        ids = set()
        for review in reviews:
            if set(review) != {'id', 'selection', 'page', 'source_sha256', 'reviewer', 'reason', 'streams', 'isolated_symbols'}:
                raise ValueError('unsupported_representation_review')
            if any(not isinstance(review[k], str) or not review[k] for k in ('id', 'reviewer', 'reason')) or review['id'] in ids:
                raise ValueError('invalid_representation_review_identity')
            ids.add(review['id'])
            region = regions[review['selection']]
            if (review['source_sha256'] != policy['coverage']['source_sha256']
                    or type(review['page']) is not int or review['page'] != region['page']
                    or region['required_count'] != 1):
                raise ValueError('representation_review_attribution_mismatch')
            if set(review['streams']) != {'header_body', 'caption'}:
                raise ValueError('incomplete_representation_streams')
            for name, stream in review['streams'].items():
                if set(stream) != {'source_compacted_sha256', 'extracted_compacted_sha256', 'differences'}:
                    raise ValueError('unsupported_representation_stream')
                for key in ('source_compacted_sha256', 'extracted_compacted_sha256'):
                    sha = stream[key]
                    if not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
                        raise ValueError('invalid_representation_digest')
                if not isinstance(stream['differences'], list):
                    raise ValueError('invalid_representation_differences')
                for difference in stream['differences']:
                    pairs = {'minus_hyphen': ('−', '-'), 'combining_control': ('\x07', ''), 'caption_control': ('\x02', '')}
                    if (set(difference) != {'kind', 'source_range', 'extracted_range', 'source', 'extracted', 'disposition'}
                            or difference['kind'] not in pairs
                            or (difference['source'], difference['extracted']) != pairs[difference['kind']]
                            or (difference['kind'] == 'caption_control') != (name == 'caption')):
                        raise ValueError('unsupported_representation_difference')
                    if difference['disposition'] not in ('retain_uninterpreted', 'release_gate'):
                        raise ValueError('unsupported_representation_disposition')
                    for key in ('source_range', 'extracted_range'):
                        bounds = difference[key]
                        if (not isinstance(bounds, list) or len(bounds) != 2
                                or any(type(n) is not int for n in bounds) or not 0 <= bounds[0] <= bounds[1]):
                            raise ValueError('invalid_representation_comparison_range')
            if not isinstance(review['isolated_symbols'], list):
                raise ValueError('invalid_isolated_symbol_reviews')
            for symbol in review['isolated_symbols']:
                if (set(symbol) != {'text', 'disposition'} or not isinstance(symbol['text'], str) or not symbol['text']
                        or not all(unicodedata.category(c).startswith('M') for c in symbol['text'])
                        or symbol['disposition'] not in ('retain_uninterpreted', 'release_gate')):
                    raise ValueError('unsupported_isolated_symbol_review')
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('invalid_representation_policy') from error


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
            if (relation['disposition'] != 'candidate' or (relation.get('symbol_uncertainty') and 'representation' not in policy) or
                    not all(inside(m, region) for m in relation['members'])):
                record['disposition'] = 'unresolved'
                record['reason'] = ('symbol_disposition_not_supported' if relation.get('symbol_uncertainty')
                                    else 'incomplete_or_outside_selected_region')
                unresolved.append(record)
            else:
                if 'representation' in policy:
                    member_stream(record['members'], document)
                    record['representation'] = reviewed_representation(record, document, region, policy)
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
    from .relationship_method import digest
    expected = build(document, source, parsed_result, assembly, policy)
    try:
        if set(report) != set(expected):
            raise ValueError('relationship_fields_mismatch')
        for field in expected:
            if field != 'resolved' and digest(report[field]) != digest(expected[field]):
                raise ValueError('relationship_mismatch_' + field)
        if len(report['resolved']) != len(expected['resolved']):
            raise ValueError('incomplete_required_relationships')
        for actual, required in zip(report['resolved'], expected['resolved']):
            # JSON fingerprints distinguish true/1 and 1.0/1 in symbol evidence
            # and comparison coordinates; Python container equality does not.
            if digest({k: v for k, v in actual.items() if k != 'members'}) != digest({k: v for k, v in required.items() if k != 'members'}):
                raise ValueError('relationship_result_mismatch')
            if member_stream(actual['members'], document) != member_stream(required['members'], document):
                raise ValueError('relationship_membership_mismatch')
        if report['unresolved'] and policy['unresolved'] == 'reject':
            raise ValueError('required_relationship_unresolved')
        for relation in report['resolved']:
            representation = relation.get('representation')
            if representation:
                observations = representation['isolated_symbols'] + [
                    d for stream in representation['streams'].values() for d in stream['differences']]
                if any(o['disposition'] != 'retain_uninterpreted' for o in observations):
                    raise ValueError('representation_release_gate')
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('invalid_relationship_output') from error


def reviewed_representation(relation, document, region, policy):
    """Apply an operator's source review after discovery, never as an answer table.

    Compacted sequences are only a comparison coordinate system. Every emitted
    extraction range indexes unchanged raw text; absent characters have no range.
    """
    reviews = policy['representation']['reviews']
    # validate_policy has already checked review identity, attribution and shape.
    review = next(r for r in reviews if r['selection'] == region['id'])
    items = {item['self_ref']: item for item in document['texts']}
    evidence = {'page': region['page'], 'box': region['box'], 'scope': 'selected_source_region',
                'coordinate_space': 'page-local TOPLEFT PDF points'}
    streams = {}
    for name, roles in [('header_body', ('header', 'body')), ('caption', ('caption',))]:
        members = [m for m in relation['members'] if m['role'] in roles]
        characters = [(c, m, offset) for m in members for offset in range(*m['range'])
                      if not (c := items[m['ref']]['text'][offset]).isspace()]
        text = ''.join(c for c, _, _ in characters)
        reviewed = review['streams'][name]
        if hashlib.sha256(text.encode()).hexdigest() != reviewed['extracted_compacted_sha256']:
            raise ValueError('unreviewed_representation_content')
        differences = []
        reconstructed, source_end, extracted_end = '', 0, 0
        for difference in reviewed['differences']:
            start, end = difference['extracted_range']
            left, right = difference['source_range']
            if (any(type(n) is not int for n in (start, end, left, right))
                    or not extracted_end <= start <= end <= len(text)
                    or left != source_end + start - extracted_end
                    or right != left + len(difference['source'])
                    or text[start:end] != difference['extracted']):
                raise ValueError('invalid_representation_comparison_range')
            reconstructed += text[extracted_end:start] + difference['source']
            source_end, extracted_end = right, end
            raw = []
            for _, member, offset in characters[start:end]:
                # Keep raw provenance, not an invented glyph position.
                raw.append({**member, 'range': [offset, offset+1],
                            'text_sha256': hashlib.sha256(items[member['ref']]['text'][offset].encode()).hexdigest()})
            differences.append({**copy.deepcopy(difference), 'raw_extracted_ranges': raw,
                                'evidence': evidence})
        reconstructed += text[extracted_end:]
        if hashlib.sha256(reconstructed.encode()).hexdigest() != reviewed['source_compacted_sha256']:
            raise ValueError('unreviewed_representation_difference')
        streams[name] = {**copy.deepcopy(reviewed), 'differences': differences,
                         'comparison_coordinates': 'whitespace-compacted Unicode code points; not raw item ranges',
                         'source_native_equal': not differences}
    symbols = relation.get('symbol_uncertainty', [])
    if len(symbols) != len(review['isolated_symbols']):
        raise ValueError('unreviewed_isolated_symbols')
    isolated = []
    size = document['pages'][str(region['page'])]['size']
    for member, annotation in zip(symbols, review['isolated_symbols']):
        text = items[member['ref']]['text'][slice(*member['range'])]
        if text != annotation['text'] or not inside(member, region):
            raise ValueError('isolated_symbol_review_mismatch')
        isolated.append({**copy.deepcopy(annotation), 'member': copy.deepcopy(member),
                         'position_in_body': None, 'evidence': {**evidence, 'scope': 'full_page_context',
                            'box': [0, 0, size['width'], size['height']]}})
    return {'version': REPRESENTATION, 'review_id': review['id'], 'reviewer': review['reviewer'],
            'reason': review['reason'], 'assertion_origin': 'profile_source_review_not_discovery',
            'streams': streams, 'isolated_symbols': isolated, 'evidence': evidence,
            'source_native_equal': all(s['source_native_equal'] for s in streams.values()) and not isolated,
            'semantic_equivalence': 'not_claimed', 'raw_extraction_modified': False}
