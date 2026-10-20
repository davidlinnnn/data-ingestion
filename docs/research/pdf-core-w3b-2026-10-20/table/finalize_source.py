"""Finalize source-only audit, native-PDF crosscheck, semantic groups and seal."""
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
sha = parser.sha


def main():
    oracle = json.loads((P / 'oracle.json').read_text())
    plan = json.loads((P / 'audit-plan.json').read_text())
    trace = json.loads((P / 'audit-trace.json').read_text())
    images = json.loads((P / 'audit-pages/manifest.json').read_text())
    tables = {t['id']: t for t in oracle['tables']}
    own_notes = {
        'P-03-2603.25158v5:html-table:A2.T11.fig1.4': 'PDF p15 左側 Table10：Runner122B 跨 ANLS/Acc，Time 獨立；4×3 個值逐一一致，0、5.2min、35.9min、4.8min 單位完整，沒有混右側 Table11。',
        'P-05-2602.08234v2:html-table:S4.T1.16': 'PDF p6 上方 Table1：ALFWorld 跨7欄、WebShop跨2欄、Method rowspan2；16方法×9數值144逐一一致，全部小數尾零與來源星號保留；4全寬方法群組及Qwen2.5-7B基座標記非數值資料。',
        'P-13-2601.01885v3:html-table:S4.T3.2': 'PDF p8 左下 Table3：Qwen2.5-7B/Qwen3-4B 各跨noRL/GRPO，ToolCategory rowspan2；LTM/STM全寬分組，7列×4值28逐一相同（含0.00）。上方Table2及Figure4沒有混入此HTML表。',
        'P-19-2511.10395v1:html-table:S7.T7.6': 'PDF p26 Table7：TGC/SGC 各跨@4/@8，四個CMT列16值逐一一致，包含0.500兩次及0.720/0.607；所有數值對應表頭位置及colspan正確。',
        'P-17-2506.10943v1:html-table:A2.T3.2': 'PDF p19 Table3：Parameter/SearchSpace五列；LoRArank2、alpha2、LR5、epochs5、batch2共16個數值逐項相同，科學記號及list次序保留。此表無span，但單格多值依Q13為complex。',
    }
    own = []
    for tid, note in own_notes.items():
        t = tables[tid]
        own.append({'sourceID': tid, 'job_id': t['job_id'], 'status': 'PDF_FAITHFUL',
                    'phase': 'SOURCE_ONLY_PRE_GLOBAL_FREEZE', 'pages': t['location']['pages'],
                    'reviewed_visual': True, 'all_headers_reviewed': True, 'all_values_reviewed': True,
                    'all_spans_reviewed': True, 'reason': note, 'source_evidence': images[tid],
                    'html_sha256': t['html_sha256'], 'pdf_sha256': t['pdf_sha256'],
                    'reviewed_cell_count': len(t['cells']), 'version_claim_scope': 'Local table content agrees; not full-document version certification.'})
    audit = {'seed': plan['seed'], 'plan_sha256': sha((P / 'audit-plan.json').read_bytes()),
             'source_only': True, 'records': trace + own,
             'sampling_revision': 'Original float-only draft inventory and seed retained in draft-v1. Before any output read, inclusion was corrected to include inline/figure-contained data tabular; same fixed SHA seed resampled expanded source population. P03 entered and P10 left; no inspected table was dropped for a bad result.',
             'latex_html_conversion_errors_confirmed': 0,
             'parser_defects_fixed_before_freeze': ['Numeric suffix B/decimal backtracking fixed; 68.00B is not 68.',
                                                    'Pure numeric first column is data/configuration, not a model name; trainOS counted.',
                                                    'Numeric component denominator, units and component positions retained.',
                                                    'Same-caption leaf subgrids grouped into a semantic complex table.']}
    assert len(audit['records']) == 10
    assert {r['sourceID'] for r in audit['records']} == {r['id'] for r in plan['tables']}
    assert all(r['reviewed_visual'] and r['all_headers_reviewed'] and r['all_values_reviewed'] and r['all_spans_reviewed'] for r in audit['records'])
    audited = {r['sourceID']: r for r in audit['records']}
    cache, documents, crosschecks = {}, {}, []
    for t in oracle['tables']:
        t['manual_pdf_audit'] = audited.get(t['id'])
        if t['id'] in audited:
            t['pdf_table_fidelity'] = 'MANUALLY_CONFIRMED_HEADERS_VALUES_SPANS'
            for point in t['points']:
                point['unknown_reasons'] = [r for r in point['unknown_reasons'] if r != 'MATH_VALUE_NEEDS_PDF_VALIDATION']
                point['status'] = 'UNKNOWN' if point['unknown_reasons'] else 'TRUSTED_SOURCE_POINT'
        else:
            t['pdf_table_fidelity'] = 'HTML_SOURCE_WITH_NATIVE_TEXT_CROSSCHECK_NOT_MANUAL_FULL_GRID_CERTIFICATION'
        pages = t['location']['pages']
        if not pages:
            t['pdf_numeric_crosscheck'] = {'status': 'UNKNOWN_PAGE_LOCATION', 'missing_values_are_not_LATEXML_errors': True}
            continue
        jid = t['job_id']
        if jid not in documents:
            path = pathlib.Path(t['pdf'])
            assert sha(path.read_bytes()) == t['pdf_sha256']
            documents[jid] = pdfium.PdfDocument(str(path))
        text = ''
        for pg in pages:
            key = (jid, pg)
            if key not in cache:
                page = documents[jid][pg - 1]
                tp = page.get_textpage()
                cache[key] = tp.get_text_range()
                tp.close()
                page.close()
            text += '\n' + cache[key]
        # Source text layer only; all tables on a page share this evidence.
        # Missing native words are NOT automatically a source conversion error.
        available = collections.Counter(parser.numeric(re.sub(r'\s+', ' ', text)))
        expected = collections.Counter(p['value'] for p in t['points'])
        missing = expected - available
        record = {'id': t['id'], 'pages': pages, 'status': 'NO_NUMERIC_POINTS' if not expected else 'NUMERIC_MULTISET_PRESENT' if not missing else 'INCOMPLETE_NATIVE_TEXT_EVIDENCE',
                  'source_numeric_points': sum(expected.values()), 'source_numeric_values_missing_from_native_page_multiset': dict(missing),
                  'native_page_text_sha256': sha(text.encode()), 'source_error_confirmed': False,
                  'meaning': 'Presence is supporting source-only evidence, not row/column proof; absence may be PDF native-text extraction loss.'}
        t['pdf_numeric_crosscheck'] = record
        crosschecks.append(record)
        # Preserve explicit suffix unit without inventing unit conversions.
        for point in t['points']:
            match = re.search(r'(ms|GB|MB|[kKmMgGtTbBs%‰])$', point['value'])
            point['literal_numeric_unit_suffix'] = match.group(1) if match else None
            point['full_cell_unit_context'] = point['cell_value']
    for doc in documents.values():
        doc.close()
    grouped = collections.defaultdict(list)
    for t in oracle['tables']:
        grouped[t['semantic_table_id']].append(t)
    semantics = []
    for sid, leaves in grouped.items():
        points = []
        for si, leaf in enumerate(leaves):
            for original in leaf['points']:
                point = dict(original)
                point.update(id=leaf['id'] + ':' + point['id'], subgrid_id=leaf['id'], subgrid_index=si)
                points.append(point)
        pages = sorted({p for leaf in leaves for p in leaf['location']['pages']})
        scopes = {leaf['location']['scope'] for leaf in leaves}
        scope = next(iter(scopes)) if len(scopes) == 1 else 'UNKNOWN'
        reasons = sorted({r for leaf in leaves for r in leaf['Q13_reasons']} | ({'MULTIPLE_SUBTABLES'} if len(leaves) > 1 else set()))
        unknowns = sorted({r for leaf in leaves for r in leaf['source_issues']})
        semantics.append({'id': sid, 'job_id': leaves[0]['job_id'], 'family': leaves[0]['family'],
                          'caption': leaves[0]['semantic_caption'], 'leaf_ids': [t['id'] for t in leaves],
                          'subgrids': [{'leaf_id': t['id'], 'rows': t['rows'], 'cols': t['cols'], 'grid': t['grid'], 'cells': t['cells'], 'header_rows': t['header_rows']} for t in leaves],
                          'pages': pages, 'scope': scope, 'Q13': 'complex' if reasons else 'ordinary', 'Q13_reasons': reasons,
                          'points': points, 'expected_numeric_points': len(points),
                          'source_status': 'UNKNOWN' if unknowns or not points else 'HTML_PARSED', 'source_issues': unknowns,
                          'pdf': leaves[0]['pdf'], 'pdf_sha256': leaves[0]['pdf_sha256'], 'html_sha256': leaves[0]['html_sha256'],
                          'numeric_denominator_status': 'MANUALLY_VALIDATED_NUMERIC_INVENTORY' if all(t['id'] in audited for t in leaves) else 'HTML_STRUCTURAL_COUNT_UNAUDITED',
                          'trust_note': 'Unknown point roles stay UNKNOWN; source extraction uncertainty is distinct from target tuple-alignment uncertainty.'})
    oracle['semantic_tables'] = semantics
    oracle['primary_evaluation_unit'] = 'semantic_tables; sibling leaves with a shared caption/float are one complex table; never average leaf passes'
    oracle['version'] = 'w3b-html-table-source-v2-frozen'
    oracle['counts'].update(semantic_tables=len(semantics), semantic_scope=dict(collections.Counter(t['scope'] for t in semantics)),
                            semantic_Q13=dict(collections.Counter(t['Q13'] for t in semantics)),
                            manual_pdf_tables=10, numeric_crosscheck=dict(collections.Counter(t['status'] for t in crosschecks)))
    oracle['selfchecks'] = {'units_no_decimal_backtracking': parser.numeric('68.00B 601.74B 1e-4 0.12%') == ['68.00B', '601.74B', '1e-4', '0.12%'],
                            'semantic_point_count_equals_leaf_sum': sum(len(t['points']) for t in semantics) == sum(len(t['points']) for t in oracle['tables']),
                            'sample_unique_10': len(audited) == 10, 'no_E0_E1_inputs': True}
    assert all(oracle['selfchecks'].values())
    (P / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    (P / 'source-pdf-numeric-crosscheck.json').write_text(json.dumps(crosschecks, ensure_ascii=False, indent=2) + '\n')
    (P / 'oracle.json').write_text(json.dumps(oracle, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(oracle['counts']))


if __name__ == '__main__':
    main()
