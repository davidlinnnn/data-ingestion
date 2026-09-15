"""Frozen P2 scoring logic, adapted imports/paths only; never used by production."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
from .role_oracle import coverage, expected_roles, roles_and_order
from .source_segments import segments, digest
ROOT = Path(__file__).resolve().parent
SOURCE = 'b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980'
# Independent source regions frozen in ORACLE.md, not fed to derive().
CASES = [(3, 'BREADTH-FIRST-SEARCH', '3.11', [110,80,475,255], [120,270,495,286]),
         (5, 'UNIFORM-COST-SEARCH', '3.14', [110,80,475,267], [120,280,495,346]),
         (9, 'DEPTH-LIMITED-SEARCH', '3.17', [110,80,475,247], [120,260,495,278]),
         (10, 'ITERATIVE-DEEPENING-SEARCH', '3.18', [110,90,475,142], [120,155,495,197])]


def inside(box, region):
    return region[0] <= box[0] <= box[2] <= region[2] and region[1] <= box[1] <= box[3] <= region[3]


def validate_binding(doc, report):
    assert report['source_sha256'] == SOURCE, 'wrong_source'
    assert report['document_sha256'] == digest(doc), 'wrong_document_version'
    items = {x['self_ref']: x for x in doc['texts']}
    for relation in report['relationships']:
        for m in relation['members'] + relation.get('symbol_uncertainty', []):
            assert m['ref'] in items, 'dangling_member'
            item = items[m['ref']]
            start, end = m['range']
            assert 0 <= start < end <= len(item['text']), 'invalid_member_range'
            assert hashlib.sha256(item['text'][start:end].encode()).hexdigest() == m['text_sha256'], 'wrong_member_content'
            assert any(s['ref'] == m['ref'] and s['page'] == m['page'] and s['box'] == m['box']
                       and s['range'][0] <= start < end <= s['range'][1] for s in segments(doc)), 'missing_source_region'


def score(doc, report):
    validate_binding(doc, report)
    parts = segments(doc)
    items = {i['self_ref']: i for i in doc['texts']}
    transcripts = json.loads(Path('/private/tmp/t09a-code-oracle.json').read_text())
    caption_oracle = json.loads((ROOT/'caption-oracle.json').read_text())
    historical_hashes = json.loads((ROOT.parents[1]/'t09a/evidence/code-source-oracle.json').read_text())
    results = []
    for page, name, number, region, caption_region in CASES:
        transcript = next(t for t in transcripts if t['processed_page'] == page)
        expected_hash = next(t['source_text_sha256'] for t in historical_hashes if t['processed_page'] == page)
        assert hashlib.sha256(transcript['source_native_text'].encode()).hexdigest() == expected_hash
        reviewed = [s for s in parts if s['page'] == page and inside(s['box'], region)]
        expected_caption = [s for s in parts if s['page'] == page and inside(s['box'], caption_region)]
        expected = expected_roles(reviewed, transcript)
        reviewed_characters = coverage(reviewed)
        matches = [r for r in report['relationships'] if any(
            coverage([m]) & reviewed_characters for m in r['members'])]
        if len(matches) != 1:
            results.append({'page': page, 'structure_pass': False, 'reason': 'missing_or_duplicate_relationship'})
            continue
        relation = matches[0]
        members = relation['members'] + relation.get('symbol_uncertainty', [])
        role_ok, order_ok = roles_and_order(relation, expected)
        body_members = [m for m in members if m.get('role') != 'caption']
        caption_members = [m for m in members if m.get('role') == 'caption']
        coverage_ok = coverage(body_members) == coverage(reviewed) and coverage(caption_members) == coverage(expected_caption)
        ordered = [m for m in relation['members'] if m.get('role') in ('header', 'body')]
        content = ''.join(items[m['ref']]['text'][m['range'][0]:m['range'][1]] for m in ordered)
        equal = ''.join(content.split()) == ''.join(transcript['source_native_text'].split())
        caption_content = ''.join(items[m['ref']]['text'][m['range'][0]:m['range'][1]] for m in caption_members)
        caption_review = next(c for c in caption_oracle if c['page'] == page)
        caption_hash = hashlib.sha256(''.join(caption_content.split()).encode()).hexdigest()
        caption_ok = caption_hash == caption_review['reviewed_extracted_whitespace_compacted_sha256']
        expected_symbol = page in (9,10)
        symbols = relation.get('symbol_uncertainty', [])
        symbol_ok = (len(symbols) == 1 and items[symbols[0]['ref']]['text'] == '\u0338') if expected_symbol else not symbols
        # For symbols, source-native comparison remains unequal; never normalize to green.
        actual_sequence = ''.join(content.split())
        source_sequence = ''.join(transcript['source_native_text'].split())
        differences = [{'source_range': [i,j], 'extracted_range': [k,l],
                        'source': source_sequence[i:j], 'extracted': actual_sequence[k:l]}
                       for tag,i,j,k,l in difflib.SequenceMatcher(None, source_sequence, actual_sequence, autojunk=False).get_opcodes() if tag != 'equal']
        # Source-reviewed localized differences; keep them unequal and inspectable.
        expected_differences = [(chr(7), '')] if page == 10 else [('−', '-'), (chr(7), '')]
        outside_uncertainty_equal = [(d['source'], d['extracted']) for d in differences] == expected_differences
        sequence_ok = equal if not expected_symbol else symbol_ok and outside_uncertainty_equal
        results.append({'page': page, 'algorithm': name, 'structure_pass': role_ok and order_ok and coverage_ok and caption_ok and sequence_ok and relation['disposition']=='candidate',
                        'exact_membership': coverage_ok, 'exact_roles': role_ok, 'order_consistent': order_ok, 'caption_correct': caption_ok,
                        'caption_source_native_equal': caption_hash == caption_review['whitespace_compacted_sha256'],
                        'caption_uncertainty': caption_review['uncertainty'],
                        'source_native_whitespace_only_equal': equal, 'localized_symbol_uncertainty': expected_symbol and symbol_ok,
                        'semantic_equivalence': 'not_claimed', 'sequence_differences': differences,
                        'content_verdict': 'exact_whitespace_only' if equal else 'localized_representation_uncertainty',
                        'members': relation['members'],
                        'symbols': symbols})
    return results

