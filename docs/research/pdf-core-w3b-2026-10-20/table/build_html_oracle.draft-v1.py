"""Source-only HTML table oracle. No conversion-output inputs are permitted."""
import argparse
import collections
import datetime
import hashlib
import json
import pathlib
import re
import unicodedata
from lxml import html, etree

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
RESEARCH = ROOT.parent
SOURCE_GOLD = RESEARCH / 'pdf-core-w3-structured-elements-2026-10-20/table/oracle.json'
SEED = 'W3b-html-table-audit-20261020'
NUMBER = re.compile(r'(?<![A-Za-z0-9_])[-+−–]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][−+-]?\d+)?(?:\s*[%‰])?(?![A-Za-z0-9_])')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cls(node, value):
    return value in (node.get('class') or '').split()


def tag(node):
    return etree.QName(node).localname.lower() if isinstance(node.tag, str) else ''


def text(node):
    """One presentation stream: suppress annotations, scripts and hidden twins."""
    name = tag(node)
    if name in {'annotation', 'annotation-xml', 'script', 'style'}:
        return ''
    if node.get('aria-hidden') == 'true' or 'display:none' in (node.get('style') or '').replace(' ', ''):
        return ''
    # MathML presentation is used once; TeX alttext remains separately recorded.
    parts = [node.text or '']
    for child in node:
        parts.extend([text(child), child.tail or ''])
    return re.sub(r'\s+', ' ', ''.join(parts)).strip()


def norm(value):
    return ''.join(c.lower() for c in unicodedata.normalize('NFKC', value) if c.isalnum())


def numeric(value):
    return [m.group(0).replace('−', '-').replace('–', '-').replace(' ', '') for m in NUMBER.finditer(value)]


def nearest_table(node):
    return next((x for x in node.iterancestors() if tag(x) == 'table'), None)


def figure_for(node):
    return next((x for x in node.iterancestors() if tag(x) == 'figure' and cls(x, 'ltx_table')), None)


def parse_grid(table):
    rows = [x for x in table.iterdescendants() if tag(x) == 'tr' and nearest_table(x) is table]
    occupancy, cells, problems = {}, [], []
    for ri, row in enumerate(rows):
        ci = 0
        for element in row:
            if tag(element) not in {'td', 'th'}:
                continue
            while (ri, ci) in occupancy:
                ci += 1
            try:
                rs, cs = int(element.get('rowspan', 1)), int(element.get('colspan', 1))
                if not (1 <= rs <= 1000 and 1 <= cs <= 1000):
                    raise ValueError('out-of-range span')
            except ValueError:
                problems.append('INVALID_SPAN')
                rs = cs = 1
            cell = {'id': element.get('id') or f'cell-r{ri}-c{ci}', 'row': ri, 'col': ci,
                    'rowspan': rs, 'colspan': cs, 'tag': tag(element), 'scope': element.get('scope'),
                    'class': element.get('class', ''), 'text': text(element),
                    'math_alttext': [x.get('alttext') for x in element.iterdescendants() if tag(x) == 'math' and x.get('alttext')],
                    'dom_line': element.sourceline}
            cell['numeric_tokens'] = numeric(cell['text'])
            cells.append(cell)
            for rr in range(ri, ri + rs):
                for cc in range(ci, ci + cs):
                    if (rr, cc) in occupancy:
                        problems.append('OVERLAPPING_SPANS')
                    occupancy[(rr, cc)] = len(cells) - 1
            ci += cs
    nr = len(rows)
    nc = max((c + 1 for r, c in occupancy), default=0)
    if any(r >= nr for r, c in occupancy):
        problems.append('ROWSPAN_BEYOND_ROWS')
    holes = [(r, c) for r in range(nr) for c in range(nc) if (r, c) not in occupancy]
    if holes:
        problems.append('RAGGED_GRID')
    return cells, [[occupancy.get((r, c)) for c in range(nc)] for r in range(nr)], sorted(set(problems))


