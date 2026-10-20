"""Frozen HTML source -> saved native table tuples; no conversion/inference.

Packed rows/headers are UNKNOWN, never zipped back using source values.
"""
import argparse
import collections
import copy
import decimal
import hashlib
import html
import importlib.util
import json
import pathlib
import re
import sys
import unicodedata
from markdown_it import MarkdownIt
from lxml import html as lhtml

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
RESEARCH = ROOT.parent
NUMBER = re.compile(r'(?<![A-Za-z0-9_.])[-+−–]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)(?:[eE][−+-]?\d+)?(?:\s*(?:ms|GB|MB|[kKmMgGtTbBs%‰]))?(?![A-Za-z0-9_.])')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def norm(value):
    return ''.join(c.casefold() for c in unicodedata.normalize('NFKC', value) if c.isalnum())


def numbers(value):
    return [re.sub(r'\s+', '', m.group().replace('−', '-').replace('–', '-')) for m in NUMBER.finditer(value)]


def numberkey(value):
    value = re.sub(r'\s+', '', value.replace('−', '-').replace('–', '-').replace(',', ''))
    match = re.fullmatch(r'([+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?)(.*)', value)
    if not match:
        return value
    return str(decimal.Decimal(match[1]).normalize()) + '|' + match[2]


def labelmatch(source, target):
    a, b = norm(source), norm(target)
    if not a or not b:
        return False
    if a == b:
        return True
    # Exact full label substring, not fuzzy edit distance; native packed labels
    # may locate a row but do not thereby establish numeric cell association.
    return len(a) >= 4 and a in b


def resolve(doc, ref):
    parts = ref.replace('#/', '').split('/')
    node = doc
    for part in parts:
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def native_tables(doc, path):
    result = []
    for table in doc.get('tables', []):
        captions = []
        for ref in table.get('captions', []):
            item = resolve(doc, ref.get('$ref', ref.get('cref')))
            captions.append(item.get('text') or item.get('orig') or '')
        data = table['data']
        cells = []
        for i, cell in enumerate(data['table_cells']):
            cells.append(dict(cell, cell_id=f'{path.parent}:{table["self_ref"]}:cell-{i}', native_index=i,
                              number_tokens=numbers(cell.get('text', ''))))
        result.append({'id': str(path.parent) + ':' + table['self_ref'], 'ref': table['self_ref'],
                       'document_path': str(path), 'caption': ' '.join(captions),
                       'pages': sorted({p['page_no'] for p in table.get('prov', [])}),
                       'prov': table.get('prov', []), 'rows': data['num_rows'], 'cols': data['num_cols'],
                       'cells': cells, 'all_text': ' '.join(c['text'] for c in cells),
                       'data': data})
    return result


