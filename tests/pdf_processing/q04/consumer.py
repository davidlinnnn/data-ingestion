"""Independent Q04 consumer checks over checked durable outputs, never production rules."""
from collections import Counter
from io import BytesIO
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def ref(value):
    return value.get('$ref', value.get('cref'))


def references(value):
    if isinstance(value, dict):
        if '$ref' in value or 'cref' in value:
            yield ref(value)
        for child in value.values():
            yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def check_graph(document, report):
    """Account for every collection, source region and graph edge, not only body text."""
    nodes = [document[k] for k in ('body', 'furniture') if document.get(k)]
    for key in ('groups', 'texts', 'pictures', 'tables', 'key_value_items', 'form_items'):
        nodes.extend(document.get(key, []))
    index = {n['self_ref']: n for n in nodes}
    records = {n['ref']: n for n in report['items']}
    require(len(index) == len(nodes), 'duplicate document ref')
    require(len(records) == len(report['items']) and records.keys() == index.keys(), 'incomplete typed graph')
    require(all(r in index for r in references(nodes)), 'dangling graph edge')
    visiting, visited = set(), set()

    def visit(key):
        require(key not in visiting, 'cyclic children')
        if key in visited:
            return
        visiting.add(key)
        children = [ref(x) for x in index[key].get('children', [])]
        require(len(children) == len(set(children)), 'duplicate child')
        for child in children:
            require(ref(index[child].get('parent', {})) == key, 'child parent mismatch')
            visit(child)
        visiting.remove(key)
        visited.add(key)

    for key, node in index.items():
        visit(key)
        item = records[key]
        require(item['actual_type'] == node.get('label', 'group') and item['text'] == node.get('text'), 'typed content changed')
        require(item['collection'] == key.split('/')[1], 'wrong collection')
        require(ref(item.get('parent') or {}) == ref(node.get('parent') or {}), 'parent lost')
        for field in ('children', 'captions'):
            require([ref(x) for x in item.get(field, [])] == [ref(x) for x in node.get(field, [])], field + ' lost')
        require([r['provenance'] for r in item['regions']] == node.get('prov', []), 'provenance changed')
        for region in item['regions']:
            page = report['pages'][str(region['page'])]
            require(region['page'] == region['provenance']['page_no'], 'wrong source page')
            require(region['page_artifact'] == page['artifact'] and region['page_sha256'] == page['sha256'], 'source region binding')
            box = region['provenance']['bbox']
            height = page['size_points'][1]
            expected = [box['l'], box['t'], box['r'], box['b']] if box['coord_origin'] == 'TOPLEFT' else [box['l'], height-box['t'], box['r'], height-box['b']]
            require(region['bbox_top_left_points'] == expected, 'source geometry changed')
    for table in document.get('tables', []):
        data = table['data']
        occupied = set()
        for cell in data['table_cells']:
            r, c = cell['start_row_offset_idx'], cell['start_col_offset_idx']
            end_r, end_c = cell['end_row_offset_idx'], cell['end_col_offset_idx']
            require(0 <= r < end_r <= data['num_rows'] and 0 <= c < end_c <= data['num_cols'], 'table cell bounds')
            require(end_r-r == cell['row_span'] and end_c-c == cell['col_span'], 'table cell span')
            cells = {(row, col) for row in range(r, end_r) for col in range(c, end_c)}
            require(not occupied.intersection(cells), 'overlapping table cells')
            occupied.update(cells)
    return {'items': len(nodes), 'tables': len(document.get('tables', [])),
            'pictures': len(document.get('pictures', [])), 'types': dict(Counter(r['actual_type'] for r in records.values()))}


def source_signature(document):
    """Ref-independent, lossless multiset for discovering collateral changes; no normalization."""
    parts = []
    for collection in ('texts', 'pictures', 'tables', 'groups'):
        for node in document.get(collection, []):
            for prov in node.get('prov', []):
                text = node.get('text')
                if text is not None:
                    text = text[slice(*prov['charspan'])]
                parts.append(canonical([collection, node.get('label'), prov['page_no'], prov['bbox'], text]))
    return Counter(parts)


