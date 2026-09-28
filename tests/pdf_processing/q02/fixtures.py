"""Private retained inputs and independently pinned qualification expectations."""
import copy
import hashlib
import json
import os
from pathlib import Path

BASELINE = Path(os.environ.get('Q02_BASELINE', '/private/tmp/aima-p2-main-recheck-20260915/baseline-document.json'))
SOURCE = 'b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980'


def document():
    raw = BASELINE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '7cbc44478d4a3d2f60256f6f92828b2396b1b932579436546e3d32b6f601f564'
    return json.loads(raw)


def policy():
    return {'method': 'local-function-block-v1', 'unresolved': 'reject', 'coverage': {
        'mode': 'selected_regions', 'source_sha256': SOURCE, 'regions': [
            {'id': 'first', 'page': 3, 'box': [100, 75, 500, 290], 'required_count': 1},
            {'id': 'second', 'page': 5, 'box': [100, 75, 500, 350], 'required_count': 1}]}}


def mutate(report, case, doc):
    result = copy.deepcopy(report)
    if not result['resolved']:
        return result
    members = result['resolved'][0]['members']
    if case == 'body_as_header':
        for member in members:
            if member['role'] == 'body': member['role'] = 'header'
    elif case == 'missing_role': del members[0]['role']
    elif case == 'missing_body': members.pop(1)
    elif case == 'missing_result': result['resolved'].pop()
    elif case == 'missing_candidate': result['candidates']['relationships'].pop(0)
    elif case == 'coverage': result['coverage']['selections'][0]['required_count'] = 0
    elif case == 'wrong_source': result['source'] = {'wrong': True}
    elif case == 'wrong_result': result['parsed_result'] = 'wrong'
    elif case == 'wrong_assembly': result['assembly'] = 'wrong'
    elif case == 'wrong_method': result['method'] = 'wrong'
    elif case == 'wrong_region': members[0]['box'][0] += 1
    elif case == 'wrong_type': members[0]['actual_type'] = 'code'
    elif case == 'bad_reference': members[0]['ref'] = '#/texts/missing'
    elif case == 'bool_range': members[0]['range'][0] = False
    elif case == 'short_header': members[0]['range'][1] -= 3
    elif case == 'wide_header': result['resolved'][1]['members'][0]['range'][0] = 0
    elif case == 'truncated_caption': members[-1]['range'][1] -= 5
    elif case == 'float_order': members[1]['order'] = 1.0
    elif case == 'bool_order': members[1]['order'] = True
    elif case == 'duplicate_order': members[1]['order'] = 0
    elif case == 'contradictory_order': members[0], members[1] = members[1], members[0]
    elif case == 'reordered':
        members[1], members[2] = members[2], members[1]
        for i, member in enumerate(members): member['order'] = i
    elif case == 'duplicate_member': members.insert(1, copy.deepcopy(members[1]))
    elif case == 'split':
        for relation in result['resolved']:
            split = []
            for member in relation['members']:
                start, end = member['range']
                mid = (start+end)//2
                for bounds in ([[start, mid], [mid, end]] if mid > start else [[start, end]]):
                    split.append({**member, 'range': bounds, 'order': len(split)})
            relation['members'] = split
    # Refresh hashes to prove role/range checks do more than detect stale hashes.
    items = {i['self_ref']: i for i in doc['texts']}
    for relation in result['resolved']:
        for member in relation['members']:
            if member['ref'] in items:
                member['text_sha256'] = hashlib.sha256(items[member['ref']]['text'][slice(*member['range'])].encode()).hexdigest()
    return result

FAILURES = ['body_as_header', 'missing_role', 'missing_body', 'missing_result', 'missing_candidate',
            'coverage', 'wrong_source', 'wrong_result', 'wrong_assembly', 'wrong_method', 'wrong_region',
            'wrong_type', 'bad_reference', 'bool_range', 'short_header', 'wide_header', 'truncated_caption',
            'float_order', 'bool_order', 'duplicate_order', 'contradictory_order', 'reordered', 'duplicate_member']