def build_delivery(doc, path, variant, job_id):
    mapperpath = RESEARCH / 'pdf-core-w2-native-coverage-round4-2026-10-20/mapper/map_documents.py'
    spec = importlib.util.spec_from_file_location('frozen_w2_mapper', mapperpath)
    mapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mapper)
    folder = HERE / 'delivery' / variant / job_id / path.parent.name
    folder.mkdir(parents=True, exist_ok=True)
    auditfile = folder / 'delivery-audit.json'
    digest = sha(path.read_bytes())
    if auditfile.exists():
        cached = json.loads(auditfile.read_text())
        if cached.get('version') == 'rendered-v4' and cached['input_sha256'] == digest and cached['mapper_sha256'] == sha(mapperpath.read_bytes()):
            return cached
    mapped = mapper.map_document(doc)
    mhtml, mmd = mapper.render(mapped)
    (folder / 'mapped.json').write_text(json.dumps(mapped, ensure_ascii=False, indent=2) + '\n')
    (folder / 'document.html').write_text(mhtml)
    (folder / 'document.md').write_text(mmd)
    mapped_tables = {}
    def walk(node):
        if isinstance(node, dict):
            if node.get('kind') == 'table':
                mapped_tables[node['self_ref']] = node
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for child in node:
                walk(child)
    # Walk rendered tree only, not metadata/events/units duplicates.
    for key in ['body', 'furniture', 'unlinked']:
        walk(mapped.get(key))
    from docling_core.types.doc import DoclingDocument
    core = DoclingDocument.model_validate(doc)
    rawpath = path.parent / 'document.md'
    raw = rawpath.read_text()
    compact = lambda s: re.sub(r'\s+', ' ', s).strip()
    tables = {}
    for i, table in enumerate(core.tables):
        ref = table.self_ref
        exported = table.export_to_markdown(doc=core)
        exported_path = folder / f'table-{i:03d}-RAW.md'
        exported_path.write_text(exported)
        rendered = MarkdownIt('commonmark', {'html': True}).enable('table').render(exported)
        (folder / f'table-{i:03d}-RAW-rendered.html').write_text(rendered)
        fragment = lhtml.fragment_fromstring(rendered, create_parent='div')
        rendered_tables = []
        for actual in fragment.xpath('.//table'):
            rendered_tables.append({'headers': [' '.join(x.itertext()) for x in actual.xpath('./thead/tr/*')],
                                    'rows': [[' '.join(x.itertext()) for x in row] for row in actual.xpath('./tbody/tr')]})
        node = mapped_tables.get(ref)
        native_cells = doc['tables'][i]['data']['table_cells']
        rendered_refs = [c.get('source_ref') for c in node['cells']] if node else []
        mapped_once = bool(node) and len(rendered_refs) == len(set(rendered_refs)) == len(native_cells)
        tables[ref] = {'RAW_export_exact_in_saved_markdown': exported in raw,
                       'RAW_export_whitespace_normalized_in_saved_markdown': compact(exported) in compact(raw),
                       'RAW_export_file': str(exported_path), 'RAW_saved_markdown': str(rawpath),
                       'RAW_actual_renderer': 'markdown_it commonmark + table, installed baseline environment',
                       'RAW_rendered_tables': rendered_tables,
                       'RAW_rendered_html': str(folder / f'table-{i:03d}-RAW-rendered.html'),
                       'MAPPED_table_found': bool(node), 'MAPPED_native_cells_delivered_once_by_ref': mapped_once,
                       'MAPPED_cell_text_equal_native': bool(node) and [c['text'] for c in node['cells']] == [c['text'] for c in native_cells],
                       'MAPPED_layout': node.get('layout') if node else None,
                       'MAPPED_saved_markdown': str(folder / 'document.md'),
                       'MAPPED_saved_html': str(folder / 'document.html'),
                       'RAW_expanded_grid_numeric_exposures': sum(len(numbers(c['text'])) * c['row_span'] * c['col_span'] for c in native_cells if not c['column_header'] and not c['row_header']),
                       'MAPPED_atomic_cell_numeric_exposures': sum(len(numbers(c['text'])) for c in native_cells if not c['column_header'] and not c['row_header']),
                       'span_exposure_is_not_automatically_confirmed_semantic_duplicate': True}
    result = {'version': 'rendered-v4', 'input': str(path), 'input_sha256': digest, 'mapper_path': str(mapperpath),
              'mapper_sha256': sha(mapperpath.read_bytes()), 'zero_inference': True, 'tables': tables,
              'mapped_selfcheck': mapped['selfcheck']}
    auditfile.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def captionkeys(value):
    parts = re.split(r'(?=\b(?:Table|Figure)\s+\d+\s*[:.])', value, flags=re.I)
    result = []
    for part in parts:
        part = re.sub(r'^\s*(?:Table|Figure)\s*[\w.]+\s*[:.]?\s*', '', part, flags=re.I)
        words = part.split()
        result.extend(norm(' '.join(words[:n])) for n in [20, 12, 10, 8] if len(words) >= n and len(norm(' '.join(words[:n]))) >= 35)
    return result


def caption_conflict(source, target):
    pattern = r'\b(Table|Figure)\s+(\d+)\s*[:.]'
    a = {(kind.lower(), number) for kind, number in re.findall(pattern, source, re.I)}
    b = {(kind.lower(), number) for kind, number in re.findall(pattern, target, re.I)}
    return bool(a and b and not a & b)


