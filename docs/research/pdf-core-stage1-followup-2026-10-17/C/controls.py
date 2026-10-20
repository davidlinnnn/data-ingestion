"""Bounded cached-native image integration; no model, converter, client or install."""
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from PIL import Image
from docling_core.types.doc import DescriptionMetaField, DoclingDocument, ImageRef, ImageRefMode

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
S0 = ROOT / 'docs/research/pdf-core-native-round-2026-10-17'
SOURCE = S0 / 'S0/nccu/document.json'
METHOD = 'C-native-same-input-v2'
VERSIONS = {'docling-slim': '2.132.0', 'docling-core': '2.99.0', 'docling-parse': '7.22.3', 'pypdfium2': '5.14.0'}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def markdown(doc):
    return doc.export_to_markdown(image_mode=ImageRefMode.REFERENCED,
                                  allowed_meta_names=set(), include_annotations=False)


def rotate(point, width, height, clockwise):
    x, y = point
    if clockwise == 0:
        return [x, y]
    if clockwise == 90:
        return [height-y, x]
    if clockwise == 180:
        return [width-x, height-y]
    if clockwise == 270:
        return [y, width-x]
    raise ValueError('rotation must be 0/90/180/270')


def to_page(point, mapping):
    x, y = point
    width, height = mapping['crop_size_px']
    if not (0 <= x <= width and 0 <= y <= height):
        raise ValueError('crop polygon outside delivered image')
    left, top, _, _ = mapping['page_pixel_window']
    sx, sy = mapping['page_scale_xy']
    return [(x+left)/sx, (y+top)/sy]


def native_mapping(doc, picture):
    page = doc.pages[picture.prov[0].page_no]
    # Pinned Standard records images_scale through both page and picture ImageRef dpi.
    scale = picture.image.dpi / 72
    if scale <= 0 or page.image.dpi != picture.image.dpi:
        raise ValueError('native page/picture scale identity mismatch')
    bbox = picture.prov[0].bbox.scaled(scale=scale).to_top_left_origin(page_height=page.size.height*scale)
    window = [round(v) for v in bbox.as_tuple()]
    image = picture.get_image(doc)
    pixel_crop = page.image.pil_image.crop(tuple(window))
    if image.size != pixel_crop.size or image.tobytes() != pixel_crop.tobytes():
        raise ValueError('baseline native crop does not match page window')
    return {'method':'pinned Standard images_scale + Pillow integer crop window; pixel equality verified',
            'crop_size_px':list(image.size),'page_image_size_px':list(page.image.pil_image.size),
            'page_size_pdf_points':page.size.model_dump(mode='json'),
            'native_bbox':picture.prov[0].bbox.model_dump(mode='json'),
            'requested_crop_bbox_page_px':list(bbox.as_tuple()), 'page_pixel_window':window,
            'effective_bbox_page_top_left_pdf_points':[v/scale for v in window],
            'page_scale_xy':[scale,scale], 'rotation_clockwise':0}


def validate(doc, supplement, baseline, raw):
    if supplement['method'] != METHOD or supplement['document_revision'] != digest(baseline):
        raise ValueError('method/revision mismatch')
    records = supplement['images']
    if len(records) != len(doc.pictures) or {r['owner_ref'] for r in records} != {p.self_ref for p in doc.pictures}:
        raise ValueError('missing/duplicate/foreign image owner')
    restored = doc.export_to_dict()
    baseline_doc = DoclingDocument.model_validate(baseline)
    for record in records:
        picture = next(p for p in doc.pictures if p.self_ref == record['owner_ref'])
        original = baseline['pictures'][int(picture.self_ref.rsplit('/', 1)[1])]
        if record['image_key'] != digest([supplement['document_revision'], picture.self_ref, record['crop_sha256']]):
            raise ValueError('image key mismatch')
        if str(picture.image.uri) != record['image_path'] or picture.prov[0].model_dump(mode='json') != record['provenance']:
            raise ValueError('URI/provenance mismatch')
        expected_input = {k: record[k] for k in ['owner_ref', 'image_key', 'crop_sha256']}
        if raw['input'] != expected_input or raw['evidence_kind'] != 'MOCK_same_input':
            raise ValueError('response input identity mismatch')
        if record['required_work'] != ['ocr', 'description', 'chart_assessment']:
            raise ValueError('unknown classification cannot exempt work')
        if record['classification'] != 'unknown' or record['ocr']['state'] != 'mock_response':
            raise ValueError('mock status lost')
        if record['ocr']['texts'] != [line['text'] for line in raw['ocr']]:
            raise ValueError('OCR response changed')
        if picture.meta.description.text != raw['description']:
            raise ValueError('description changed')
        mapping = record['mapping']
        native_picture = next(p for p in baseline_doc.pictures if p.self_ref == picture.self_ref)
        if mapping != native_mapping(baseline_doc, native_picture):
            raise ValueError('mapping does not match immutable native baseline')
        if picture.image.dpi != native_picture.image.dpi or picture.image.size != native_picture.image.size:
            raise ValueError('image metadata changed')
        left, top, right, bottom = mapping['page_pixel_window']
        if mapping['crop_size_px'] != [right-left, bottom-top]:
            raise ValueError('crop/window mismatch')
        if mapping['page_size_pdf_points'] != baseline['pages'][str(picture.prov[0].page_no)]['size']:
            raise ValueError('page size mismatch')
        if any(scale <= 0 for scale in mapping['page_scale_xy']):
            raise ValueError('invalid page scale')
        projected = [[to_page(point, mapping) for point in line['polygon_crop_px']] for line in raw['ocr']]
        if projected != record['ocr']['polygons_page_top_left_pdf_points']:
            raise ValueError('OCR polygon mapping mismatch')
        restored_picture = restored['pictures'][int(picture.self_ref.rsplit('/', 1)[1])]
        restored_picture['image'] = original['image']
        if 'meta' in original:
            restored_picture['meta'] = original['meta']
        else:
            restored_picture.pop('meta', None)
    if restored != baseline:
        raise ValueError('native graph/text/children/caption/order/provenance changed')