def graph_projection(document):
    def clean(value) -> Any:
        if isinstance(value, dict):
            return {('$ref' if k == 'cref' else k): clean(v) for k, v in value.items() if v is not None}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    return clean({k: document.get(k, [] if k not in ('body', 'furniture', 'pages') else {})
        for k in ('body', 'furniture', 'groups', 'texts', 'pictures', 'tables', 'key_value_items', 'form_items', 'pages')})


def check_reference(document, reference, out):
    before, after = graph_projection(reference), graph_projection(document)
    if before != after:
        old, new = source_signature(reference), source_signature(document)
        (out/'graph-delta.json').write_text(json.dumps({'status': 'SOURCE_REVIEW_REQUIRED',
            'expected_graph_sha256': sha(canonical(before).encode()), 'actual_graph_sha256': sha(canonical(after).encode()),
            'removed_source_segments': list((old-new).elements()), 'added_source_segments': list((new-old).elements()),
            'changed_collections': [k for k in before if before[k] != after[k]]}, indent=2))
        raise ValueError('unreviewed full graph delta; retain output and source-review before acceptance')
    return sha(canonical(after).encode())


def check_fixture(sid, document, report, relationship_report, policy, oracles):
    checks = check_graph(document, report)
    norm = lambda text: ' '.join(text.split())
    typed = {n['ref']: n for n in report['items']}
    if sid in ('06', '07'):
        expected = json.loads((oracles/(sid+'-table-full-audit.json')).read_text())
        tables = [t for t in document['tables'] if t['data']['num_rows'] == (26 if sid == '06' else 15)]
        require(len(tables) == 1, 'ambiguous source-audited table')
        cells = {(c['start_row_offset_idx'], c['start_col_offset_idx']): c for c in tables[0]['data']['table_cells']}
        require(set(cells) == {(e['row'], e['col']) for e in expected}, 'table audit coverage')
        for entry in expected:
            cell = cells[entry['row'], entry['col']]
            source = entry['parsed_text'] if sid == '07' and '\x02' in entry['source_text'] else entry['source_text']
            require(norm(cell['text']) == norm(source) and cell['row_span'] == entry['rowspan'], 'source-audited cell changed')
        checks['audited_cells'] = len(expected)
    elif sid == '08':
        sys.path.insert(0, str(ROOT/'tests/pdf_processing/q02'))
        from oracle.score import score
        candidate = copy.deepcopy(relationship_report['candidates'])
        candidate['relationships'] = [{**r, 'disposition': 'candidate'} for r in relationship_report['resolved']]
        verdicts = score(document, candidate)
        require(len(verdicts) == 4 and all(v['structure_pass'] for v in verdicts), 'four algorithm oracle')
        # Exact source-reviewed Q01 element segments identify the accepted edges,
        # independently of new Docling item numbering.
        expected = json.loads((oracles/'continuation-oracle.json').read_text())
        memberships = {}
        for name, anchor in expected['anchors'].items():
            box = anchor['bbox']
            matches = []
            for item in document['texts']:
                for prov in item['prov']:
                    b = dict(prov['bbox'])
                    if b['coord_origin'] != box['coord_origin']:
                        height = document['pages'][str(prov['page_no'])]['size']['height']
                        b.update(t=height-b['t'], b=height-b['b'], coord_origin=box['coord_origin'])
                    if (prov['page_no'] == anchor['page']
                            and b['l']-.01 <= box['l'] <= box['r'] <= b['r']+.01
                            and min(b['t'], b['b'])-.01 <= min(box['t'], box['b'])
                            and max(box['t'], box['b']) <= max(b['t'], b['b'])+.01
                            and anchor['text'] in item['text'][slice(*prov['charspan'])]):
                        matches.append(item['self_ref'])
            require(len(set(matches)) == 1, 'Q01 source anchor absent or ambiguous')
            memberships[name] = matches[0]
        for edge in expected['edges']:
            a, b = edge['members']
            require((memberships[a] == memberships[b]) is edge['joined'], 'Q01 source-reviewed continuation edge')
        require(len(relationship_report['resolved']) == 4 and not relationship_report['unresolved'], 'required relationships incomplete')
        require(policy['representation'] == json.loads((ROOT/'tests/pdf_processing/q03/reviewed-representation.json').read_text()), 'representation disposition drift')
        checks.update(algorithms=4, continuation_edges=len(expected['edges']))
    elif sid == '09':
        equations = [x for x in report['formula_occurrences'] if x.get('review_id', '').startswith('eq')]
        require(len(equations) == 6 and {x['review_id'] for x in equations} == {f'eq{i}' for i in range(1, 7)}, 'six ACL equations')
        require(any(typed[r]['actual_type'] == 'text' for e in equations if e['review_id'] == 'eq2' for r in e['refs']), 'eq2 actual type')
        require(bool(report['representation_observations']), 'ACL uncertainty evidence')
        expected = json.loads((oracles/'quality-oracle.json').read_text())
        for page in [p for p in expected['pages'] if p['source_id'] == '09']:
            actual = [n for n in report['items'] if any(r['page'] == page['processed_page'] for r in n['regions'])]
            require(len(actual) == len(page['items']), 'ACL full typed coverage')
            for node, old in zip(actual, page['items']):
                h = lambda text: sha(json.dumps(text, ensure_ascii=False).encode())
                require(node['actual_type'] == old['type'] and h(node['text']) == old['text_sha256'], 'ACL typed text')
                require([h(typed[ref(c)]['text']) for c in node['captions']] == old['caption_text_hashes'], 'ACL real captions')
        checks['equations'] = 6
    elif sid == '10':
        expected = next(x['regions'] for x in json.loads((oracles/'new-source-oracle.json').read_text()) if x['source_id'] == '10')
        require(len(expected) == 27, 'Keynote oracle coverage')
        for region in expected:
            l, t, r, b = region['bbox']
            pieces = []
            for node in report['items']:
                if not node.get('text'):
                    continue
                for geometry in node['regions']:
                    x1, y1, x2, y2 = geometry['bbox_top_left_points']
                    if geometry['page'] == 1 and l <= (x1+x2)/2 <= r and t <= (y1+y2)/2 <= b:
                        pieces.append((y1, x1, node['text']))
                        break
            require(norm(region['expected_text']) == norm(' '.join(x[2] for x in sorted(pieces))), 'Keynote textbox')
        checks['textboxes'] = 27
    else:
        require(sid == 'native', 'unsupported fixture')
    return checks