def match_tables(source, candidates, leaves):
    local = [t for t in candidates if set(t['pages']) & set(source['pages'])]
    strong = []
    skeys = captionkeys(source['caption'])
    for table in local:
        target = norm(table['caption'])
        if target and any(k in target for k in skeys):
            strong.append(table)
    if strong and len(source['leaf_ids']) == 1:
        return strong, 'CAPTION_AND_ABSOLUTE_PAGE'
    if len(source['leaf_ids']) > 1:
        # A common caption may be attached only to one sibling table item.
        # Supplement the union by independent explicit labels for each subgrid.
        for leafid in source['leaf_ids']:
            leaf = leaves[leafid]
            rows = {p['row_label'] for p in leaf['points'] if len(norm(p['row_label'])) >= 6}
            headers = {h for p in leaf['points'] for h in p['column_labels'] if len(norm(h)) >= 2}
            matches = [t for t in local if not caption_conflict(source['caption'], t['caption'])
                       and sum(norm(r) in norm(t['all_text']) for r in rows) >= 2
                       and sum(norm(h) in norm(t['all_text']) for h in headers) >= 1]
            if len(matches) == 1 and matches[0] not in strong:
                strong.append(matches[0])
        if strong:
            return strong, 'CAPTION_AND_UNIQUE_SIBLING_SUBGRID_LABEL_UNION'
    # Caption may be a TEXT node. A source table is located only if several
    # unique source row/column labels identify exactly one native table.
    rows = {p['row_label'] for p in source['points'] if p['row_label_mode'] == 'explicit_first_column_label' and len(norm(p['row_label'])) >= 6}
    headers = {h for p in source['points'] for h in p['column_labels'] if len(norm(h)) >= 2}
    matches = []
    for table in local:
        if caption_conflict(source['caption'], table['caption']):
            continue
        text = norm(table['all_text'])
        mr = [r for r in rows if norm(r) in text]
        mh = [h for h in headers if norm(h) in text]
        if len(mr) >= 2 and len(mh) >= 2:
            matches.append(table)
    if len(matches) == 1:
        return matches, 'UNIQUE_PAGE_ROW_AND_HEADER_LABELS'
    return [], 'UNKNOWN_TABLE_IDENTITY' if local else 'NO_NATIVE_TABLE_ITEM_ON_SOURCE_PAGES'


def native_header_paths(table):
    paths = {c: [] for c in range(table['cols'])}
    for cell in table['cells']:
        if not cell.get('column_header') or not cell.get('text', '').strip():
            continue
        for c in range(cell['start_col_offset_idx'], cell['end_col_offset_idx']):
            if c in paths:
                paths[c].append(cell['text'])
    return {c: ' '.join(v) for c, v in paths.items()}


def source_row_context(leaf, row, first_data_col):
    cells = leaf['cells']
    seen, labels = set(), []
    for c in range(first_data_col):
        index = leaf['grid'][row][c]
        if index is not None and index not in seen:
            seen.add(index)
            value = cells[index]['text']
            if value:
                labels.append(value)
    return labels


