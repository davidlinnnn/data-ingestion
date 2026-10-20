"""Source-only caption-prefix page locator; never alter grid/point/Q13 gold."""
import collections
import datetime
import hashlib
import importlib.util
import json
import pathlib
import re
import pypdfium2 as pdfium

P = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('source_parser', P / 'build_html_oracle.py')
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


def main():
    d = json.loads((P / 'oracle.json').read_text())
    before = {t['id']: (t['cells'], t['points'], t['Q13'], t['Q13_reasons']) for t in d['tables']}
    m = json.loads((P.parent / 'html-manifest.json').read_text())
    jobs = {j['job_id']: j for j in m['jobs']}
    texts, normalized, evidence = {}, {}, []
    for jid in sorted({t['job_id'] for t in d['tables']}):
        job = jobs[jid]
        data = pathlib.Path(job['pdf']).read_bytes()
        assert parser.sha(data) == job['pdf_sha256']
        pdf = pdfium.PdfDocument(job['pdf'])
        pages = []
        for page in pdf:
            tp = page.get_textpage()
            pages.append(tp.get_text_range())
            tp.close()
            page.close()
        pdf.close()
        texts[jid] = pages
        normalized[jid] = [parser.norm(t) for t in pages]
    changed = []
    for table in d['tables']:
        if table['location']['scope'] != 'UNKNOWN' or not table['caption']:
            continue
        raw = re.sub(r'^\s*Table\s*[\w.]+\s*[:.]?\s*', '', table['caption'], flags=re.I)
        words = raw.split()
        attempts = []
        location = None
        for size in [20, 12, 10]:
            if len(words) < size:
                continue
            prefix = ' '.join(words[:size])
            key = parser.norm(prefix)
            if len(key) < 30:
                continue
            hits = [pg + 1 for pg, text in enumerate(normalized[table['job_id']]) if key in text]
            attempts.append({'words': size, 'prefix': prefix, 'normalized_key': key, 'matching_pages': hits})
            if len(hits) == 1:
                pg = hits[0]
                job = jobs[table['job_id']]
                scope = 'IN_SCOPE' if job['first'] <= pg <= job['last'] else 'OUT_OF_SCOPE'
                location = {'method': 'source PDF native text caption-prefix unique in entire original PDF',
                            'pages': [pg], 'scope': scope, 'prefix_words': size, 'prefix': prefix,
                            'normalized_prefix': key, 'pdf_sha256': table['pdf_sha256'],
                            'native_page_text_sha256': parser.sha(texts[table['job_id']][pg - 1].encode()),
                            'earlier_source_location': table['location']}
                break
        if location:
            table['location'] = location
            changed.append(table['id'])
        evidence.append({'id': table['id'], 'attempts': attempts, 'new_location': location,
                         'failure_means': 'UNKNOWN locator only, not source table absent.'})
    byid = {t['id']: t for t in d['tables']}
    for table in d['semantic_tables']:
        leaves = [byid[i] for i in table['leaf_ids']]
        table['pages'] = sorted({p for leaf in leaves for p in leaf['location']['pages']})
        scopes = {leaf['location']['scope'] for leaf in leaves}
        table['scope'] = next(iter(scopes)) if len(scopes) == 1 else 'UNKNOWN'
    checks = []
    for table in d['tables']:
        pages = table['location']['pages']
        if not pages:
            table['pdf_numeric_crosscheck'] = {'status': 'UNKNOWN_PAGE_LOCATION', 'missing_values_are_not_LATEXML_errors': True}
            continue
        tx = '\n'.join(texts[table['job_id']][pg - 1] for pg in pages)
        available = collections.Counter(parser.numeric(re.sub(r'\s+', ' ', tx)))
        expected = collections.Counter(p['value'] for p in table['points'])
        missing = expected - available
        result = {'id': table['id'], 'pages': pages,
                  'status': 'NO_NUMERIC_POINTS' if not expected else 'NUMERIC_MULTISET_PRESENT' if not missing else 'INCOMPLETE_NATIVE_TEXT_EVIDENCE',
                  'source_numeric_points': sum(expected.values()),
                  'source_numeric_values_missing_from_native_page_multiset': dict(missing),
                  'native_page_text_sha256': parser.sha(tx.encode()), 'source_error_confirmed': False,
                  'meaning': 'Source-only supporting page multiset; absent native tokens do not prove LaTeXML error; not row/column proof.'}
        table['pdf_numeric_crosscheck'] = result
        checks.append(result)
    assert before == {t['id']: (t['cells'], t['points'], t['Q13'], t['Q13_reasons']) for t in d['tables']}
    d['version'] = 'w3b-html-table-source-v3-locator-only-frozen'
    d['counts']['locations'] = dict(collections.Counter(t['location']['scope'] for t in d['tables']))
    d['counts']['semantic_scope'] = dict(collections.Counter(t['scope'] for t in d['semantic_tables']))
    d['counts']['numeric_crosscheck'] = dict(collections.Counter(c['status'] for c in checks))
    d['locator_v2'] = {'source_only': True, 'prefix_lengths': [20, 12, 10], 'unique_pages_in_entire_pdf_required': True,
                       'changed_leaf_count': len(changed), 'changed_leaf_ids': changed,
                       'grid_point_Q13_gold_unchanged_assertion': True, 'fixed_10_audit_not_resampled': True}
    (P / 'source-locator-v2.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    (P / 'source-pdf-numeric-crosscheck.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2) + '\n')
    (P / 'oracle.json').write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(d['counts']))
    print('newly located', len(changed))


if __name__ == '__main__':
    main()
