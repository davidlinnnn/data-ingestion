"""PDFium native characters inside saved picture bounds; no render or inference."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import unicodedata

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / 'pdf-core-w2-native-coverage-round2-2026-10-20'


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s).casefold() if c.isalnum())


def chars(page):
    tp = page.get_textpage()
    output = []
    skip = False
    for i in range(tp.count_chars()):
        text = '' if skip else tp.get_text_range(i, 1, errors='surrogatepass')
        skip = False
        if len(text) == 1 and 0xD800 <= ord(text) <= 0xDBFF:
            text = tp.get_text_range(i, 2)
            skip = True
        output.append({'index': i, 'text': text, 'bbox': list(tp.get_charbox(i))})
    assert norm(''.join(c['text'] for c in output)) == norm(tp.get_text_range())
    tp.close()
    return output


def intersection_fraction(charbox, picbox):
    l, b, r, t = charbox
    pl, pb, pr, pt = picbox
    area = (r - l) * (t - b)
    if area <= 0:
        return 0
    return max(0, min(r, pr) - max(l, pl)) * max(0, min(t, pt) - max(b, pb)) / area


def box(prov, height):
    b = prov['bbox']
    if b['coord_origin'] == 'TOPLEFT':
        return [b['l'], height - b['b'], b['r'], height - b['t']]
    return [b['l'], b['b'], b['r'], b['t']]


def descendants(pic, nodes):
    result = []
    seen = set()

    def visit(ref):
        if ref in seen:
            return
        seen.add(ref)
        node = nodes[ref]
        if node.get('text') and node.get('label') not in ('caption', 'footnote'):
            result.append(node)
        for child in node.get('children', []):
            visit(child['cref'])

    for child in pic.get('children', []):
        visit(child['cref'])
    return result


def inventory(job, folder, family):
    raw = json.loads((folder / 'result.json').read_text())
    document = raw['document']
    md = (folder / 'document.md').read_bytes().decode()
    md_norm = norm(md)
    nodes = {n['self_ref']: n for k in ('texts', 'groups', 'pictures', 'tables') for n in document[k]}
    pics = document['pictures']
    by_page = collections.defaultdict(list)
    for pic in pics:
        for prov in pic.get('prov', []):
            by_page[prov['page_no']].append((pic, prov))
    locations = collections.defaultdict(list)
    pdf = pdfium.PdfDocument(job['pdf'])
    try:
        for page_no, pairs in by_page.items():
            page = pdf[page_no - 1]
            page_chars = chars(page)
            _, height = page.get_size()
            for pic, prov in pairs:
                bounds = box(prov, height)
                matched = [c for c in page_chars if c['text'].strip() and intersection_fraction(c['bbox'], bounds) >= .5]
                strict = [c for c in page_chars if c['text'].strip() and intersection_fraction(c['bbox'], bounds) >= 1 - 1e-6]
                text = ''.join(c['text'] for c in matched)
                locations[pic['self_ref']].append({'page': page_no, 'bbox': bounds,
                    'native_nonspace_characters': sum(len(c['text']) for c in matched),
                    'strict_containment_nonspace_characters': sum(len(c['text']) for c in strict),
                    'native_stream_text_without_whitespace': text,
                    'raw_char_indices': [c['index'] for c in matched]})
            page.close()
    finally:
        pdf.close()
    rows = []
    for pic in pics:
        children = descendants(pic, nodes)
        child_rows = []
        for node in children:
            n = norm(node['text'])
            child_rows.append({'ref': node['self_ref'], 'label': node['label'],
                'native_nonspace_characters': sum(not c.isspace() for c in node['text']),
                'orig_nonspace_characters': sum(not c.isspace() for c in (node.get('orig') or node['text'])),
                'marker': node.get('marker'), 'orig': node.get('orig'),
                'normalized_characters': len(n),
                'exact_normalized_text_found_in_md': bool(n) and n in md_norm,
                'text': node['text']})
        locs = locations[pic['self_ref']]
        source_count = sum(l['native_nonspace_characters'] for l in locs) if locs else None
        child_count = sum(n['native_nonspace_characters'] for n in child_rows)
        substantial = [n for n in child_rows if n['native_nonspace_characters'] >= 30]
        rows.append({'picture_ref': pic['self_ref'], 'locations': locs,
            'source_native_nonspace_characters': source_count,
            'source_native_ge30': source_count >= 30 if source_count is not None else None,
            'native_child_text_nodes': len(child_rows), 'native_child_nonspace_characters': child_count,
            'native_child_orig_nonspace_characters': sum(n['orig_nonspace_characters'] for n in child_rows),
            'native_child_ge30': child_count >= 30,
            'substantial_child_nodes': len(substantial),
            'substantial_child_nodes_found_in_md': sum(n['exact_normalized_text_found_in_md'] for n in substantial),
            'children': child_rows,
            'routing_candidate': ('UNKNOWN_NO_PICTURE_PROVENANCE' if source_count is None else
                 'NO_GE30_NATIVE_TEXT' if source_count < 30 else
                 'NATIVE_CHILDREN_PRESENT_DELIVERY_MAPPING_81' if child_count >= 30 else
                 'NATIVE_CHILDREN_SPARSE_EXTRACTION_REVIEW_REQUIRED')})
    return {'job_id': job['id'], 'family': family, 'selected_pages': job['last'] - job['first'] + 1,
            'input_result': str(folder / 'result.json'), 'pdf_sha256': job['pdf_sha256'],
            'markdown_sha256': hashlib.sha256((folder / 'document.md').read_bytes()).hexdigest(), 'pictures': rows}


def aggregate(docs):
    out = []
    for family in sorted({d['family'] for d in docs}):
        selected = [d for d in docs if d['family'] == family]
        pictures = [p for d in selected for p in d['pictures']]
        qualifying = [p for p in pictures if p['source_native_ge30']]
        out.append({'family': family, 'documents': len(selected),
            'selected_pages': sum(d['selected_pages'] for d in selected),
            'pictures': len(pictures), 'pictures_ge30_native': len(qualifying),
            'documents_with_ge30_native_picture': sum(any(p['source_native_ge30'] for p in d['pictures']) for d in selected),
            'pages_with_ge30_native_picture': len({(d['job_id'], l['page']) for d in selected for p in d['pictures'] if p['source_native_ge30'] for l in p['locations']}),
            'ge30_pictures_with_ge30_native_children': sum(p['native_child_ge30'] for p in qualifying),
            'ge30_pictures_with_substantial_child_md_export': sum(p['substantial_child_nodes_found_in_md'] > 0 for p in qualifying),
            'ge30_pictures_without_ge30_native_children': sum(not p['native_child_ge30'] for p in qualifying)})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--extra-root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), args.output
    jobs = json.loads((OLD / 'jobs.json').read_text())['jobs']
    families = {d['id']: d['family'] for d in json.loads((OLD / 'analysis/summary.json').read_text())}
    docs, unavailable = [], []
    for job in jobs:
        oldfolder = OLD / 'jobs' / job['id']
        folder = args.extra_root / 'jobs' / job['id'] if args.extra_root and (args.extra_root / 'jobs' / job['id'] / 'result.json').exists() else oldfolder
        if not (folder / 'result.json').exists():
            unavailable.append({'job_id': job['id'], 'status': 'MISSING_RESULT_NOT_ZERO', 'selected_pages': job['last']})
            continue
        docs.append(inventory(job, folder, families[job['id']]))
        print(json.dumps({'job': job['id'], 'pictures': len(docs[-1]['pictures'])}), flush=True)
    result = {'method': {'source': 'Original PDFium text layer only; no rendering/OCR/inference',
        'primary': 'Non-whitespace Unicode character ink bbox intersection/pixel bbox area >=0.5, count>=30 per picture across provenance regions.',
        'secondary': 'Full character bbox containment fraction>=1-1e-6 also saved.',
        'coordinates': 'BOTTOMLEFT PDF points',
        'children': 'Descendant text nodes except caption/footnote; counted once per picture; count>=30 is presence, not proven semantic completeness.',
        'markdown': 'Exact full normalized child text substring in saved default Markdown, NFKD/casefold/alnum; nodes>=30 nonspace chars evaluated as substantial.',
        'limits': 'Bounding-box overlap can include prose over/behind picture bounds; geometric candidates require semantic review. Native text counted per picture, not unique globally. Pictures with no provenance remain UNKNOWN. New failed conversions are missing, not zero.'},
        'documents': docs, 'unavailable': unavailable, 'by_family': aggregate(docs)}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'documents': len(docs), 'unavailable': len(unavailable), 'by_family': result['by_family']}))


if __name__ == '__main__':
    main()