def verify_bundle(directory):
    directory = Path(directory)
    manifest = read(directory / 'bundle.json')
    actual_files = {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file() and p.name != 'bundle.json'}
    if actual_files != set(manifest['files']):
        raise ValueError('bundle file inventory mismatch')
    for name, expected in manifest['files'].items():
        if sha(directory / name) != expected:
            raise ValueError('bundle hash mismatch: '+name)
    baseline = read(directory / 'baseline.json')
    doc = DoclingDocument.load_from_json(directory / 'document.json')
    supplement = read(directory / 'supplement.json')
    raw = read(directory / 'provider/mock-response.json')
    validate(doc, supplement, baseline, raw)
    text = (directory / 'document.md').read_text()
    if text != markdown(doc) or raw['description'] in text or any(line['text'] in text for line in raw['ocr']):
        raise ValueError('Markdown changed or generated content mixed into source')
    for record in supplement['images']:
        image_path = directory / record['image_path']
        if sha(image_path) != record['crop_sha256'] or record['image_path'] not in text:
            raise ValueError('missing/unbound crop')
        with Image.open(image_path) as image:
            if list(image.size) != record['mapping']['crop_size_px']:
                raise ValueError('actual crop size mismatch')
            baseline_doc=DoclingDocument.model_validate(baseline)
            native_picture=next(p for p in baseline_doc.pictures if p.self_ref==record['owner_ref'])
            native_image=native_picture.get_image(baseline_doc)
            if image.mode!=native_image.mode or image.tobytes()!=native_image.tobytes():
                raise ValueError('delivered crop pixels differ from native baseline')
    return {'pass': True, 'native_pictures': len(doc.pictures),
            'native_picture_children': sum(len(p.children) for p in doc.pictures),
            'response_kind': raw['evidence_kind'], 'source_markdown_policy': 'no metadata/annotations',
            'verified_files': len(manifest['files'])}


