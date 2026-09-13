"""THROWAWAY eight-page native structural diagnostic; no whole-document inference."""
import os,sys,json,hashlib,platform,importlib.metadata as md
from pathlib import Path
R=Path(__file__).resolve().parent;O=R/'local';S=Path(sys.argv[1]);P=json.loads((R/'plan.json').read_text());os.environ['HF_HOME']='/experiment/PROTOTYPE-wipe-me/hf'
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions,RapidOcrOptions
from docling.datamodel.accelerator_options import AcceleratorOptions,AcceleratorDevice
from docling.document_converter import DocumentConverter,PdfFormatOption
import pypdfium2 as pdfium
from rapidocr import RapidOCR
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2))
def norm(t):return ''.join(t.split())
def check(t,anchors):return [dict(anchor=a,found=norm(a) in norm(t)) for a in anchors]
def box(p):return p.bbox.model_dump(mode='json')
def crop(source,page,bbox,target):
 d=pdfium.PdfDocument(source);pg=d[page-1];im=pg.render(scale=3).to_pil().crop(tuple(round(v*3) for v in bbox));im.save(target);pg.close();d.close();return sha(target)
opts=ThreadedPdfPipelineOptions(do_ocr=False,ocr_options=RapidOcrOptions(backend='onnxruntime',force_full_page_ocr=False),do_table_structure=True,generate_page_images=True,generate_picture_images=True,images_scale=1,accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU,num_threads=4))
rapid=Path(__import__('rapidocr').__file__).parent;models={str(p):sha(p) for p in Path(os.environ['HF_HOME']).rglob('*') if p.is_file()};models.update({str(p):sha(p) for p in rapid.rglob('*.onnx')});base=json.loads(Path('/experiment/evidence/native-method.json').read_text());assert all(v in models.values() for v in base['model_artifacts'].values())
dump(R/'environment.json',dict(platform=platform.platform(),python=sys.version,packages={d.metadata['Name']:d.version for d in md.distributions()},models=models,baseline_models_matched=len(base['model_artifacts']),options=opts.model_dump(mode='json'),plan_sha256=sha(R/'plan.json')))
c=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=opts)});rows=[]
for case in P['pages']:
 src=next(x for x in P['sources'] if x['id']==case['source_id']);f=S/src['file'];assert sha(f)==src['sha256'];n=case['page'];stem=f'{src["id"]}-{n}'
 pd=pdfium.PdfDocument(f);page=pd[n-1];native=page.get_textpage().get_text_range();render=page.render(scale=1.5).to_pil();render.save(O/(stem+'-source.png'));page.close();pd.close()
 result=c.convert(f,page_range=(n,n));doc=result.document;doc.save_as_json(O/(stem+'.json'));text=doc.export_to_markdown();(O/(stem+'.md')).write_text(text)
 pics=[dict(ref=x.self_ref,bboxes=[box(p) for p in x.prov],pages=[p.page_no for p in x.prov],captions=[dict(ref=y.cref,text=y.resolve(doc).text) for y in x.captions]) for x in doc.pictures]
 tables=[]
 for t in doc.tables:
  expected=next((x for x in P['tables'] if x['source_id']==src['id'] and x['page']==n),None);cells=[]
  if expected:
   for e in expected['cells']:
    matching=[cell.text for cell in t.data.table_cells if cell.start_row_offset_idx<=e['row']<cell.end_row_offset_idx and cell.start_col_offset_idx<=e['col']<cell.end_col_offset_idx];cells.append(dict(e,actual=matching,found=any(norm(e['value']) in norm(x) for x in matching)))
  tables.append(dict(ref=t.self_ref,rows=t.data.num_rows,cols=t.data.num_cols,expected=expected,cells=cells,spans=[dict(row=x.start_row_offset_idx,col=x.start_col_offset_idx,rowspan=x.row_span,colspan=x.col_span) for x in t.data.table_cells if x.row_span>1 or x.col_span>1],bboxes=[box(p) for p in t.prov]))
 paragraphs=[dict(expected=x['text'],exact_present=norm(x['text']) in norm(text),native_exact_present=norm(x['text']) in norm(native)) for x in P['paragraphs'] if x['source_id']==src['id'] and x['page']==n]
 positions=[norm(text).find(norm(a)) for a in case['order']]
 rows.append(dict(source_id=src['id'],page=n,printed=case['printed'],status=str(result.status),source_native_characters=len(norm(native)),source_native_replacement_characters=native.count('\ufffd'),anchors=check(text,case['anchors']),order=dict(anchors=case['order'],positions=positions,passed=all(x>=0 for x in positions) and positions==sorted(positions)),paragraphs=paragraphs,pictures=pics,tables=tables,formulas=[dict(ref=x.self_ref,text=x.text,provenance=[dict(page=p.page_no,bbox=box(p)) for p in x.prov]) for x in doc.texts if str(x.label)=='formula'],source_render_sha256=sha(O/(stem+'-source.png')),output_json_sha256=sha(O/(stem+'.json'))))
 dump(R/'scores.json',rows);print(stem,'parsed',flush=True)
engine=RapidOCR();figresults=[]
for i,e in enumerate(P['figures']):
 src=next(x for x in P['sources'] if x['id']==e['source_id']);target=O/f'figure-{i}.png';h=crop(S/src['file'],e['page'],e['bbox'],target);ocr=engine(str(target));txt='\n'.join(ocr.txts or []);(O/f'figure-{i}-ocr.txt').write_text(txt);figresults.append(dict(e,crop_sha256=h,ocr=check(txt,e['labels'])));dump(R/'figure-crops.json',figresults)
formula=[]
for i,e in enumerate(P['formula_regions']):
 src=next(x for x in P['sources'] if x['id']==e['source_id']);h=crop(S/src['file'],e['page'],e['bbox'],O/f'formula-{i}.png');formula.append(dict(e,crop_sha256=h))
dump(R/'formula-regions.json',formula);print('DONE',flush=True)