def assess_leaf(leaf, points, targets):
    answers = []
    extras = []
    source_by_cell = collections.defaultdict(list)
    for point in points:
        source_by_cell[point['cell_id']].append(point)
    source_columns = {}
    row_first_numeric = {}
    for point in points:
        source_columns.setdefault(point['col'], point['column_labels'])
        row_first_numeric[point['row']] = min(point['col'], row_first_numeric.get(point['row'], point['col']))
    maps = {}
    for table in targets:
        paths = native_header_paths(table)
        packed_columns = set()
        for nc, path in paths.items():
            exact = [sc for sc, labels in source_columns.items() if labels and norm(' '.join(labels)) == norm(path)]
            broad = [sc for sc, labels in source_columns.items() if labels and all(norm(h) and norm(h) in norm(path) for h in labels)]
            if not exact and len(broad) > 1:
                packed_columns.add(nc)
        mapping = {}
        for sc, labels in source_columns.items():
            exact = [nc for nc, path in paths.items() if nc not in packed_columns and labels and norm(' '.join(labels)) == norm(path)]
            matches = exact or [nc for nc, path in paths.items() if nc not in packed_columns and labels and all(norm(h) and norm(h) in norm(path) for h in labels)]
            mapping[sc] = matches[0] if len(matches) == 1 else None
        inverse = collections.Counter(v for v in mapping.values() if v is not None)
        for key, value in list(mapping.items()):
            if value is not None and inverse[value] > 1:
                mapping[key] = None  # no packed-header inversion by source order
        maps[table['id']] = mapping
    rowmaps = {}
    for target in targets:
        mapped_cols = [c for c in maps[target['id']].values() if c is not None]
        label_end = min(mapped_cols, default=0)
        mapping = {}
        for sr, firstcol in row_first_numeric.items():
            labels = source_row_context(leaf, sr, firstcol)
            matches = []
            for nr in range(target['rows']):
                earlier = [c for c in target['cells'] if c['start_row_offset_idx'] <= nr < c['end_row_offset_idx']
                           and c['start_col_offset_idx'] < label_end and not c.get('column_header')]
                combined = ' '.join(c['text'] for c in sorted(earlier, key=lambda c:c['start_col_offset_idx']))
                if labels and all(labelmatch(label, combined) for label in labels):
                    matches.append(nr)
            mapping[sr] = matches[0] if len(matches) == 1 else None
        inverse = collections.Counter(v for v in mapping.values() if v is not None)
        for sr, nr in list(mapping.items()):
            if nr is not None and inverse[nr] > 1:
                mapping[sr] = None  # packed multiple labeled source rows
        rowmaps[target['id']] = mapping
    all_native_numbers = {numberkey(n) for t in targets for c in t['cells'] for n in c['number_tokens']}
    all_native_magnitudes = {v.split('|',1)[0] for v in all_native_numbers}
    for cell_id, group in source_by_cell.items():
        point = group[0]
        row, sc = point['row'], point['col']
        context = source_row_context(leaf, row, row_first_numeric[row])
        blocked_source = sorted({x for p in group for x in p['unknown_reasons']})
        # Full frozen DOM can disambiguate repeated backbone labels with an
        # explicit second label column. Gold itself is never rewritten.
        if len(context) >= 2:
            blocked_source = [x for x in blocked_source if x != 'NONUNIQUE_ROW_COLUMN_LABELS']
        located = []
        for target in targets:
            nc = maps[target['id']].get(sc)
            if nc is None:
                continue
            candidate_rows = []
            if point['row_label_mode'] == 'physical_source_row_configuration':
                headers = [c['end_row_offset_idx'] for c in target['cells'] if c.get('column_header')]
                start = max(headers, default=0)
                source_body_count = len(leaf['grid']) - len(leaf['header_rows'])
                if target['rows'] - start == source_body_count:
                    candidate_rows = [row - len(leaf['header_rows']) + start]
            elif context and rowmaps[target['id']].get(row) is not None:
                candidate_rows = [rowmaps[target['id']][row]]
            if len(candidate_rows) != 1:
                continue
            nr = candidate_rows[0]
            candidate_cells = [c for c in target['cells'] if c['start_row_offset_idx'] <= nr < c['end_row_offset_idx'] and c['start_col_offset_idx'] <= nc < c['end_col_offset_idx'] and not c.get('column_header')]
            if len(candidate_cells) == 1:
                located.append((target, candidate_cells[0], nr, nc))
            elif not candidate_cells:
                located.append((target, None, nr, nc))
        for p in group:
            result = {'point_id': p['id'], 'source_cell_id': cell_id, 'subgrid_id': p['subgrid_id'],
                      'source_row': row, 'source_col': sc, 'row_labels': context or [p['row_label']],
                      'column_labels': p['column_labels'], 'expected_value': p['value'],
                      'component_index': p['component_index'], 'component_role': p['component_role'],
                      'source_unknown_reasons': blocked_source, 'status': 'UNKNOWN', 'unknown_cause': None}
            if blocked_source:
                result['unknown_cause'] = 'SOURCE_POINT_ROLE_OR_VALUE_UNRESOLVED'
            elif len(located) != 1:
                if numberkey(p['value']) not in all_native_numbers and targets:
                    if numberkey(p['value']).split('|',1)[0] in all_native_magnitudes:
                        result['unknown_cause'] = 'UNIT_SUFFIX_OR_SHARED_UNIT_CONTEXT_UNRESOLVED'
                    elif leaf.get('pdf_numeric_crosscheck', {}).get('status') == 'NUMERIC_MULTISET_PRESENT' or leaf.get('manual_pdf_audit'):
                        result.update(status='MISSING', reason='Trusted source numeric value absent from matched native table union; source native-page multiset supports whole source inventory on located page.', error_subtype='VALUE_ABSENT_FROM_MATCHED_TABLE_UNION')
                    else:
                        result['unknown_cause'] = 'SOURCE_PHYSICAL_EXTENT_OR_NATIVE_TEXT_EVIDENCE_UNKNOWN'
                else:
                    result['unknown_cause'] = 'TARGET_ROW_COLUMN_ASSOCIATION_UNRESOLVED_OR_COLLAPSED'
            else:
                target, native, nr, nc = located[0]
                result.update(native_table_id=target['id'], native_row=nr, native_col=nc,
                              native_cell_id=native['cell_id'] if native else None,
                              native_text=native['text'] if native else '')
                values = native['number_tokens'] if native else []
                expected = [x['value'] for x in group]
                if native and (native['row_span'] > 1 or native['col_span'] > 1):
                    result['unknown_cause'] = 'TARGET_DATA_SPAN_ASSOCIATION_UNRESOLVED'
                elif not values:
                    value_in_row_label = any(c.get('row_header') and c['start_row_offset_idx'] <= nr < c['end_row_offset_idx'] and any(numberkey(v) == numberkey(p['value']) for v in c['number_tokens']) for c in target['cells'])
                    if value_in_row_label:
                        result['unknown_cause'] = 'TARGET_PACKED_ROW_LABEL_CONTAINS_DATA_UNASSIGNED_TO_METRIC_COLUMNS'
                    elif leaf.get('pdf_numeric_crosscheck', {}).get('status') != 'NUMERIC_MULTISET_PRESENT' and not leaf.get('manual_pdf_audit'):
                        result['unknown_cause'] = 'SOURCE_PHYSICAL_EXTENT_OR_NATIVE_TEXT_EVIDENCE_UNKNOWN'
                    else:
                        result.update(status='MISSING', reason='Unique explicit native metric row/column tuple is empty; values in another metric column are not this tuple.', error_subtype='MISSING_VALUE_LABEL_TUPLE')
                elif len(expected) == 1:
                    if any(numberkey(p['value']) == numberkey(v) for v in values):
                        result.update(status='CORRECT', reason='Numeric value and unique explicit native row/column tuple found.')
                    elif len(values) == 1:
                        if numberkey(p['value']).split('|',1)[0] == numberkey(values[0]).split('|',1)[0]:
                            result['unknown_cause'] = 'UNIT_SUFFIX_OR_NEIGHBOR_LETTER_CONTEXT_UNRESOLVED'
                        else:
                            result.update(status='WRONG', reason='Unique explicit native tuple contains a different scalar numeric value.')
                    else:
                        result['unknown_cause'] = 'TARGET_MULTIVALUE_COMPONENT_ROLE_UNRESOLVED'
                elif len(values) == len(expected) and (('±' in p['cell_value'] and '±' in native['text']) or (p['component_role'] == 'search_space_option' and '[' in native['text'])):
                    idx = p['component_index']
                    result.update(status='CORRECT' if numberkey(p['value']) == numberkey(values[idx]) else 'WRONG', reason='Explicit same-cell component role/order and row/column labels aligned.')
                else:
                    result['unknown_cause'] = 'TARGET_MULTIVALUE_COMPONENT_ROLE_UNRESOLVED'
            answers.append(result)
            result['numeric_text_present_somewhere_in_matched_tables'] = numberkey(p['value']) in all_native_numbers
            if result['status'] == 'MISSING' and result['numeric_text_present_somewhere_in_matched_tables']:
                result['lexical_omission_claimed'] = False
                result['error_subtype'] = 'VALUE_PRESENT_BUT_REQUIRED_METRIC_LABEL_TUPLE_MISSING'
        # Extra values only when the target cell's row/column association is
        # explicit and the complete source cell tuple is known.
        if not blocked_source and len(located) == 1:
            target, native, nr, nc = located[0]
            if native and native['row_span'] == native['col_span'] == 1:
                expected = collections.Counter(numberkey(p['value']) for p in group)
                actual = collections.Counter(numberkey(v) for v in native['number_tokens'])
                if sum(expected.values()) == 1 and sum(actual.values()) == 1 and not (expected & actual):
                    continue  # one wrong substitution, not wrong+extra
                extra = actual - expected
                for value, count in extra.items():
                    extras.append({'source_cell_id': cell_id, 'native_table_id': target['id'], 'native_cell_id': native['cell_id'],
                                   'source_row': row, 'source_col': sc, 'value_key': value, 'count': count,
                                   'native_col': nc, 'value_exists_elsewhere_in_source_table': any(numberkey(v['value']) == value for v in points),
                                   'reason': 'Additional value+metric-label tuple in an explicit metric cell; not necessarily a new numeric word.'})
    return answers, extras