def controls(directory):
    directory = Path(directory)
    baseline = read(directory / 'baseline.json')
    doc = DoclingDocument.load_from_json(directory / 'document.json')
    supplement = read(directory / 'supplement.json')
    raw = read(directory / 'provider/mock-response.json')
    validate(doc, supplement, baseline, raw)
    negatives = []
    for name, change in [
        ('revision', lambda s: s.update(document_revision='stale')),
        ('method', lambda s: s.update(method='stale')),
        ('owner', lambda s: s['images'][0].update(owner_ref='#/pictures/99')),
        ('duplicate_owner', lambda s: s['images'].append(copy.deepcopy(s['images'][0]))),
        ('key', lambda s: s['images'][0].update(image_key='foreign')),
        ('input_crop', lambda s: s['images'][0].update(crop_sha256='foreign')),
        ('provenance', lambda s: s['images'][0]['provenance'].update(page_no=99)),
        ('work_exemption', lambda s: s['images'][0].update(required_work=[])),
        ('window', lambda s: s['images'][0]['mapping']['page_pixel_window'].__setitem__(0, 126)),
        ('scale', lambda s: s['images'][0]['mapping']['page_scale_xy'].__setitem__(0, 3)),
        ('page_size', lambda s: s['images'][0]['mapping']['page_size_pdf_points'].update(width=999)),
        ('mapped_polygon', lambda s: s['images'][0]['ocr']['polygons_page_top_left_pdf_points'][0][0].__setitem__(0, -5)),
    ]:
        altered = copy.deepcopy(supplement)
        change(altered)
        try:
            validate(doc, altered, baseline, raw)
        except (ValueError, StopIteration):
            negatives.append(name)
        else:
            raise AssertionError('accepted negative: '+name)
    wrong_input = copy.deepcopy(raw)
    wrong_input['input']['crop_sha256'] = 'different crop'
    try:
        validate(doc, supplement, baseline, wrong_input)
    except ValueError:
        negatives.append('raw_response_other_crop')
    else:
        raise AssertionError('response from another crop accepted')
    outside = copy.deepcopy(raw)
    outside['ocr'][0]['polygon_crop_px'][0] = [-1, 0]
    try:
        validate(doc, supplement, baseline, outside)
    except ValueError:
        negatives.append('raw_polygon_outside_crop')
    else:
        raise AssertionError('out of bounds polygon accepted')
    for name, change in [
        ('coordinated_scale_and_polygon', lambda m: m['page_scale_xy'].__setitem__(0, m['page_scale_xy'][0]+1)),
        ('coordinated_translated_window_and_polygon', lambda m: m.update(page_pixel_window=[v+1 for v in m['page_pixel_window']])),
    ]:
        altered=copy.deepcopy(supplement)
        record=altered['images'][0]
        change(record['mapping'])
        record['ocr']['polygons_page_top_left_pdf_points']=[[to_page(p,record['mapping']) for p in line['polygon_crop_px']] for line in raw['ocr']]
        try:
            validate(doc,altered,baseline,raw)
        except ValueError:
            negatives.append(name)
        else:
            raise AssertionError('coordinated mapping mutation accepted: '+name)
    geometry = []
    # Synthetic geometry includes anisotropic X/Y scaling; no orientation model is loaded.
    mapping = {'crop_size_px': [317, 199], 'page_pixel_window': [41, 73, 358, 272], 'page_scale_xy': [2.3, 1.7]}
    points = [[0,0], [317,0], [317,199], [0,199], [13.25,72.5], [201.75,18.125]]
    for angle in [0,90,180,270]:
        width, height = mapping['crop_size_px']
        rotated_size = [height,width] if angle in [90,270] else [width,height]
        for point in points:
            turned = rotate(point,width,height,angle)
            inverse = rotate(turned,*rotated_size,(360-angle)%360)
            assert max(abs(a-b) for a,b in zip(point,inverse)) < 1e-9
            pdf = to_page(inverse,mapping)
            back = [pdf[0]*2.3-41,pdf[1]*1.7-73]
            assert max(abs(a-b) for a,b in zip(point,back)) < 1e-9
        geometry.append({'clockwise':angle,'points':len(points),'inverse_roundtrip_pass':True,'rotated_size':rotated_size})
    try:
        rotate([0,0],317,199,45)
    except ValueError:
        negatives.append('invalid_rotation')
    else:
        raise AssertionError('non-quarter rotation accepted')
    return {'positive_native_bundle':verify_bundle(directory), 'negative_controls_rejected':negatives,
            'four_direction_synthetic_geometry':geometry, 'orientation_detection_tested':False}


