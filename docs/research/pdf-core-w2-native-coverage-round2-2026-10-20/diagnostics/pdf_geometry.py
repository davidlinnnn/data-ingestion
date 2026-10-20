"""Independent PDF text-layer geometry, with no Docling inputs or rendering."""
import argparse
import bisect
import collections
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s).casefold() if c.isalnum())


def side(box, width):
    if box[2] < width * .54:
        return 'L'
    if box[0] > width * .46:
        return 'R'
    return 'SPAN'


def line_row(chars, start, end, offset, width):
    ink = [c['bbox'] for c in chars[start:end] if c['text'].strip()]
    if not ink:
        return None
    box = [min(b[0] for b in ink), min(b[1] for b in ink),
           max(b[2] for b in ink), max(b[3] for b in ink)]
    return {'text': ''.join(c['text'] for c in chars[start:end]), 'bbox': box,
            'raw_char_range': [start, end], 'pdf_normalized_range':
            [offset + sum(len(c['normalized']) for c in chars[:start]),
             offset + sum(len(c['normalized']) for c in chars[:end])],
            'column_geometry': side(box, width)}


def process(job, oracle=None):
    doc = pdfium.PdfDocument(job['pdf'])
    pages = []
    locators = []
    offset = 0
    try:
        for pn in range(job['first'], job['last'] + 1):
            page = doc[pn - 1]
            tp = page.get_textpage()
            w, h = page.get_size()
            chars = []
            skip_surrogate = False
            for i in range(tp.count_chars()):
                text = '' if skip_surrogate else tp.get_text_range(i, 1, errors='surrogatepass')
                skip_surrogate = False
                if len(text) == 1 and 0xD800 <= ord(text) <= 0xDBFF:
                    # PDFium counts UTF-16 halves; preserve the raw index while decoding the pair.
                    text = tp.get_text_range(i, 2)
                    skip_surrogate = True
                chars.append({'text': text, 'normalized': norm(text),
                              'bbox': list(tp.get_charbox(i))})
            joined = ''.join(c['text'] for c in chars)
            assert norm(joined) == norm(tp.get_text_range()), (job['id'], pn, 'text map differs')
            lines = []
            start = 0
            for i, char in enumerate(chars):
                if char['text'] in ('\n', '\r'):
                    row = line_row(chars, start, i, offset, w)
                    if row:
                        lines.append(row)
                    start = i + 1
            row = line_row(chars, start, len(chars), offset, w)
            if row:
                lines.append(row)
            counts = collections.Counter(row['column_geometry'] for row in lines
                                         if row['bbox'][2] - row['bbox'][0] >= 40
                                         and row['bbox'][1] > h * .08 and row['bbox'][3] < h * .92)
            left, right, span = (counts[k] for k in ('L', 'R', 'SPAN'))
            column = ('DOUBLE' if left >= 8 and right >= 8 and left + right > span * 1.5
                      else 'SINGLE' if span >= 8 and span > left + right else 'UNKNOWN')
            normalized = norm(joined)
            norm_ends = []
            pos = offset
            for char in chars:
                pos += len(char['normalized'])
                norm_ends.append(pos)
            pages.append({'page': pn, 'page_dimensions': {'width': w, 'height': h},
                          'coord_origin': 'BOTTOMLEFT', 'raw_char_count': len(chars),
                          'pdf_normalized_range': [offset, offset + len(normalized)],
                          'column_class': column, 'column_evidence_counts': dict(counts),
                          'lines': lines})
            locators.append((offset, offset + len(normalized), pn, chars, norm_ends, w, column, lines))
            offset += len(normalized)
            tp.close()
            page.close()
    finally:
        doc.close()
    furniture = []
    repeated = collections.defaultdict(list)
    for page in pages:
        h = page['page_dimensions']['height']
        for line in page['lines']:
            l, b, r, t = line['bbox']
            text = line['text'].strip()
            reasons = []
            if re.search(r'arxiv\s*:', text, re.I):
                reasons.append('arxiv_stamp')
            if (t < h * .08 or b > h * .92) and re.fullmatch(r'(?:\d{1,5}|[ivxlcdmIVXLCDM]{1,6})', text):
                reasons.append('isolated_margin_page_number')
            if (t < h * .08 or b > h * .92) and len(text) <= 160 and len(norm(text)) >= 5:
                repeated[(norm(text), round(((b + t) / 2) / h * 200))].append((page['page'], line))
            if reasons:
                furniture.append({'page': page['page'], **line, 'candidate_reasons': reasons})
    for rows in repeated.values():
        if len({pn for pn, _ in rows}) >= 3:
            for pn, line in rows:
                furniture.append({'page': pn, **line, 'candidate_reasons': ['same_margin_y_text_at_least_3_pages']})
    locations = {}
    if oracle:
        whole = ''.join(c['normalized'] for p in locators for c in p[3])
        for anchor in oracle['anchors']:
            if anchor['status'] != 'TRUSTED' or 'pdf_normalized_offset' not in anchor:
                continue
            start = anchor['pdf_normalized_offset']
            end = start + len(anchor['normalized'])
            hits = [p for p in locators if p[0] < end and p[1] > start]
            if not hits:
                continue
            assert whole[start:end] == anchor['normalized'], (job['id'], anchor['id'], 'oracle offset mismatch')
            p = hits[0]
            idx = bisect.bisect_right(p[4], start)
            assert idx < len(p[3]), (job['id'], anchor['id'])
            box = p[3][idx]['bbox']
            line = next((r for r in p[7] if r['raw_char_range'][0] <= idx < r['raw_char_range'][1]), None)
            column = ('MULTI' if len(hits) > 1 else 'S' if p[6] == 'SINGLE' else
                      line['column_geometry'] if p[6] == 'DOUBLE' and line and line['column_geometry'] in ('L', 'R') else 'UNKNOWN')
            locations[anchor['id']] = {'page': p[2], 'pages': [x[2] for x in hits],
                                       'column': column, 'bbox': box,
                                       'raw_char_index': idx, 'pdf_normalized_offset': start,
                                       'source_line_bbox': line['bbox'] if line else None}
    return {'job_id': job['id'], 'pdf': job['pdf'], 'pdf_sha256': job['pdf_sha256'],
            'method': 'pypdfium2 char text and bottom-left boxes; no Docling/output/render/OCR',
            'normalization': 'NFKD then casefold then alnum only', 'pages': pages,
            'furniture_candidates': furniture, 'anchor_locations': locations,
            'oracle_sha256': hashlib.sha256(json.dumps(oracle, sort_keys=True).encode()).hexdigest() if oracle else None,
            'limits': 'Column and margin-furniture are conservative geometry candidates, not semantic judgments. Raw char ranges are PDFium textpage indices, end-exclusive; line wrap is original PDF text stream. No body content is deleted.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--anchors', action='store_true', help='Read only sealed oracle anchors')
    args = parser.parse_args()
    jobs = json.loads((ROOT / 'jobs.json').read_text())['jobs']
    idx = json.loads((ROOT / 'oracle/job-index.json').read_text()) if args.anchors else {}
    folder = ROOT / 'diagnostics/geometry'
    folder.mkdir(exist_ok=True)
    counts = collections.Counter()
    for job in jobs:
        oracle = json.loads(Path(idx[job['id']]).read_text()) if args.anchors else None
        result = process(job, oracle)
        out = folder / (job['id'] + '.json')
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        counts.update(p['column_class'] for p in result['pages'])
        print(json.dumps({'id': job['id'], 'pages': len(result['pages']), 'anchors': len(result['anchor_locations'])}), flush=True)
    assert sum(counts.values()) == 715, counts
    print(json.dumps({'pages': sum(counts.values()), 'column_classes': dict(counts)}), flush=True)


if __name__ == '__main__':
    main()
