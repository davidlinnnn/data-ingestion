"""Offline retained-output audit; no models, source text output, or service writes.

Run: rtk python3 probe.py --implementation <integrated checkout> --out <new JSON>
Private inputs use the retained locations below; their absence fails the probe.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root):
    consumer = load_module('consumer', root/'tests/pdf_processing/q04/consumer.py')
    evidence = load_module('evidence', root/'src/pdf_processing/evidence.py')
    bundle = Path('/private/tmp/q44-inputs-warm-20260928-db')
    manifest = json.loads((bundle/'inputs.json').read_text())
    rows = []
    references = {}
    for sid, expected in manifest['reference_graphs'].items():
        path = bundle/'references'/(sid+'.json')
        document = json.loads(path.read_text())
        graph_sha = consumer.sha(consumer.canonical(consumer.graph_projection(document)).encode())
        assert sha(path) == expected, (sid, 'retained reference identity')
        references[sid] = document
        rows.append({'fixture': sid, 'path': str(path), 'sha256': sha(path),
            'graph_sha256': graph_sha, 'keys': sorted(document),
            'collections': {k: len(document.get(k, [])) for k in ('texts', 'tables',
                'pictures', 'field_regions', 'field_items', 'key_value_items', 'form_items')},
            'heading_levels': sorted({n.get('level') for n in document['texts']
                if n.get('label') == 'section_header' and n.get('level') is not None})})
    comparisons = []
    state = Path('/private/tmp/t09b-calibration-20260930-a12/evidence/state/t09b-calibration-a12')
    for sid, name in [('06', 'warm-0-06'), ('07', 'warm-1-07'), ('08', 'warm-2-08'), ('native', 'warm-3-native')]:
        path = state/name/'document.json'
        document = json.loads(path.read_text())
        before, after = consumer.graph_projection(references[sid]), consumer.graph_projection(document)
        cells = [c for t in document.get('tables', []) for c in t['data']['table_cells']]
        comparisons.append({'fixture': sid, 'path': str(path), 'sha256': sha(path),
            'original_q44_reference_graph_equal': before == after,
            'different_projected_keys': sorted(k for k in before if before[k] != after[k]),
            'full_json_equal': document == references[sid],
            'different_top_level_keys': sorted(k for k in document.keys() | references[sid].keys()
                if document.get(k) != references[sid].get(k)),
            'actual_populated_output': {'table_cells': len(cells),
                'spanning_cells': sum(c['row_span'] > 1 or c['col_span'] > 1 for c in cells),
                'caption_links': sum(len(n.get('captions', [])) for k in ('pictures', 'tables') for n in document.get(k, [])),
                'picture_child_links': sum(len(n.get('children', [])) for n in document.get('pictures', [])),
                'picture_annotations': sum(len(n.get('annotations', [])) for n in document.get('pictures', [])),
                'field_regions': len(document.get('field_regions', [])),
                'field_items': len(document.get('field_items', [])),
                'text_labels': dict(consumer.Counter(n['label'] for n in document['texts'])),
                'heading_levels': sorted({n.get('level') for n in document['texts']
                    if n['label'] == 'section_header' and n.get('level') is not None})}})
    aima = state/'warm-2-08/document.json'
    delivery = Path('/private/tmp/pdf-t10-f-result/assembly/document.json')
    assert delivery.read_bytes() == aima.read_bytes()
    native = state/'warm-3-native/document.json'
    recovered = Path('/private/tmp/t09b-calibration-20260930-ra2/evidence/state/t09b-calibration-ra2/drain-native/document.json')
    assert native.read_bytes() == recovered.read_bytes()
    repeated = state/'warm-4-06/document.json'
    assert (state/'warm-0-06/document.json').read_bytes() == repeated.read_bytes()
    export = delivery.parents[1]
    final = json.loads((export/'processing-result.json').read_text())
    selection = json.loads((export/'selection/selection.json').read_text())
    content = json.loads((export/'content-evidence/content-evidence.json').read_text())
    assert final['processing_complete'] and not final['canonical_accepted'] and not final['quality_accepted']
    assert content['document_sha256'] == sha(delivery)
    assert content['source'] == final['source'] == selection['source']
    assert sha(export/'content-evidence/source.pdf') == final['source']['artifact']['sha256']
    for page in content['pages'].values():
        assert sha(export/'content-evidence'/page['artifact']) == page['sha256']
    pictures = {p['self_ref']: p for p in json.loads(delivery.read_text())['pictures']}
    components = []
    for folder in sorted(export.glob('ocr-*')):
        ocr = json.loads((folder/'ocr.json').read_text())
        assert ocr['source'] == final['source'] and ocr['assembly'] == final['assembly']
        assert ocr['method'] == selection['ocr_method'] and ocr['selection'] == final['selection']
        assert ocr['provenance'] in pictures[ocr['component']]['prov']
        assert sha(folder/'figure.png') == ocr['crop_sha256']
        components.append(ocr['component'])
    assert len(components) == 9 and set(components) == set(selection['selected']) == set(pictures)
    checks = {sid: json.loads((state/name/'checks.json').read_text()) for sid, name in
        [('06', 'warm-0-06'), ('07', 'warm-1-07'), ('08', 'warm-2-08'), ('native', 'warm-3-native')]}
    original = json.loads(delivery.read_text())
    synthetic = copy.deepcopy(original)
    for key in ('field_regions', 'field_items'):
        synthetic[key] = [{'self_ref': '#/'+key+'/0', 'research_probe': True}]
    synthetic['research_top_level_metadata'] = {'producer': 'synthetic'}
    assert consumer.graph_projection(synthetic) == consumer.graph_projection(original)
    assert synthetic != original
    visited = {n['self_ref'] for n in evidence.graph_items(synthetic)}
    assert '#/field_regions/0' not in visited and '#/field_items/0' not in visited
    table = copy.deepcopy(references['07'])
    assert table['tables'][0]['data']['table_cells']
    table['tables'][0]['data']['table_cells'][0]['row_span'] += 1
    assert consumer.graph_projection(table) != consumer.graph_projection(references['07'])
    return {'scope': 'read-only retained JSON and synthetic comparator probe; no new inference or API round trip',
        'implementation_head': subprocess.check_output(['rtk', 'git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'producers': {str(p.relative_to(root)): sha(p) for p in [root/'src/pdf_processing/evidence.py', root/'tests/pdf_processing/q04/consumer.py']},
        'manifest_sha256': sha(bundle/'inputs.json'), 'inventory': rows, 'comparisons': comparisons,
        't10_f_equals_a12_aima_bytes': True, 't10_f_sha256': sha(delivery),
        'retained_same_method_recovery': {'uninterrupted': str(native), 'recovered': str(recovered),
            'byte_equal': True, 'sha256': sha(native), 'claim': 'existing accepted bytes rechecked; no fault rerun'},
        'wiki_later_request_byte_equal': True, 'retained_checks': checks,
        't10_f_local_export_attribution': {'pages_hash_checked': len(content['pages']),
            'ocr_components_and_crop_hashes_checked': len(components), 'canonical_accepted': False,
            'quality_accepted': False, 'remote_store_reread_or_ocr_quality_claimed': False},
        'synthetic_probe': {'field_and_top_level_changes_escape_q04_projection': True,
            'field_items_absent_from_evidence_index': True, 'table_span_change_detected': True,
            'schema_validity_or_selected_parser_population_claimed': False}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--implementation', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.implementation)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'references': len(result['inventory']), 'comparisons': len(result['comparisons']),
        't10_f_byte_equal': True, 'synthetic_comparator_checks': 'PASS'}))
