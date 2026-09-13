"""THROWAWAY: exactly four new native pages, from frozen source-only inventory."""
import os,sys,json,hashlib,platform,importlib.metadata as md
from pathlib import Path
R=Path(__file__).resolve().parent;S=Path(sys.argv[1]);P=json.loads((R/'new-plan.json').read_text());O=R/'local';oracle=json.loads((O/'new-source-oracle.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();norm=lambda s:''.join(s.split())
assert sha(O/'new-source-oracle.json')==P['oracle_sha256']
os.environ['HF_HOME']='/experiment/PROTOTYPE-wipe-me/hf';os.environ['HF_HUB_OFFLINE']='1'
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions,RapidOcrOptions
from docling.datamodel.accelerator_options import AcceleratorOptions,AcceleratorDevice
from docling.document_converter import DocumentConverter,PdfFormatOption
import rapidocr
models={str(p):sha(p) for p in Path(os.environ['HF_HOME']).rglob('*') if p.is_file()};models.update({str(p):sha(p) for p in Path(rapidocr.__file__).parent.rglob('*.onnx')});baseline=json.loads(Path('/experiment/evidence/native-method.json').read_text());assert all(v in models.values() for v in baseline['model_artifacts'].values())
opts=ThreadedPdfPipelineOptions(do_ocr=False,do_formula_enrichment=False,ocr_options=RapidOcrOptions(backend='onnxruntime',force_full_page_ocr=False),do_table_structure=True,generate_page_images=True,generate_picture_images=True,images_scale=1,accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU,num_threads=4))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2))
env=dict(platform=platform.platform(),python=sys.version,packages={d.metadata['Name']:d.version for d in md.distributions()},models=models,baseline_models_matched=len(baseline['model_artifacts']),options=opts.model_dump(mode='json'),plan_sha256=sha(R/'new-plan.json'),oracle_sha256=sha(O/'new-source-oracle.json'),producer_sha256=sha(Path(__file__)))
dump(R/'new-environment.json',env);converter=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=opts)});allrows=[]
for case in oracle:
 src=next(x for x in P['sources'] if x['id']==case['source_id']);f=S/src['file'];assert sha(f)==src['sha256'];n=case['page'];stem=f'{src["id"]}-{n}';result=converter.convert(f,page_range=(n,n));doc=result.document;doc.save_as_json(O/(stem+'.json'));doc.save_as_markdown(O/(stem+'.md'));height=doc.pages[n].size.height
 items=[]
 for i,(item,depth) in enumerate(doc.iterate_items()):
  if not item.prov:continue
  prov=next((p for p in item.prov if p.page_no==n),None)
  if prov is None:continue
  b=prov.bbox;b=[b.l,height-b.t,b.r,height-b.b] if str(b.coord_origin)=='BOTTOMLEFT' else [b.l,b.t,b.r,b.b]
  def intersect(a):return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
  reg=max(case['regions'],key=lambda x:intersect(x['bbox']));region=reg['id'] if intersect(reg['bbox']) else None
  items.append(dict(index=i,ref=item.self_ref,type=str(item.label),text=getattr(item,'text',''),bbox=b,region=region,captions=[x.cref for x in getattr(item,'captions',[])]))
 (O/(stem+'-items.json')).write_text(json.dumps(items,ensure_ascii=False,indent=2));regions=[]
 for reg in case['regions']:
  matched=[x for x in items if x['region']==reg['id']];txt='\n'.join(x['text'] for x in matched);regions.append(dict(id=reg['id'],type=reg['type'],source_bbox=reg['bbox'],expected_sha256=hashlib.sha256(reg['expected_text'].encode()).hexdigest(),actual_sha256=hashlib.sha256(txt.encode()).hexdigest(),expected_nonspace=len(norm(reg['expected_text'])),actual_nonspace=len(norm(txt)),exact_whitespace_match=norm(reg['expected_text'])==norm(txt),items=[dict(index=x['index'],ref=x['ref'],type=x['type'],bbox=x['bbox'],captions=x['captions']) for x in matched]));(O/(stem+'-'+reg['id']+'.txt')).write_text(txt)
 edges=[]
 for a,b in P['partial_orders'][f'{src["id"]}:{n}']:
  aa=[x['index'] for x in items if x['region']==a and (x['text'] or x['type']=='formula')];bb=[x['index'] for x in items if x['region']==b and (x['text'] or x['type']=='formula')];edges.append(dict(before=a,after=b,before_indices=aa,after_indices=bb,passed=bool(aa and bb) and max(aa)<min(bb)))
 row=dict(source_id=src['id'],page=n,printed_page=case['printed_page'],status=str(result.status),regions=regions,partial_order=edges,output_sha256=sha(O/(stem+'.json')),page_image_present=doc.pages[n].image is not None,unassigned_item_refs=[x['ref'] for x in items if x['region'] is None]);allrows.append(row);dump(R/'new-results.json',allrows);print(stem,'complete',sum(x['exact_whitespace_match'] for x in regions),'/',len(regions),'order',sum(x['passed'] for x in edges),'/',len(edges),flush=True)
print('DONE',flush=True)
