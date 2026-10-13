"""THROWAWAY Q39 spike: pinned Docling serialization, no inference or services.

Run with the existing Docling 2.102.0 / Core 2.96.0 Python environment.
Outputs use synthetic fixtures; no customer documents are included.
"""
import copy
import hashlib
import json
import os
import shutil
import tempfile
from importlib.metadata import version
from pathlib import Path

from PIL import Image
from pydantic import ValidationError
from docling.datamodel.document import ConversionResult
from docling_core.types.doc import (
    BoundingBox, DocItemLabel, DoclingDocument, ImageRef, ImageRefMode,
    ProvenanceItem, Size, TableCell, TableData,
)
from docling_core.types.doc.common.annotations import DescriptionAnnotation

HERE = Path(__file__).resolve().parent
records = []


def record(name, observation, **details):
    records.append({'case': name, 'observation': observation, **details})


def prov(left=10.123456789):
    return ProvenanceItem(page_no=1, bbox=BoundingBox(l=left, t=10, r=70, b=30), charspan=(0, 5))


def fixture():
    doc = DoclingDocument(name='Q39 synthetic fixture')
    doc.add_page(page_no=1, size=Size(width=100, height=100),
                 image=ImageRef.from_pil(Image.new('RGB', (100, 100), '#f0e0d0'), dpi=72))
    doc.add_text(label=DocItemLabel.TITLE, text='繁體中文 / Formula', orig='繁體中文 / Formula', prov=prov())
    group = doc.add_inline_group(name='inline expression')
    doc.add_text(label=DocItemLabel.TEXT, text='When ', parent=group, prov=prov())
    doc.add_formula(text=r'x_i^2 \leq 1', orig='xᵢ² ≤ 1', parent=group, prov=prov())
    doc.add_text(label=DocItemLabel.TEXT, text=', stop.', parent=group, prov=prov())
    caption = doc.add_text(label=DocItemLabel.CAPTION, text='Figure 1: source caption', prov=prov())
    doc.add_picture(image=ImageRef.from_pil(Image.new('RGB', (12, 8), '#287080'), dpi=72),
                    caption=caption, prov=prov(),
                    annotations=[DescriptionAnnotation(text='Derived description', provenance='synthetic-producer')])
    doc.add_table(data=TableData(num_rows=2, num_cols=2, table_cells=[
        TableCell(text='Merged header', row_span=1, col_span=2,
                  start_row_offset_idx=0, end_row_offset_idx=1,
                  start_col_offset_idx=0, end_col_offset_idx=2, column_header=True),
        TableCell(text='A', start_row_offset_idx=1, end_row_offset_idx=2,
                  start_col_offset_idx=0, end_col_offset_idx=1),
        TableCell(text='1.25', start_row_offset_idx=1, end_row_offset_idx=2,
                  start_col_offset_idx=1, end_col_offset_idx=2),
    ]), prov=prov())
    return doc


def image_result(image):
    try:
        pixels = image.pil_image
        return {'readable': pixels is not None, 'size': list(pixels.size) if pixels else None}
    except Exception as error:
        return {'readable': False, 'error': type(error).__name__}


def rejection(payload):
    try:
        DoclingDocument.model_validate(payload)
        return None
    except ValidationError as error:
        return [{'type': e['type'], 'loc': list(e['loc'])} for e in error.errors(include_url=False)]


