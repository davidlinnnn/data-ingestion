"""Source-backed typed content; no text rewriting or formula interpretation.

Executed in a bounded fresh child. The original document remains the authority
for typed content; this manifest adds traversal, region evidence and reviewed
observations without making traversal order into a reading-order guarantee.
"""
import hashlib
import json
import math
from pathlib import Path
import sys


def graph_items(document):
    nodes = {}
    for key in ('body', 'furniture'):
        if document.get(key):
            node = document[key]
            nodes[node['self_ref']] = node
    for key in ('groups', 'texts', 'pictures', 'tables', 'key_value_items', 'form_items'):
        for node in document.get(key, []):
            if node['self_ref'] in nodes:
                raise ValueError('duplicate_typed_reference')
            nodes[node['self_ref']] = node
    ordered, visited, active = [], set(), set()
    def visit(ref):
        if ref in active:
            raise ValueError('cyclic_typed_children')
        if ref in visited:
            return
        if ref not in nodes:
            raise ValueError('missing_typed_reference')
        active.add(ref)
        node = nodes[ref]
        for key in ('parent',):
            if node.get(key) and node[key]['$ref'] not in nodes:
                raise ValueError('missing_typed_reference')
        for caption in node.get('captions', []):
            if caption['$ref'] not in nodes:
                raise ValueError('missing_caption_reference')
        ordered.append(node)
        for child in node.get('children', []):
            visit(child['$ref'])
        active.remove(ref)
        visited.add(ref)
    for root in ('body', 'furniture'):
        if document.get(root):
            visit(document[root]['self_ref'])
    # Preserve unlinked typed content as well; do not silently hide it from callers.
    for ref in nodes:
        visit(ref)
    return ordered


def top_left(box, width, height):
    if box['coord_origin'] == 'BOTTOMLEFT':
        result = [box['l'], height-box['t'], box['r'], height-box['b']]
    elif box['coord_origin'] == 'TOPLEFT':
        result = [box['l'], box['t'], box['r'], box['b']]
    else:
        raise ValueError('unknown_coordinate_origin')
    if not all(math.isfinite(x) for x in result):
        raise ValueError('invalid_region')
    if not (0 <= result[0] < result[2] <= width and 0 <= result[1] < result[3] <= height):
        raise ValueError('region_outside_page')
    return result


def overlap(a, b):
    area = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    return area / ((a[2]-a[0])*(a[3]-a[1]))


