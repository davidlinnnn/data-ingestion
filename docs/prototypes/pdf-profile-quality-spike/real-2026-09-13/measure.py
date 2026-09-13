"""THROWAWAY bounded real-source diagnostic. Outputs stay local until summarized."""
import hashlib,json,os,platform,sys,time,importlib.metadata as md
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'local';OUT.mkdir(exist_ok=True)
os.environ['HF_HOME']='/experiment/PROTOTYPE-wipe-me/hf';os.environ['HF_HUB_OFFLINE']='1'
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions,RapidOcrOptions
from docling.datamodel.accelerator_options import AcceleratorOptions,AcceleratorDevice
from docling.document_converter import DocumentConverter,PdfFormatOption
import pypdfium2 as pdfium
from rapidocr import RapidOCR
plan=json.loads((ROOT/'plan.json').read_text());source=Path(sys.argv[1])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def norm(s):return ''.join(s.split())
def checks(txt,anchors):return [{'anchor':a,'found':norm(a) in norm(txt)} for a in anchors]
def order(txt,anchors):
 ps=[norm(txt).find(norm(a)) for a in anchors];return dict(anchors=anchors,positions=ps,all_present_in_order=all(p>=0 for p in ps) and ps==sorted(ps))
rapid=Path(__import__('rapidocr').__file__).parent
baseline=json.loads(Path('/experiment/evidence/native-method.json').read_text())
models={str(p):sha(p) for p in Path(os.environ['HF_HOME']).rglob('*') if p.is_file()};models.update({str(p):sha(p) for p in rapid.rglob('*.onnx')})
missing={k:v for k,v in baseline['model_artifacts'].items() if v not in set(models.values())};assert not missing,missing
env=dict(platform=platform.platform(),python=sys.version,packages={d.metadata['Name']:d.version for d in md.distributions()},models=models,baseline_model_hashes_match=True,baseline_model_count=len(baseline['model_artifacts']),plan_sha256=sha(ROOT/'plan.json'),profiles={})
dump(ROOT/'environment.json',env)
for c in plan['sources']:assert sha(source/c['file'])==c['sha256']
observations=[]
for name,cfg in plan['profiles'].items():
 opts=ThreadedPdfPipelineOptions(do_ocr=cfg['do_ocr'],ocr_options=RapidOcrOptions(backend='onnxruntime',force_full_page_ocr=cfg['force_full_page_ocr']),do_table_structure=True,generate_page_images=False,generate_picture_images=False,images_scale=1,accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU,num_threads=4))
 env['profiles'][name]=opts.model_dump(mode='json');dump(ROOT/'environment.json',env)
 converter=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=opts)})
 for src in plan['sources']:
  cases=[p for p in plan['pages'] if p['source_id']==src['id']];page_range=(min(p['page'] for p in cases),max(p['page'] for p in cases))
  start=time.monotonic();result=converter.convert(source/src['file'],page_range=page_range)
  stem=f'{name}-{src["id"]}';result.document.save_as_json(OUT/(stem+'.json'));result.document.save_as_markdown(OUT/(stem+'.md'))
  for case in cases:
   n=case['page'];txt=result.document.export_to_markdown(page_no=n);(OUT/f'{stem}-p{n}.md').write_text(txt)
   tables=[dict(ref=t.self_ref,rows=t.data.num_rows,cols=t.data.num_cols,cells=len(t.data.table_cells)) for t in result.document.tables if any(p.page_no==n for p in t.prov)]
   row=dict(profile=name,source_id=src['id'],page=n,category=case['category'],status=str(result.status),content=checks(txt,case['content_anchors']),screenshots=checks(txt,case['screenshot_only_anchors']),reading_order=order(txt,case['ordered_anchors']),tables=tables,markdown_characters=len(txt),source_run_seconds=time.monotonic()-start)
   observations.append(row);dump(ROOT/'scores.json',observations)
  print(stem,'complete',flush=True)
engine=RapidOCR();crop_results=[]
for k,crop in enumerate(plan['crop_regions']):
 src=next(x for x in plan['sources'] if x['id']==crop['source_id']);doc=pdfium.PdfDocument(source/src['file']);im=doc[crop['page']-1].render(scale=3).to_pil();im=im.crop(tuple(round(v*3) for v in crop['bbox_points']));path=OUT/f'crop-{k}.png';im.save(path);doc.close();res=engine(str(path));txt='\n'.join(res.txts or []);(OUT/f'crop-{k}.txt').write_text(txt)
 crop_results.append(dict(crop, crop_sha256=sha(path), anchors=checks(txt,crop['anchors']), recognized_lines=0 if res.txts is None else len(res.txts)));dump(ROOT/'crop-scores.json',crop_results)
 print('crop',k,'complete',flush=True)
print('DONE',flush=True)