with tempfile.TemporaryDirectory(prefix='Q39-PROTOTYPE-wipe-me-') as temporary:
    root = Path(temporary)
    doc = fixture()
    baseline = doc.export_to_dict()
    doc.save_as_json(root / 'embedded.json')
    stored = json.loads((root / 'embedded.json').read_text())
    restored = DoclingDocument.load_from_json(root / 'embedded.json')
    assert restored.export_to_dict() == baseline == stored
    assert restored.texts[0].prov[0].bbox.l == 10.123456789
    assert restored.pictures[0].captions == doc.pictures[0].captions
    assert restored.tables[0].data.table_cells[0].col_span == 2
    assert image_result(restored.pictures[0].image)['readable']
    assert image_result(restored.pages[1].image)['readable']
    record('Known schema, embedded images', 'PASS', semantic_tree_equal=True,
           unicode_orig_inline_formula_caption_refs_merged_cells_annotations_precision_preserved=True,
           document_schema=stored['version'])

    future = copy.deepcopy(stored)
    future['future_provider_extension'] = {'confidence_explanation': 'must survive raw preservation'}
    raw_bytes = json.dumps(future, ensure_ascii=False).encode()
    (root / 'raw-provider.json').write_bytes(raw_bytes)
    copied = (root / 'raw-provider.json').read_bytes()
    assert copied == raw_bytes
    normalized = DoclingDocument.model_validate_json(copied).export_to_dict()
    assert 'future_provider_extension' not in normalized
    record('Unknown top-level field', 'SILENT_DROP_ON_TYPED_ROUNDTRIP',
           raw_bytes_preserved=True, typed_roundtrip_preserved=False,
           sha256=hashlib.sha256(raw_bytes).hexdigest())

    unknown_item = copy.deepcopy(stored)
    unknown_item['texts'][0]['future_provider_extension'] = {'value': 7}
    errors = rejection(unknown_item)
    assert errors and any(e['type'] == 'extra_forbidden' for e in errors)
    record('Unknown item field', 'REJECTED', validation_errors=errors)

    old = copy.deepcopy(stored)
    major, minor, patch = map(int, stored['version'].split('.'))
    old['version'] = f'{major}.{minor - 1}.0'
    normalized_old = DoclingDocument.model_validate(old).export_to_dict()
    assert normalized_old['version'] == stored['version']
    future_version = copy.deepcopy(stored)
    future_version['version'] = f'{major}.{minor + 1}.0'
    assert rejection(future_version)
    record('Schema versions', 'OLDER_NORMALIZED_NEWER_REJECTED',
           original_old_version=old['version'], normalized_version=normalized_old['version'],
           rejected_future_version=future_version['version'])

    outside = copy.deepcopy(stored)
    outside['texts'][0]['prov'][0]['bbox']['l'] = -4.25
    restored_outside = DoclingDocument.model_validate(outside).export_to_dict()
    assert restored_outside['texts'][0]['prov'][0]['bbox']['l'] == 0
    record('Source bbox outside page', 'NORMALIZED_ON_LOAD', before=-4.25, after=0,
           note='A typed reload can change source observations even without inference.')

    broken = copy.deepcopy(stored)
    broken['body']['children'].append({'$ref': '#/texts/9999'})
    try:
        DoclingDocument.model_validate(broken)
        broken_outcome = 'accepted'
    except Exception as error:
        broken_outcome = type(error).__name__
    assert broken_outcome != 'accepted'
    record('Dangling body reference', 'REJECTED', exception=broken_outcome)

    absolute_bundle = root / 'absolute-bundle'
    absolute_bundle.mkdir()
    doc.save_as_json(absolute_bundle / 'document.json', image_mode=ImageRefMode.REFERENCED)
    absolute_payload = json.loads((absolute_bundle / 'document.json').read_text())
    assert Path(absolute_payload['pictures'][0]['image']['uri']).is_absolute()
    absolute_moved = root / 'absolute-moved'
    shutil.move(absolute_bundle, absolute_moved)
    absolute_loaded = DoclingDocument.load_from_json(absolute_moved / 'document.json')
    absolute_image = image_result(absolute_loaded.pictures[0].image)
    assert not absolute_image['readable']
    record('REFERENCED default with absolute output path', 'ABSOLUTE_PATH_BREAKS_AFTER_MOVE',
           json_load_succeeded=True, after_move=absolute_image)

    bundle = root / 'bundle'
    bundle.mkdir()
    doc.save_as_json(bundle / 'document.json', artifacts_dir=Path('images'), image_mode=ImageRefMode.REFERENCED)
    referenced_payload = json.loads((bundle / 'document.json').read_text())
    uris = {'picture': referenced_payload['pictures'][0]['image']['uri'],
            'page': referenced_payload['pages']['1']['image']['uri']}
    assert all(not Path(u).is_absolute() for u in uris.values())
    moved = root / 'moved'
    shutil.move(bundle, moved)
    original_cwd = Path.cwd()
    try:
        os.chdir(root)
        moved_doc = DoclingDocument.load_from_json(moved / 'document.json')
        wrong_cwd = {k: image_result(v) for k, v in (
            ('picture', moved_doc.pictures[0].image), ('page', moved_doc.pages[1].image))}
        assert all(not value['readable'] for value in wrong_cwd.values())
        os.chdir(moved)
        moved_doc = DoclingDocument.load_from_json(moved / 'document.json')
        right_cwd = {k: image_result(v) for k, v in (
            ('picture', moved_doc.pictures[0].image), ('page', moved_doc.pages[1].image))}
        assert all(value['readable'] for value in right_cwd.values())
        (moved / uris['picture']).unlink()
        missing_doc = DoclingDocument.load_from_json(moved / 'document.json')
        missing = image_result(missing_doc.pictures[0].image)
        assert not missing['readable']
    finally:
        os.chdir(original_cwd)
    record('Referenced bundle relocation', 'LOAD_OK_IMAGES_DEPEND_ON_RESOLUTION',
           original_and_relative_uris=uris, wrong_cwd=wrong_cwd,
           correct_bundle_root=right_cwd, missing_picture_after_successful_json_load=missing,
           note='Changing process CWD demonstrates the defect; it is not a concurrent-worker design recommendation.')

    external_page = root / 'external-page.png'
    Image.new('RGB', (100, 100), 'white').save(external_page)
    external_doc = fixture()
    external_doc.pages[1].image = ImageRef(mimetype='image/png', dpi=72,
        size=Size(width=100, height=100), uri=external_page)
    external_doc.save_as_json(root / 'embedded-with-external-page.json')
    external_stored = json.loads((root / 'embedded-with-external-page.json').read_text())
    page_uri = external_stored['pages']['1']['image']['uri']
    external_page.unlink()
    external_reloaded = DoclingDocument.load_from_json(root / 'embedded-with-external-page.json')
    external_result = image_result(external_reloaded.pages[1].image)
    assert not page_uri.startswith('data:') and not external_result['readable']
    record('EMBEDDED mode with existing external page image', 'NOT_SELF_CONTAINED',
           page_uri_kind='external path', after_original_removed=external_result)

    result_fields = set(ConversionResult.model_fields)
    absent = sorted(result_fields - set(stored))
    assert all(k not in stored for k in ('status', 'errors', 'confidence', 'timings'))
    record('Document JSON versus processing envelope', 'SEPARATE_ARTIFACTS_NEEDED',
           absent_from_document_json=absent,
           note='Retain the existing result/checkpoint/enrichment references; this does not select Q38 status policy.')

    (HERE / 'synthetic-document.json').write_text(json.dumps(stored, ensure_ascii=False, indent=2))

report = {
    'scope': 'Synthetic fixture roundtrip only; no PDF parsing, model inference, production mapping or DB writes.',
    'packages': {name: version(name) for name in ('docling', 'docling-core', 'pydantic', 'Pillow')},
    'cases': records,
    'recommendation': 'Retain emitted provider bytes and dependency references before typed adaptation; map required semantics explicitly; preserve deferred content with a disposition.',
}
(HERE / 'observations.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps({'packages': report['packages'], 'cases': [
    {'case': c['case'], 'observation': c['observation']} for c in records]}, ensure_ascii=False, indent=2))