def execute(request):
    import pypdfium2 as pdfium
    from .execution import ChildFailure
    from .processing import encoded
    out = Path(request['out'])
    out.mkdir(parents=True, exist_ok=True)
    try:
        parsed_path = Path(request['parsed'])
        document = json.loads(parsed_path.read_text())
        items = graph_items(document)
        if request['policy'] != 'typed-source-evidence-v1':
            raise ValueError('unsupported_evidence_policy')
        review = request['review']
        if review and review['source_sha256'] != request['source']['artifact']['sha256']:
            raise ValueError('review_source_mismatch')
        pages, records = {}, []
        with pdfium.PdfDocument(request['pdf']) as pdf:
            for number in sorted(int(n) for n in document['pages']):
                page = pdf[number-1]
                try:
                    width, height = page.get_size()
                    if page.get_rotation() != 0:
                        raise ValueError('unsupported_evidence_rotation')
                    size = document['pages'][str(number)]['size']
                    if abs(width-size['width']) > .01 or abs(height-size['height']) > .01:
                        raise ValueError('evidence_page_size_mismatch')
                    scale = 3
                    if math.ceil(width*scale)*math.ceil(height*scale) > request['max_render_pixels']:
                        raise ValueError('evidence_pixel_limit')
                    bitmap = page.render(scale=scale)
                    image = bitmap.to_pil().copy()
                    bitmap.close()
                    if request.get('original_pdf'):
                        original_number = review['original_pages'][str(number)]
                        with pdfium.PdfDocument(request['original_pdf']) as original_pdf:
                            if type(original_number) is not int or not 1 <= original_number <= len(original_pdf):
                                raise ValueError('invalid_original_page_number')
                            original_page = original_pdf[original_number-1]
                            try:
                                ow, oh = original_page.get_size()
                                if (not all(math.isfinite(v) and v > 0 for v in (ow, oh)) or
                                        math.ceil(ow*scale)*math.ceil(oh*scale) > request['max_render_pixels']):
                                    raise ValueError('original_evidence_pixel_limit')
                                if original_page.get_rotation() != 0 or abs(ow-width) > .01 or abs(oh-height) > .01:
                                    raise ValueError('original_page_geometry_mismatch')
                                original_bitmap = original_page.render(scale=scale)
                                try:
                                    original_image = original_bitmap.to_pil()
                                    if original_image.size != image.size or original_image.tobytes() != image.tobytes():
                                        raise ValueError('original_page_mapping_mismatch')
                                finally:
                                    original_bitmap.close()
                            finally:
                                original_page.close()
                    filename = f'page-{number}.png'
                    image.save(out/filename)
                    pages[str(number)] = {'artifact': filename, 'sha256': hashlib.sha256((out/filename).read_bytes()).hexdigest(),
                        'physical_page': number, 'original_physical_page': review.get('original_pages', {}).get(str(number), number),
                        'size_points': [width, height], 'pixel_dimensions': list(image.size), 'rotation': 0,
                        'pdf_effective_box': list(page.get_bbox()), 'cropbox': list(page.get_cropbox() or page.get_bbox()),
                        'renderer': {'engine': 'pypdfium2', 'version': request['renderer_version'],
                                     'scale': scale, 'coordinate_space': 'page-local TOPLEFT PDF points'}}
                    image.close()
                finally:
                    page.close()
        for node in items:
            record = {'ref': node['self_ref'], 'actual_type': node.get('label', 'group'),
                'collection': node['self_ref'].split('/')[1], 'text': node.get('text'), 'parent': node.get('parent'), 'children': node.get('children', []),
                'captions': node.get('captions', []), 'regions': [],
                'representation': 'not_independently_validated', 'text_empty': node.get('text') == ''}
            for prov in node.get('prov', []):
                page = pages[str(prov['page_no'])]
                box = top_left(prov['bbox'], *page['size_points'])
                record['regions'].append({'page': prov['page_no'], 'provenance': prov,
                    'bbox_top_left_points': box, 'page_artifact': page['artifact'],
                    'page_sha256': page['sha256'], 'crop_recipe': {'scale': 3, 'box_pixels': [x*3 for x in box]}})
            records.append(record)
        if any(r['actual_type'] == 'formula' and not r['regions'] for r in records):
            raise ValueError('formula_evidence_missing')
        review_ids = [a['id'] for a in review.get('regions', [])]
        if len(review_ids) != len(set(review_ids)):
            raise ValueError('duplicate_review_id')
        formulas = [{'refs': [r['ref']], 'classification': 'parser_formula_label', 'regions': r['regions'],
                     'interpretation': 'not_performed'} for r in records if r['actual_type'] == 'formula']
        observations = []
        for annotation in review.get('regions', []):
            page = pages[str(annotation['page'])]
            box = top_left(annotation['bbox'], *page['size_points'])
            refs = [r['ref'] for r in records if any(g['page'] == annotation['page'] and
                    (overlap(box, g['bbox_top_left_points']) >= .5 or
                     (annotation['kind'] == 'representation' and overlap(g['bbox_top_left_points'], box) >= .5))
                    for g in r['regions'])]
            if not refs:
                raise ValueError('review_region_has_no_typed_content')
            evidence = {'page': annotation['page'], 'bbox_top_left_points': box,
                        'page_artifact': page['artifact'], 'page_sha256': page['sha256'],
                        'crop_recipe': {'scale': 3, 'box_pixels': [x*3 for x in box]}}
            if annotation['kind'] == 'formula':
                formulas = [f for f in formulas if f['classification'] != 'parser_formula_label' or not (set(f['refs']) & set(refs))]
                formulas.append({'review_id': annotation['id'], 'refs': refs, 'classification': 'source_reviewed_occurrence',
                    'regions': [evidence], 'interpretation': 'not_performed', 'actual_types_preserved': True})
            elif annotation['kind'] == 'representation':
                observations.append({'review_id': annotation['id'], 'refs': refs, 'regions': [evidence],
                    'status': 'textual_or_mathematical_representation_unconfirmed', 'reason': annotation['reason'],
                    'text_rewritten': False})
            else:
                raise ValueError('unsupported_review_kind')
        expected_formula_ids = {a['id'] for a in review.get('regions', []) if a['kind'] == 'formula'}
        if {f['review_id'] for f in formulas if 'review_id' in f} != expected_formula_ids:
            raise ValueError('incomplete_reviewed_formula_coverage')
        manifest = {'version': 1, 'source': request['source'], 'parsed_result': request['parsed_result'],
            'assembly': request['assembly'], 'document_sha256': hashlib.sha256(parsed_path.read_bytes()).hexdigest(),
            'policy': request['policy'], 'source_review': review,
            'retained_source': {'artifact': 'source.pdf', 'sha256': request['source']['artifact']['sha256']},
            'retained_original': {'artifact': 'original-source.pdf', 'source': review['original_source']} if request.get('original_pdf') else None,
            'pages': pages, 'items': records,
            'formula_occurrences': formulas, 'formula_coverage': 'source_reviewed_regions' if review else 'unreviewed',
            'representation_observations': observations, 'reading_order': 'source-backed; traversal_is_not_reading_order',
            'note_associations': 'parser_links_only; other_associations_unconfirmed', 'canonical_accepted': False}
        (out/'content-evidence.json').write_bytes(encoded(manifest))
    except (ValueError, KeyError, TypeError, IndexError) as error:
        (out/'failure.json').write_text(json.dumps({'category': 'integrity', 'code': str(error)}))
        raise ChildFailure('integrity', str(error)) from error

if __name__ == '__main__':
    execute(json.load(sys.stdin))