def assess(source, leaves, candidates):
    result = {'id': source['id'], 'job_id': source['job_id'], 'family': source['family'], 'pages': source['pages'],
              'Q13': source['Q13'], 'scope': source['scope'], 'caption': source['caption'],
              'N': len(source['points']), 'source_status': source['source_status'], 'leaf_ids': source['leaf_ids'],
              'source_issues': source['source_issues'], 'points': [], 'extra_points': []}
    if source['scope'] != 'IN_SCOPE':
        result.update(detection='NOT_EVALUATED', verdict='OUT_OF_SCOPE' if source['scope'] == 'OUT_OF_SCOPE' else 'UNKNOWN', unknown_cause='SOURCE_PAGE_SCOPE_UNKNOWN')
        return result
    targets, method = match_tables(source, candidates, leaves)
    result.update(detection='DETECTED' if targets else method, identity_method=method,
                  native_tables=[{k:t[k] for k in ['id','ref','document_path','caption','pages','rows','cols','prov']} for t in targets])
    for leafid in source['leaf_ids']:
        leaf = leaves[leafid]
        points = [p for p in source['points'] if p['subgrid_id'] == leafid]
        answers, extra = assess_leaf(leaf, points, targets)
        result['points'].extend(answers)
        result['extra_points'].extend(extra)
    counts = collections.Counter(p['status'] for p in result['points'])
    extra = sum(x['count'] for x in result['extra_points'])
    errors = counts['WRONG'] + counts['MISSING'] + extra
    n = result['N']
    result.update(counts=dict(counts), confirmed_extra=extra, confirmed_errors=errors,
                  source_unknown_points=sum(p['unknown_cause'] == 'SOURCE_POINT_ROLE_OR_VALUE_UNRESOLVED' for p in result['points']),
                  target_unknown_points=sum(p['status'] == 'UNKNOWN' and p['unknown_cause'] != 'SOURCE_POINT_ROLE_OR_VALUE_UNRESOLVED' for p in result['points']),
                  native_label_geometry_is_not_gold_zip=True)
    denominator_known = source['source_status'] == 'HTML_PARSED' and n > 0
    result['denominator_status'] = 'FROZEN_HTML_NUMERIC_COMPONENT_INVENTORY' if denominator_known else 'UNKNOWN_SOURCE_INVENTORY'
    # Additional unassociated native data may exist; PASS requires a complete,
    # explicit scalar-cell structure match, not just finding source anchors.
    used_cells = {p.get('native_cell_id') for p in result['points'] if p['status'] != 'UNKNOWN'}
    numeric_cells = {c['cell_id'] for t in targets for c in t['cells'] if c['number_tokens'] and not c.get('column_header') and not c.get('row_header')}
    result['unassociated_native_numeric_cells'] = sorted(numeric_cells - used_cells)
    full_structure = len(targets) == len(source['subgrids']) == 1 and bool(targets) and targets[0]['rows'] == source['subgrids'][0]['rows'] and targets[0]['cols'] == source['subgrids'][0]['cols'] and not result['unassociated_native_numeric_cells']
    result['unassociated_extra_values_ruled_out'] = full_structure and all(p['status'] != 'UNKNOWN' for p in result['points'])
    if denominator_known:
        result['error_rate_lower'] = errors / n
        result['error_rate_upper'] = (errors + counts['UNKNOWN']) / n if result['unassociated_extra_values_ruled_out'] else None
    else:
        result['error_rate_lower'] = result['error_rate_upper'] = None
    if not n:
        result.update(verdict='UNKNOWN', unknown_cause='NO_NUMERICAL_POINTS_NO_0_OVER_0_PASS')
    elif source['Q13'] == 'ordinary' and errors:
        result['verdict'] = 'FAIL'
    elif source['Q13'] == 'complex' and denominator_known and errors / n > .05:
        result['verdict'] = 'FAIL'
    elif denominator_known and result['error_rate_upper'] is not None and result['error_rate_upper'] <= (.05 if source['Q13'] == 'complex' else 0):
        result['verdict'] = 'PASS'
    else:
        result['verdict'] = 'UNKNOWN'
    return result