def label_points(cells, grid):
    """Keep label inference explicit; no output-guided repairs or values guessed."""
    if not grid or not grid[0]:
        return [], [], ['EMPTY_GRID']
    nr, nc = len(grid), len(grid[0])
    # LaTeXML commonly guesses only first-column th, including the top-left cell.
    # Data starts at the first nonempty row label with numerical cells to its right.
    data_start = None
    for ri in range(1, nr):
        unique = list(dict.fromkeys(i for i in grid[ri] if i is not None))
        rowcells = [cells[i] for i in unique]
        label = next((c for c in rowcells if c['col'] == 0), None)
        if label and label['text'] and label['colspan'] < nc and any(c['col'] > 0 and c['numeric_tokens'] for c in rowcells):
            data_start = ri
            break
    if data_start is None:
        return [], [], ['NO_UNAMBIGUOUS_DATA_START']
    header_rows = list(range(data_start))
    points, problems = [], []
    section_label = ''
    for ri in range(data_start, nr):
        idx = list(dict.fromkeys(i for i in grid[ri] if i is not None))
        rowcells = [cells[i] for i in idx]
        if len(rowcells) == 1 and rowcells[0]['colspan'] == nc:
            section_label = rowcells[0]['text']
            continue
        left = cells[grid[ri][0]] if grid[ri][0] is not None else None
        row_label = left['text'] if left else ''
        for cell in rowcells:
            if cell['row'] != ri or cell['col'] == 0 or not cell['numeric_tokens']:
                continue
            labels = []
            for hr in header_rows:
                for cc in range(cell['col'], cell['col'] + cell['colspan']):
                    hidx = grid[hr][cc]
                    if hidx is not None:
                        value = cells[hidx]['text']
                        if value and value not in labels:
                            labels.append(value)
            reasons = []
            if not row_label:
                reasons.append('EMPTY_ROW_LABEL')
            if not labels:
                reasons.append('EMPTY_COLUMN_LABEL')
            if cell['rowspan'] > 1 or cell['colspan'] > 1:
                reasons.append('DATA_CELL_SPANS_LABEL_DOMAINS')
            if cell['math_alttext']:
                reasons.append('MATH_VALUE_NEEDS_PDF_VALIDATION')
            point = {'id': f'point-{len(points):04d}', 'cell_id': cell['id'], 'row': ri, 'col': cell['col'],
                     'row_label': row_label, 'row_group_label': section_label, 'column_labels': labels,
                     'value': cell['text'], 'numeric_components': cell['numeric_tokens'],
                     'multiple_numeric_components': len(cell['numeric_tokens']) > 1,
                     'status': 'TRUSTED_HTML_STRUCTURAL_CANDIDATE' if not reasons else 'UNKNOWN', 'unknown_reasons': reasons}
            points.append(point)
    keys = [(norm(p['row_group_label'] + '|' + p['row_label']), tuple(map(norm, p['column_labels']))) for p in points]
    duplicates = {k for k, count in collections.Counter(keys).items() if count > 1}
    for point, key in zip(points, keys):
        if key in duplicates:
            point['status'] = 'UNKNOWN'
            point['unknown_reasons'].append('NONUNIQUE_ROW_COLUMN_LABELS')
    if not points:
        problems.append('NO_NUMERIC_DATA_POINTS_NO_0_OVER_0_PASS')
    return header_rows, points, problems


def locate(caption, old):
    key = norm(re.sub(r'^\s*Table\s*[\w.]+\s*[:.]?', '', caption, flags=re.I))
    candidates = []
    for table in old:
        for cap in table.get('captions', []):
            other = norm(cap.get('text', ''))
            if len(key) >= 24 and (key in other or other in key or key[:80] == other[:80]):
                candidates.append(table)
                break
    if len(candidates) == 1:
        table = candidates[0]
        return {'method': 'unique HTML caption versus frozen source LaTeX caption (source only)',
                'old_source_id': table['id'], 'pages': table.get('pages', []),
                'scope': table.get('scope', 'UNKNOWN'), 'source_reference': table.get('source')}
    return {'method': 'caption source-only locator', 'pages': [], 'scope': 'UNKNOWN',
            'candidate_source_ids': [t['id'] for t in candidates]}


