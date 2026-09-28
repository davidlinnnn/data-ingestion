"""Evidence-seam candidate: local function-block/caption associations.

No oracle, page numbers, source hashes, item IDs, or algorithm names are inputs.
Discovery coverage is intentionally unknown outside the emitted candidates.
"""
import hashlib
import json
import re
from pathlib import Path
from .evidence import top_left
import unicodedata

METHOD = 'local-function-block-v1'
HEADER = re.compile(r'function\s+[\w-]+\s*\(.*?\)\s*returns\s+.*?(?:failure/cutoff|failure)')
CAPTION = re.compile(r'Figure\s+\d+(?:\.\d+)*\b')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def segments(doc):
    result = []
    for item in doc['texts']:
        for prov in item.get('prov', []):
            start, end = prov['charspan']
            valid = type(start) is int and type(end) is int and 0 <= start < end <= len(item['text'])
            b = prov['bbox']
            h = doc['pages'][str(prov['page_no'])]['size']['height']
            box = top_left(b, doc['pages'][str(prov['page_no'])]['size']['width'], h, allow_zero_width=True)
            result.append({'ref': item['self_ref'], 'page': prov['page_no'], 'range': [start, end],
                           'box': box, 'text': item['text'][start:end] if valid else '', 'actual_type': item['label'], 'valid_range': valid})
    return result


def member(segment, role, order):
    return {k: v for k, v in segment.items() if k != 'text'} | {
        'role': role, 'order': order, 'text_sha256': hashlib.sha256(segment['text'].encode()).hexdigest()}


def header_parts(header, parts):
    """Bounded neighboring fragments; raw offsets survive concatenation."""
    joined = header['text']
    selected = [header]
    match = HEADER.match(joined)
    if not match and joined.startswith('function'):
        neighbors = [s for s in parts if s is not header and s['page'] == header['page']
                     and abs(s['box'][1]-header['box'][1]) <= 2
                     and s['box'][0] >= header['box'][0]]
        for part in sorted(neighbors, key=lambda s: s['box'][0])[:8]:
            selected.append(part)
            joined += part['text']
            match = HEADER.match(joined)
            if match:
                break
    if not match:
        return [], []
    remaining = match.end()
    headers, tails = [], []
    for part in selected:
        take = min(remaining, len(part['text']))
        headers.append(dict(part, text=part['text'][:take], range=[part['range'][0], part['range'][0]+take]))
        if take < len(part['text']):
            tails.append(dict(part, text=part['text'][take:], range=[part['range'][0]+take, part['range'][1]]))
        remaining -= take
    return headers, tails


def row_order(parts):
    rows = []
    for part in sorted(parts, key=lambda s: s['box'][1]):
        if not rows or part['box'][1]-rows[-1][0]['box'][1] > 2:
            rows.append([part])
        else:
            rows[-1].append(part)
    return [s for row in rows for s in sorted(row, key=lambda s: s['box'][0])]


def derive(doc, source_sha256):
    all_parts = segments(doc)
    invalid = [member(s, 'invalid_source_range', None) for s in all_parts if not s['valid_range']]
    parts = [s for s in all_parts if s['valid_range']]
    relations = []
    for header in parts:
        headers, tails = header_parts(header, parts)
        if not headers:
            continue
        page = header['page']
        size = doc['pages'][str(page)]['size']
        captions = [s for s in parts if s['page'] == page and CAPTION.match(s['text'])
                    and 0 < s['box'][1]-header['box'][3] < .3*size['height']
                    and abs(s['box'][0]-header['box'][0]) < .08*size['width']]
        captions.sort(key=lambda s: s['box'][1])
        relation = {'disposition': 'unresolved', 'reason': 'missing_or_ambiguous_caption',
                    'members': [member(s, 'header', i) for i, s in enumerate(headers)]}
        if captions and (len(captions) == 1 or captions[0]['box'][1] != captions[1]['box'][1]):
            caption = captions[0]
            body, symbols = list(tails), []
            header_refs = {(s['ref'], s['page'], tuple(s['box'])) for s in headers}
            for s in parts:
                if s['page'] != page or s is caption or (s['ref'], s['page'], tuple(s['box'])) in header_refs:
                    continue
                if (header['box'][1] <= s['box'][1] and s['box'][3] < caption['box'][1]
                        and s['box'][0] >= header['box'][0]-2
                        and s['box'][2] <= max(header['box'][2], caption['box'][2])+.12*size['width']):
                    if s['text'] and all(unicodedata.category(c).startswith('M') for c in s['text']):
                        symbols.append(s)
                    else:
                        body.append(s)
            caption_parts = [caption]
            # A split caption may have several provenance fragments or same-line items.
            for part in row_order(parts):
                if part is caption or part['page'] != page or CAPTION.match(part['text']):
                    continue
                if (part['ref'] == caption['ref'] and part['range'][0] >= caption['range'][1]) or (
                        abs(part['box'][1]-caption['box'][1]) <= 2 and part['box'][0] >= caption['box'][2]-2):
                    caption_parts.append(part)
            relation['members'] += [member(s, 'body', len(headers)+i) for i, s in enumerate(row_order(body))]
            relation['members'] += [member(s, 'caption', len(headers)+len(body)+i) for i, s in enumerate(row_order(caption_parts))]
            relation['symbol_uncertainty'] = [member(s, 'unplaced_combining_mark', None) for s in symbols]
            relation['reason'] = 'local_function_block_and_numbered_caption' if body else 'missing_body'
            relation['disposition'] = 'candidate' if body else 'unresolved'
        relations.append(relation)
    return {'method': METHOD, 'method_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_sha256': source_sha256, 'document_sha256': digest(doc),
            'coverage': 'local_function_headers_only; whole_document_unknown',
            'assertion_origin': 'method_derived_not_source_review', 'relationships': relations,
            'unresolved_input_regions': invalid, 'canonical_accepted': False}