def prepare():
    start = time.monotonic()
    assert {name: importlib.metadata.version(name) for name in VERSIONS} == VERSIONS
    directory = HERE / 'bundle-original'
    directory.mkdir()  # Refuse to overwrite evidence; --check is read-only.
    (directory/'images').mkdir()
    (directory/'provider').mkdir()
    doc = DoclingDocument.load_from_json(SOURCE)
    baseline = doc.export_to_dict()
    assert len(doc.pictures) == 1
    picture = doc.pictures[0]
    page = doc.pages[picture.prov[0].page_no]
    scale = read(S0/'S0/effective-options.json')['images_scale']
    bbox = picture.prov[0].bbox.scaled(scale=scale).to_top_left_origin(page_height=page.size.height*scale)
    window = [round(v) for v in bbox.as_tuple()]
    image = picture.get_image(doc)
    pixel_crop = page.image.pil_image.crop(bbox.as_tuple())
    assert image.size == pixel_crop.size and image.tobytes() == pixel_crop.tobytes()
    temp = directory/'images/native.png'
    image.save(temp)
    crop_sha = sha(temp)
    revision = digest(baseline)
    key = digest([revision,picture.self_ref,crop_sha])
    path = f'images/{key}.png'
    temp.rename(directory/path)
    mapping = native_mapping(DoclingDocument.model_validate(baseline), picture)
    assert mapping['page_scale_xy'] == [scale, scale]
    raw = {'evidence_kind':'MOCK_same_input','model':None,'usage':None,
           'input':{'owner_ref':picture.self_ref,'image_key':key,'crop_sha256':crop_sha},
           'ocr':[{'text':'MOCK_OCR_NOT_SOURCE_TEXT','polygon_crop_px':[[22.5,14.25],[206.5,14.25],[206.5,44.75],[22.5,44.75]]}],
           'description':'MOCK_DESCRIPTION_NOT_MODEL_ACCURACY',
           'uncertainties':['synthetic payload; no claim about actual picture contents'],
           'provider_extra':{'preserve_verbatim':True}}
    # Public metadata stores the mock description; source descendants and captions remain untouched.
    if picture.meta is None:
        from docling_core.types.doc import PictureMeta
        picture.meta = PictureMeta()
    picture.meta.description = DescriptionMetaField(text=raw['description'],created_by=METHOD+' MOCK')
    picture.image = ImageRef(mimetype='image/png',dpi=baseline['pictures'][0]['image']['dpi'],
                             size=picture.image.size,uri=Path(path))
    source = next(j['source'] for j in read(S0/'inputs.json')['jobs'] if j['id']=='nccu')
    assert sha(ROOT/source['path']) == source['sha256']
    record = {'owner_ref':picture.self_ref,'image_key':key,'image_path':path,'crop_sha256':crop_sha,
              'provenance':picture.prov[0].model_dump(mode='json'),'source':source,'mapping':mapping,
              'classification':'unknown','required_work':['ocr','description','chart_assessment'],
              'ocr':{'state':'mock_response','texts':[line['text'] for line in raw['ocr']],
                     'polygons_page_top_left_pdf_points':[[to_page(p,mapping) for p in line['polygon_crop_px']] for line in raw['ocr']]},
              'description_state':'mock_response','chart_assessment_state':'unattempted'}
    supplement = {'method':METHOD,'document_revision':revision,'evidence_kind':'cached-native-plus-same-input-MOCK',
                  'source_document_sha256':sha(SOURCE),'images':[record]}
    write(directory/'baseline.json',baseline)
    write(directory/'provider/mock-response.json',raw)
    write(directory/'document.json',doc.export_to_dict())
    write(directory/'supplement.json',supplement)
    with (directory/'document.md').open('x') as stream:
        stream.write(markdown(doc))
    write(directory/'bundle.json',{'files':{str(p.relative_to(directory)):sha(p) for p in directory.rglob('*') if p.is_file()}})
    result = controls(directory)
    relocated = HERE/'bundle-relocated'
    shutil.copytree(directory,relocated)
    child = subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--verify',str(relocated.resolve())],
                           cwd=relocated,capture_output=True,text=True,check=True)
    result.update({'status':'partial','native_same_input_mechanical_gate':'pass','second_process_relocated':json.loads(child.stdout),
                   'upstream':'cached pinned S0','runtime':VERSIONS,'elapsed_control_seconds':time.monotonic()-start,
                   'new_model_calls':0,'api_calls':0,'model_loads':0,
                   'no_inference_modules_loaded':not any(n in sys.modules for n in ['torch','onnxruntime','rapidocr','openai']),
                   'not_validated':['real model content accuracy','orientation detection/inference','full source image census',
                                    'same-profile title/heading/semantic parent','fresh Standard and worker/Pod recovery']})
    assert result['no_inference_modules_loaded']
    write(HERE/'results.json',result)
    evidence_paths=[SOURCE,S0/'S0/effective-options.json',S0/'standard-runtime-v2.json',S0/'inputs.json',ROOT/source['path'],
                    ROOT/'docs/research/pdf-core-stage1-2026-10-17/C/controls.py',ROOT/'docs/research/pdf-core-stage1-2026-10-17/C/summary.md',
                    ROOT/'docs/reviews/pdf-core-stage1-main-review-2026-10-17.md']
    write(HERE/'evidence-hashes.json',{str(p.relative_to(ROOT)):sha(p) for p in evidence_paths})
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--verify':
        print(json.dumps(verify_bundle(Path(sys.argv[2]))))
    elif len(sys.argv)>1 and sys.argv[1]=='--check':
        result=controls(HERE/'bundle-original')
        result['relocated']=verify_bundle(HERE/'bundle-relocated')
        assert all(sha(ROOT/name)==expected for name,expected in read(HERE/'evidence-hashes.json').items())
        source_doc=DoclingDocument.load_from_json(SOURCE)
        assert source_doc.export_to_dict()==read(HERE/'bundle-original/baseline.json')
        crop=source_doc.pictures[0].get_image(source_doc)
        mapping=read(HERE/'bundle-original/supplement.json')['images'][0]['mapping']
        page=source_doc.pages[source_doc.pictures[0].prov[0].page_no]
        from_page=page.image.pil_image.crop(tuple(mapping['page_pixel_window']))
        assert crop.size==from_page.size and crop.tobytes()==from_page.tobytes()
        print(json.dumps(result,indent=2))
    else:
        prepare()