def load_documents(variant):
    paths = collections.defaultdict(list)
    if variant == 'E0':
        base = RESEARCH / 'pdf-core-w2-native-coverage-round3-2026-10-20/runs/V3_B/jobs'
        for path in sorted(base.glob('*/document.json')):
            paths[path.parent.name].append(path)
    else:
        for path in sorted((ROOT / 'cell-runs').glob('*/jobs/*/document.json')):
            status = path.parent / 'conversion.json'
            if status.exists():
                value = json.loads(status.read_text())
                if not (value.get('success') is True or value.get('status') in ['success', 'SUCCESS', 'completed']):
                    continue
            else:
                continue  # read successful conversions only
            paths[path.parent.parent.parent.name].append(path)
    return paths


def channel_result(row, channel):
    result = {k:copy.deepcopy(v) for k,v in row.items() if k not in ['points','extra_points','channel_results','delivery']}
    result['native_verdict'] = row['verdict']
    points = copy.deepcopy(row['points'])
    extras = copy.deepcopy(row['extra_points'])
    audits = {a['native_table_id']:a for a in row['delivery']}
    def header_verified(tid, nc, expected):
        audit = audits.get(tid, {})
        actual = audit.get('RAW_rendered_tables', [])
        return len(actual) == 1 and nc is not None and nc < len(actual[0]['headers']) and all(norm(h) in norm(actual[0]['headers'][nc]) for h in expected)
    if channel == 'RAW':
        for point in points:
            if point['status'] == 'UNKNOWN' or not point.get('native_table_id'):
                continue
            if not header_verified(point['native_table_id'], point.get('native_col'), point['column_labels']):
                if point['status'] == 'CORRECT' or point.get('numeric_text_present_somewhere_in_matched_tables'):
                    point.update(status='UNKNOWN', unknown_cause='RAW_RENDERED_MARKDOWN_HEADER_ASSOCIATION_UNRESOLVED')
        allowed = []
        for extra in extras:
            related = [p for p in row['points'] if p['source_cell_id'] == extra['source_cell_id']]
            if related and header_verified(extra['native_table_id'], extra.get('native_col'), related[0]['column_labels']):
                allowed.append(extra)
        extras = allowed
    ok = all(a['RAW_export_whitespace_normalized_in_saved_markdown'] if channel == 'RAW' else a['MAPPED_native_cells_delivered_once_by_ref'] and a['MAPPED_cell_text_equal_native'] for a in row['delivery'])
    result['rendered_delivery_verified'] = bool(row['delivery']) and ok
    counts = collections.Counter(p['status'] for p in points)
    extra_count = sum(e['count'] for e in extras)
    errors = counts['MISSING'] + counts['WRONG'] + extra_count
    result.update(points=points, extra_points=extras, counts=dict(counts), confirmed_extra=extra_count, confirmed_errors=errors,
                  source_unknown_points=sum(p['unknown_cause'] == 'SOURCE_POINT_ROLE_OR_VALUE_UNRESOLVED' for p in points),
                  target_unknown_points=sum(p['status'] == 'UNKNOWN' and p['unknown_cause'] != 'SOURCE_POINT_ROLE_OR_VALUE_UNRESOLVED' for p in points),
                  unknown_causes=dict(collections.Counter(p['unknown_cause'] for p in points if p['status'] == 'UNKNOWN')),
                  lexical_value_absent_from_matched_table_points=sum(p['status'] == 'MISSING' and not p.get('numeric_text_present_somewhere_in_matched_tables',False) for p in points),
                  tuple_missing_value_text_still_present=sum(p['status'] == 'MISSING' and p.get('numeric_text_present_somewhere_in_matched_tables',False) for p in points),
                  runtime_or_whole_document_lexical_omission_claimed=False)
    known = result.get('denominator_status') == 'FROZEN_HTML_NUMERIC_COMPONENT_INVENTORY'
    n = result['N']
    complete = result.get('unassociated_extra_values_ruled_out',False) and not counts['UNKNOWN']
    result['error_rate_lower'] = errors/n if known and n else None
    result['error_rate_upper'] = (errors + counts['UNKNOWN'])/n if known and n and complete else None
    result['error_rate_upper_unbounded_due_unassociated_extras'] = known and n > 0 and not complete
    if row['scope'] != 'IN_SCOPE':
        return result
    if not n:
        result['verdict'] = 'UNKNOWN'
    elif row['Q13'] == 'ordinary' and errors:
        result['verdict'] = 'FAIL'
    elif row['Q13'] == 'complex' and known and errors/n > .05:
        result['verdict'] = 'FAIL'
    elif known and complete and errors/n <= (.05 if row['Q13']=='complex' else 0):
        result['verdict'] = 'PASS'
    else:
        result['verdict'] = 'UNKNOWN'
    if result['verdict'] in ['PASS','FAIL'] and not result['rendered_delivery_verified']:
        result['verdict'] = 'UNKNOWN'
        result['unknown_cause'] = 'SAVED_RENDERED_DELIVERY_UNVERIFIED'
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', default='E0')
    ap.add_argument('--output-name', default=None)
    args = ap.parse_args()
    freeze = json.loads((HERE / 'freeze.json').read_text())
    for path, expected in freeze['files'].items():
        assert sha((HERE / path).read_bytes()) == expected, path
    oracle = json.loads((HERE / 'oracle.json').read_text())
    leaves = {t['id']: t for t in oracle['tables']}
    paths = load_documents(args.variant)
    native = collections.defaultdict(list)
    delivery = {}
    documents = []
    for jid, items in paths.items():
        for path in items:
            doc = json.loads(path.read_text())
            native[jid].extend(native_tables(doc, path))
            delivery[str(path)] = build_delivery(doc, path, args.variant, jid)
            documents.append({'job_id': jid, 'document': str(path), 'sha256': sha(path.read_bytes())})
    rows = [assess(t, leaves, native[t['job_id']]) for t in oracle['semantic_tables']]
    for row in rows:
        row['delivery'] = []
        for table in row.get('native_tables', []):
            info = delivery[table['document_path']]['tables'][table['ref']]
            row['delivery'].append(dict(info, native_table_id=table['id']))
        row['channel_results'] = {}
        for channel in ['RAW', 'MAPPED']:
            row['channel_results'][channel] = channel_result(row, channel)
    obj = {'version': 'w3b-table-assessment-v4-qa-corrected', 'variant': args.variant, 'source_oracle_sha256': sha((HERE / 'oracle.json').read_bytes()),
           'documents': documents, 'semantic_tables': rows,
           'channels': ['RAW', 'MAPPED'], 'channel_status': 'SAVED_RENDERED_DELIVERY_VERIFIED_PER_TABLE_OR_UNKNOWN',
           'summary': {'papers_loaded': len(paths), 'documents_loaded': len(documents),
                       'verdicts': dict(collections.Counter(r['verdict'] for r in rows)),
                       'in_scope_verdicts': dict(collections.Counter(r['verdict'] for r in rows if r['scope'] == 'IN_SCOPE')),
                       'channels': {channel: dict(collections.Counter(r['channel_results'][channel]['verdict'] for r in rows if r['scope'] == 'IN_SCOPE')) for channel in ['RAW','MAPPED']}}}
    out = HERE / 'results'
    out.mkdir(exist_ok=True)
    name = args.output_name or args.variant
    (out / f'{name}.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(obj['summary']))


if __name__ == '__main__':
    main()
