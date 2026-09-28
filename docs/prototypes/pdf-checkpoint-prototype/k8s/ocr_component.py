"""THROWAWAY: real post-parsing OCR of a version-bound figure, no parsing stages."""
import base64
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import pypdfium2 as pdfium
from PIL import Image
from rapidocr import RapidOCR
import rapidocr

root = Path(__file__).resolve().parent.parent
parsed, source, out = map(Path, sys.argv[1:4])
out.mkdir(parents=True, exist_ok=True)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
doc = json.loads(parsed.read_text())
item = doc['pictures'][0]
prov = item['prov'][0]
assert prov['page_no'] == 5
assert len(item['captions']) == 1
caption_ref = item['captions'][0]['$ref']
assert caption_ref.startswith('#/texts/')
caption = doc['texts'][int(caption_ref.split('/')[-1])]
assert caption['self_ref'] == caption_ref
assert caption['text'].startswith('Fig. 1. A timeline of existing large language models')
assert caption['prov'][0]['page_no'] == prov['page_no']
ref = json.loads((root / 'ocr-reference.json').read_text())
assert ref['component'] == item['self_ref']
pdf = pdfium.PdfDocument(source)
page = pdf[prov['page_no']-1]
b = prov['bbox']
assert b['coord_origin'] == 'BOTTOMLEFT'
w,h = page.get_size()
box = (b['l'], h-b['t'], b['r'], h-b['b'])
assert 0 <= box[0] < box[2] <= w and 0 <= box[1] < box[3] <= h
# Validate coordinates against the exact cached page/crop emitted by Docling.
page_pixels = Image.open(io.BytesIO(base64.b64decode(doc['pages']['5']['image']['uri'].split(',')[1])))
original_crop = Image.open(io.BytesIO(base64.b64decode(item['image']['uri'].split(',')[1])))
assert page_pixels.crop(box).tobytes() == original_crop.tobytes()
scale = 3
crop = page.render(scale=scale).to_pil().crop(tuple(x*scale for x in box))
crop.save(out/'figure.png')
t = time.perf_counter()
engine = RapidOCR()
result = engine(crop)
elapsed = time.perf_counter()-t
texts = list(result.txts) if result.txts else []
normalize = lambda s: ''.join(c.lower() for c in s if c.isalnum())
normalized = normalize(' '.join(texts))
matched = [label for label in ref['labels'] if normalize(label) in normalized]
missing = [label for label in ref['labels'] if label not in matched]
report = {'component': item['self_ref'], 'parsed_result_sha256': sha(parsed),
 'source_sha256': sha(source), 'provenance': prov, 'caption_ref': caption_ref, 'caption_text': caption['text'], 'render_scale': scale,
 'pixel_dimensions': crop.size, 'crop_sha256': sha(out/'figure.png'),
 'cached_component_pixels_match_coordinates': True,
 'producer': {'engine': 'RapidOCR', 'version': '3.9.2', 'backend': 'onnxruntime 1.24.3',
  'model_sha256': {p.name: sha(p) for p in (Path(rapidocr.__file__).parent/'models').glob('*.onnx')}},
 'seconds_including_engine_load': elapsed, 'texts': texts,
 'scores': [float(x) for x in result.scores], 'boxes': result.boxes.tolist(),
 'reference_sha256': sha(root/'ocr-reference.json'), 'matched_labels': matched, 'missing_labels': missing,
 'label_recall': len(matched)/len(ref['labels']),
 'accuracy_scope': 'Case/punctuation-insensitive substring recall of manually transcribed diagram labels; not character error rate or precision. Diagram reading order is not scored.'}
(out/'ocr.json').write_text(json.dumps(report, indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('boxes','scores')},indent=2))
