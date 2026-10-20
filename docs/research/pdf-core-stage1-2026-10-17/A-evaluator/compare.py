import collections
import datetime
import hashlib
import json
from pathlib import Path

import pypdfium2 as pdf

out = Path(__file__).parent
invp = out.parent / 'A/inventory.json'
inv = json.loads(invp.read_text())
assert hashlib.sha256(invp.read_bytes()).hexdigest() == '8f1961552cd6574a5d6f29614b1f5c297362d6310d63140ceb096ae349cbd593'
census = json.loads((out / 'source-census.json').read_text())
old = json.loads(Path('docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json').read_text())
rows = {}
pages = {}
provenance = []
for source in inv['sources']:
    name = source['source']
    path = Path(source['document_path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == source['document_sha256']
    assert hashlib.sha256(Path(source['pdf']['path']).read_bytes()).hexdigest() == source['pdf']['sha256']
    document = pdf.PdfDocument(source['pdf']['path'])
    rows[name] = source['rows']
    for n in source['physical_pages']:
        page = document[int(n)-1]
        textpage = page.get_textpage()
        raw = textpage.get_text_range()
        assert len(raw.encode('utf-16-le')) // 2 == textpage.count_chars()
        normalized = raw.replace('\r', '')
        assert normalized == (out / f'{name}-p{n}.txt').read_text()
        points = []
        utf16_index = normalized_index = 0
        for ch in raw:
            if ch != '\r':
                if not ch.isspace():
                    char_index = pdf.raw.FPDFText_GetCharIndexFromTextIndex(textpage.raw, utf16_index)
                    assert char_index >= 0
                    l, b, r, t = textpage.get_charbox(char_index)
                    points.append((normalized_index, (l+r)/2, page.get_height()-(b+t)/2))
                normalized_index += 1
            utf16_index += 2 if ord(ch) > 0xffff else 1
        pages[name, int(n)] = points
    provenance.append({k: source[k] for k in ['source', 'document_path', 'document_sha256', 'pdf']})


def fragments(row):
    return [fragment for entry in row.get('scope', {}).get('entries', []) for fragment in entry['fragments']]


def contains(fragment, page, x, y):
    if fragment['physical_page_1based'] != page:
        return False
    l, t, r, b = fragment['bbox_top_left_points']
    return l-2 <= x <= r+2 and t-2 <= y <= b+2


results = []
for unit in census['targets']:
    start, end = unit['span']['char_0based_halfopen']
    points = [point for point in pages[unit['source'], unit['physical_page']] if start <= point[0] < end]
    hits = collections.Counter()
    discovered = eligible = 0
    for pos, x, y in points:
        matches = [row for row in rows[unit['source']] if any(contains(f, unit['physical_page'], x, y) for f in fragments(row))]
        discovered += bool(matches)
        eligible += any(row['eligible'] for row in matches)
        hits.update(row['target_ref'] for row in matches)
    status = ('eligible_scope_present' if eligible == len(points) else 'partial_eligible_scope' if eligible else
              'discovered_unsupported' if discovered else 'not_discovered')
    results.append({'census_id': unit['id'], 'source': unit['source'], 'physical_page': unit['physical_page'],
                    'kind': unit['kind'], 'char_centers_evaluated': len(points), 'discovered_char_centers': discovered,
                    'eligible_char_centers': eligible, 'status': status,
                    'matching_rows': [{'ref': ref, 'matched_chars': count,
                                       'status': next(row['status'] for row in rows[unit['source']] if row['target_ref'] == ref)}
                                      for ref, count in hits.most_common()],
                    'scheduled': False, 'delivered': False})

visual_gaps = {
    **{i: 'table-owned required formula/code work absent from producer inventory'
       for i in ['E008', 'E009', 'E010', 'E017', 'E018', 'E019', 'E020']},
    'E021': 'caption formula scope discovered but unsupported serializer boundary',
    'E026': 'figure math descendants discovered but unsupported; extraction omits many visual math glyphs',
    'E031': 'algorithm lines eligible but heading shares unresolved mixed owner; complete source scope unsupported',
    'E032': 'prose continuation eligible but first fragment shares unresolved mixed owner; complete paragraph unsupported',
}
for result in results:
    result['visual_verdict'] = visual_gaps.get(result['census_id'], 'source scope eligible; actual delivery not established')

negative_results = []
for unit in census['ordinary_negatives']:
    text = (out / f"{unit['source']}-p{unit['physical_page']}.txt").read_text()
    lines = text.splitlines(keepends=True)
    first, last = unit['lines_1based']
    start, end = sum(map(len, lines[:first-1])), sum(map(len, lines[:last]))
    points = [point for point in pages[unit['source'], unit['physical_page']] if start <= point[0] < end]
    eligible = sum(any(row['eligible'] and any(contains(f, unit['physical_page'], x, y) for f in fragments(row))
                       for row in rows[unit['source']]) for _, x, y in points)
    negative_results.append({'negative_id': unit['id'], 'source': unit['source'],
                             'physical_page': unit['physical_page'], 'source_chars': len(points),
                             'eligible_chars': eligible,
                             'status': 'eligible_scope_present' if eligible == len(points) else 'unsupported_scope',
                             'semantic_negative_control': 'No new inference; inventory scope only. Saved-payload replay checks all non-target serialization literals unchanged.'})


def area(box):
    return max(0, box[2]-box[0]) * max(0, box[3]-box[1])


def overlap(a, b):
    return area([max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]) / max(area(a), 1e-10)


legacy = []
for unit in old['units']:
    source_fragments = []
    for old_fragment in unit['scope_fragments']:
        candidates = []
        for row in rows[unit['source']]:
            score = max([overlap(old_fragment['bbox_top_left_points'], f['bbox_top_left_points'])
                         for f in fragments(row) if f['physical_page_1based'] == old_fragment['physical_page_1based']] + [0])
            if score >= .45:
                candidates.append({'ref': row['target_ref'], 'eligible': row['eligible'], 'status': row['status'],
                                   'old_bbox_covered_fraction': score,
                                   'pages': sorted({f['physical_page_1based'] for f in fragments(row)})})
        source_fragments.append({'physical_page': old_fragment['physical_page_1based'], 'matches': candidates})
    common = set.intersection(*[{m['ref'] for m in f['matches'] if m['eligible']} for f in source_fragments])
    legacy.append({'old_unit_id': unit['unit_id'], 'prior_prepared': unit['prior_prepared'],
                   'fragments': source_fragments, 'common_eligible_owner_refs': sorted(common),
                   'geometry_status': 'eligible_source_owner_present' if common else 'source_coverage_unproved',
                   'delivery_status': 'not exercised by evaluator; not delivered in producer inventory'})

result = {'format': 'frozen-source-vs-producer-v1', 'evaluated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'source_census_freeze': json.loads((out / 'source-census.freeze.json').read_text()),
          'producer_inventory_path': str(invp), 'producer_inventory_sha256': hashlib.sha256(invp.read_bytes()).hexdigest(),
          'verified_sources': provenance,
          'method': 'Original nonspace glyph centers matched to frozen producer fragment envelopes, 2pt tolerance. Legacy same-source/page bbox overlap threshold0.45 is a locator, not semantic or delivery proof. No candidate outputs read.',
          'targets': results, 'census_status_counts': dict(collections.Counter(r['status'] for r in results)),
          'ordinary_negatives': negative_results,
          'ordinary_negative_status_counts': dict(collections.Counter(r['status'] for r in negative_results)),
          'legacy41': legacy, 'legacy_status_counts': dict(collections.Counter(r['geometry_status'] for r in legacy)),
          'source_census_count': 44, 'ordinary_negative_count': 27,
          'gate': 'fail', 'all_source_targets_eligible': False, 'model_accuracy': 'not evaluated',
          'denominator_policy': '44 grouped source spans and old41 are separate, not additive; table rows and figure contain explicit suboccurrences. No counts represent API jobs.',
          'exact_N_CF': inv['N_CF'], 'calls': 0, 'source_answers_leaked_to_producer': False}
(out / 'producer-coverage-comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print('CENSUS', result['census_status_counts'])
print('LEGACY', result['legacy_status_counts'])
for r in results:
    if r['status'] != 'eligible_scope_present':
        print(r['census_id'], r['status'], r['eligible_char_centers'], r['char_centers_evaluated'], r['visual_verdict'])
for r in legacy:
    if r['geometry_status'] != 'eligible_source_owner_present':
        print(r['old_unit_id'], r['geometry_status'])