def run():
    manifest_path = ROOT / 'html-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    old = json.loads(SOURCE_GOLD.read_text())
    grouped = collections.defaultdict(list)
    for t in old['tables']:
        grouped[t['job_id']].append(t)
    tables, excluded, papers = [], [], []
    for job in manifest['jobs']:
        jid = job['job_id']
        if job.get('status') != 'AVAILABLE':
            papers.append({'job_id': jid, 'status': 'UNKNOWN_HTML_UNAVAILABLE', 'html_status': job.get('status')})
            continue
        path = pathlib.Path(job['html_path'])
        data = path.read_bytes()
        assert sha(data) == job['sha256'], jid
        document = html.fromstring(data)
        accepted = 0
        for index, node in enumerate(document.xpath('//table')):
            uid = jid + ':html-table:' + (node.get('id') or f'index-{index:03d}')
            ancestors = list(node.iterancestors())
            why = []
            if any(tag(a) in {'math', 'mtable'} or cls(a, 'ltx_equation') or cls(a, 'ltx_equationgroup') for a in ancestors):
                why.append('MATH_OR_EQUATION_LAYOUT')
            if node.xpath('.//table'):
                why.append('NESTED_TABLE_CONTAINER_LEAF_TABLES_ONLY')
            figure = figure_for(node)
            if figure is None:
                why.append('NO_ARTICLE_TABLE_FLOAT_SEMANTICS')
            if why:
                excluded.append({'id': uid, 'job_id': jid, 'reason': why, 'dom_line': node.sourceline})
                continue
            cells, grid, issues = parse_grid(node)
            headers, points, label_issues = label_points(cells, grid)
            caps = figure.xpath('./figcaption')
            caption = ' '.join(text(c) for c in caps)
            location = locate(caption, grouped[jid])
            q13 = []
            if len(headers) > 1:
                q13.append('MULTILEVEL_HEADER')
            if any(c['rowspan'] > 1 or c['colspan'] > 1 for c in cells):
                q13.append('MERGED_CELL')
            leafcount = len([n for n in figure.xpath('.//table') if not n.xpath('.//table')])
            if leafcount > 1:
                q13.append('MULTIPLE_SUBTABLES')
            if any(p['multiple_numeric_components'] for p in points):
                q13.append('MULTIPLE_VALUES_PER_DATA_CELL')
            if len(location['pages']) > 1:
                q13.append('CROSS_PAGE')
            errors = [text(n) for n in node.iterdescendants() if cls(n, 'ltx_ERROR') or cls(n, 'ltx_error')]
            if errors:
                issues.append('LATEXML_ERROR_MARKER')
            record = {'id': uid, 'job_id': jid, 'family': job['family'], 'html_path': str(path),
                      'html_sha256': sha(data), 'html_url': job.get('final_url'), 'arxiv_version': job['arxiv_version'],
                      'pdf': job['pdf'], 'pdf_sha256': job['pdf_sha256'], 'dom_id': node.get('id'),
                      'figure_id': figure.get('id'), 'dom_line': node.sourceline,
                      'caption': caption, 'caption_sha256': sha(caption.encode()),
                      'rows': len(grid), 'cols': len(grid[0]) if grid else 0, 'cells': cells, 'grid': grid,
                      'header_rows': headers, 'header_inference': 'first labeled row with numeric data; HTML roles retained separately',
                      'latex_guessed_headers': cls(node, 'ltx_guessed_headers'), 'points': points,
                      'expected_numeric_cell_points': len(points), 'numeric_component_occurrences': sum(len(p['numeric_components']) for p in points),
                      'location': location, 'Q13': 'complex' if q13 else 'ordinary', 'Q13_reasons': q13,
                      'source_status': 'HTML_STRUCTURAL_CANDIDATE' if not issues and not label_issues else 'UNKNOWN',
                      'source_issues': issues + label_issues, 'latex_errors': errors,
                      'trust_scope': 'Source HTML only; not a blanket PDF-faithfulness certification. Manual sampled exclusions appended before freeze.'}
            tables.append(record)
            accepted += 1
        papers.append({'job_id': jid, 'status': 'HTML_PARSED', 'html_sha256': sha(data), 'accepted_leaf_tables': accepted})
    result = {'version': 'w3b-html-table-source-v1', 'phase': 'SOURCE_ONLY_NO_E0_E1_READ',
              'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'html_manifest_sha256': sha(manifest_path.read_bytes()), 'html_manifest_complete': manifest.get('complete'),
              'source_locator_oracle_sha256': sha(SOURCE_GOLD.read_bytes()),
              'denominator': 'One numeric-valued source data cell tuple (full cell value + hierarchical row/column labels); all numeric components retained, not treated as independent repeated cell assignments.',
              'papers': papers, 'tables': tables, 'excluded': excluded}
    result['counts'] = {'papers_seen': len(papers), 'html_parsed': sum(p['status'] == 'HTML_PARSED' for p in papers),
                        'table_candidates': len(tables), 'excluded_layout_or_container': len(excluded),
                        'Q13': dict(collections.Counter(t['Q13'] for t in tables)),
                        'locations': dict(collections.Counter(t['location']['scope'] for t in tables)),
                        'numeric_cell_points': sum(len(t['points']) for t in tables)}
    candidates = [t for t in tables if t['location']['scope'] == 'IN_SCOPE' and t['points'] and t['rows'] and t['cols']]
    selected = sorted(candidates, key=lambda t: sha((SEED + '|' + t['id']).encode()))[:10]
    audit_plan = {'seed': SEED, 'population_rule': 'All source-located IN_SCOPE HTML leaf data tables with numeric points; no output information.',
                  'population_count': len(candidates), 'manifest_complete': manifest.get('complete'),
                  'tables': [{'id': t['id'], 'job_id': t['job_id'], 'pages': t['location']['pages'],
                              'hash': sha((SEED + '|' + t['id']).encode()), 'rows': t['rows'], 'cols': t['cols'],
                              'numeric_cell_points': len(t['points'])} for t in selected]}
    (HERE / 'oracle.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    (HERE / 'audit-plan.json').write_text(json.dumps(audit_plan, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result['counts']))
    print(json.dumps(audit_plan, ensure_ascii=False))


if __name__ == '__main__':
    run()