class Consumer:
    """Read and audit the complete result through the same checked Store as consumers."""
    def __init__(self, store, out):
        self.store, self.out = store, out
        self.inventory = {}

    def artifact(self, identity, name):
        registration = self.store.resolve(identity)
        require(registration is not None, 'required registration missing')
        self.inventory[identity] = registration
        files = [f for f in registration['files'] if f['name'] == name]
        require(len(files) == 1, 'required artifact missing')
        return self.store.read_artifact(files[0])

    def json(self, identity, name):
        return json.loads(self.artifact(identity, name))

    def verify(self, result, request, profile, fixture, oracles):
        from pdf_processing.relationships import validate
        from PIL import Image
        require(result['status'] == 'complete' and result['processing_complete'], 'workflow incomplete')
        final = self.json(result['processing_result'], 'processing-result.json')
        require(final['processing_complete'] and final['quality_accepted'] is False and final['canonical_accepted'] is False, 'invalid completion claim')
        require(final['source'] == request, 'final source attribution')
        plan = self.json(final['plan'], 'plan.json')
        require(plan['request'] == request and plan['profile'] == profile, 'accepted plan changed')
        producer = {p.name: sha(p.read_bytes()) for p in (ROOT/'src/pdf_processing').glob('*.py')}
        require(plan['producer'] == producer and final['provenance'] == {'profile': profile, 'producer': producer}, 'producer attribution')
        parsed = self.json(final['parsed_result'], 'parsed-result.json')
        require(parsed['plan'] == final['plan'] and parsed['source'] == request and parsed['assembly'] == final['assembly'], 'parsed-result attribution')
        require(len(parsed['page_groups']) == len(plan['groups']), 'checkpoint group count')
        for group, (start, end) in zip(parsed['page_groups'], plan['groups']):
            checkpoint = self.json(group, 'complete.json')
            require(checkpoint['source_sha256'] == fixture['sha256'], 'checkpoint source attribution')
            numbers = [self.json(group, 'checkpoints/'+entry['file'])['page_no'] for entry in checkpoint['pages']]
            require(numbers == list(range(start, end+1)), 'checkpoint page coverage')
        raw = self.artifact(final['assembly'], 'document.json')
        document = json.loads(raw)
        evidence = self.json(final['content_evidence'], 'content-evidence.json')
        require(evidence['source'] == request and evidence['assembly'] == final['assembly'] and evidence['parsed_result'] == final['parsed_result'] and evidence['document_sha256'] == sha(raw), 'content attribution')
        require(sha(self.artifact(final['content_evidence'], 'source.pdf')) == fixture['sha256'], 'source changed')
        require(sha(self.artifact(final['content_evidence'], 'original-source.pdf')) == fixture['original_sha256'], 'original source changed')
        require(set(evidence['pages']) == set(document['pages']) == {str(i+1) for i in range(len(fixture['original_pages']))}, 'page coverage')
        for key, page in evidence['pages'].items():
            require(page['physical_page'] == int(key) and page['original_physical_page'] == fixture['original_pages'][int(key)-1], 'original page mapping')
            page_bytes = self.artifact(final['content_evidence'], page['artifact'])
            require(sha(page_bytes) == page['sha256'], 'unreadable page evidence')
            with Image.open(BytesIO(page_bytes)) as image:
                require(list(image.size) == page['pixel_dimensions'], 'page image dimensions')
                image.verify()
        binding = self.json(final['relationships'], 'relationships.json')
        require(binding['content_evidence'] == final['content_evidence'], 'relationship evidence binding')
        relations = binding['relationships']
        validate(relations, document, request, final['parsed_result'], final['assembly'], profile['content_evidence']['relationships'])
        selection = self.json(final['selection'], 'selection.json')
        require(selection['plan'] == final['plan'] and selection['source'] == request and selection['assembly'] == final['assembly'] and selection['parsed_result'] == final['parsed_result'], 'selection attribution')
        require(final['required_work'] == {'pages': len(fixture['original_pages']), 'components': len(final['enrichments']), 'ocr': 'complete' if final['enrichments'] else 'not_applicable', 'relationships': 'finished'}, 'required-work completion contract')
        pictures = sorted(n['self_ref'] for n in document['pictures'])
        require(sorted(selection['selected']) == pictures == sorted(e['component'] for e in final['enrichments']), 'missing required OCR')
        for entry in final['enrichments']:
            ocr = self.json(entry['operation'], 'ocr.json')
            require(ocr['component'] == entry['component'] and ocr['source'] == request
                and ocr['selection'] == final['selection'] and ocr['parsed_result'] == final['parsed_result']
                and ocr['method'] == selection['ocr_method']
                and ocr['outcome'] == entry['outcome'] and ocr['outcome'] in ('text_detected', 'no_text_detected'), 'OCR component attribution')
            crop = self.artifact(entry['operation'], 'figure.png')
            require(sha(crop) == ocr['crop_sha256'], 'OCR crop attribution')
            with Image.open(BytesIO(crop)) as image:
                image.verify()
        for step in result['steps']:
            registration = self.store.resolve(step['operation'])
            require(registration is not None, 'missing intermediate work')
            self.inventory[step['operation']] = registration
        self.out.mkdir(exist_ok=True)
        (self.out/'document.json').write_bytes(raw)
        reference = json.loads((oracles.parent/'references'/(fixture['id']+'.json')).read_text())
        graph_sha = check_reference(document, reference, self.out)
        checks = check_fixture(fixture['id'], document, evidence, relations, profile['content_evidence']['relationships'], oracles)
        self.out.mkdir(exist_ok=True)
        (self.out/'document.json').write_bytes(raw)
        checks['full_reference_graph_sha256'] = graph_sha
        for name, value in [('content-evidence', evidence), ('relationships', binding), ('registrations', self.inventory), ('checks', checks)]:
            (self.out/(name+'.json')).write_text(json.dumps(value, indent=2))
        return {'final': final, 'document_sha256': sha(raw), 'checks': checks}
