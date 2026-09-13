"""One justified detected-picture crop OCR control; not production enrichment."""
from pathlib import Path
import json,hashlib,sys
import pypdfium2 as pdfium
from rapidocr import RapidOCR
R=Path(__file__).resolve().parent;L=R/'local';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
p=json.loads((R/'new-plan.json').read_text());s=p['sources'][1];f=Path(sys.argv[1])/s['file'];assert sha(f)==s['sha256']
j=json.loads((L/'10-1.json').read_text());pic=j['pictures'][0];b=pic['prov'][0]['bbox'];h=j['pages']['1']['size']['height'];box=[b['l'],h-b['t'],b['r'],h-b['b']]
d=pdfium.PdfDocument(f);pg=d[0];crop=L/'10-1-detected-picture-3x.png';pg.render(scale=3).to_pil().crop(tuple(round(v*3) for v in box)).save(crop)
o=RapidOCR()(str(crop));txt='\n'.join(o.txts or []);(L/'10-1-detected-picture-ocr.txt').write_text(txt)
expected='Both persist progress and dispatch work. Application logic still owns idempotency and data consistency.';norm=lambda x:''.join(x.split())
r=dict(question='Does OCR of the actual detected PictureItem recover the missing final word and whole common-note sentence?',source_sha256=sha(f),parsed_result_sha256=sha(L/'10-1.json'),typed_ref=pic['self_ref'],physical_page=1,bbox=box,coordinate_convention='TOPLEFT points in rendered CropBox',cropbox=pg.get_cropbox(),scale=3,crop_sha256=sha(crop),ocr_output_sha256=sha(L/'10-1-detected-picture-ocr.txt'),expected=expected,missing_word_recovered='consistency.' in txt,whole_sentence_whitespace_match=norm(expected) in norm(txt),models={str(x.name):sha(x) for x in Path(__import__('rapidocr').__file__).parent.rglob('*.onnx')})
(R/'slide-crop-control.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));pg.close();d.close()
