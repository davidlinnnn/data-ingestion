"""Artifact-only correction of coordinate scorer; no recognition."""
from pathlib import Path
import json,hashlib
from docling_core.types.doc import DoclingDocument
R=Path(__file__).resolve().parent;P=json.loads((R/'new-plan.json').read_text());O=R/'local';oracle=json.loads((O/'new-source-oracle.json').read_text());norm=lambda x:''.join(x.split());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rows=[]
for case in oracle:
 stem=f'{case["source_id"]}-{case["page"]}';n=case['page'];doc=DoclingDocument.load_from_json(O/(stem+'.json'));height=doc.pages[n].size.height;items=[]
 for i,(item,depth) in enumerate(doc.iterate_items()):
  prov=next((p for p in item.prov if p.page_no==n),None)
  if prov is None:continue
  b=prov.bbox.model_dump(mode='json');b=[b['l'],height-b['t'],b['r'],height-b['b']] if b['coord_origin']=='BOTTOMLEFT' else [b['l'],b['t'],b['r'],b['b']]
  def intersect(a):return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
  reg=max(case['regions'],key=lambda x:intersect(x['bbox']));region=reg['id'] if intersect(reg['bbox']) else None
  items.append(dict(index=i,ref=item.self_ref,type=str(item.label),text=getattr(item,'text',''),bbox=b,region=region,captions=[x.cref for x in getattr(item,'captions',[])]))
 (O/(stem+'-items-corrected.json')).write_text(json.dumps(items,ensure_ascii=False,indent=2));regs=[]
 for reg in case['regions']:
  a=[x for x in items if x['region']==reg['id']];txt='\n'.join(x['text'] for x in a);(O/(stem+'-'+reg['id']+'-corrected.txt')).write_text(txt);regs.append(dict(id=reg['id'],type=reg['type'],expected_nonspace=len(norm(reg['expected_text'])),actual_nonspace=len(norm(txt)),exact_whitespace_match=norm(reg['expected_text'])==norm(txt),items=[{k:v for k,v in x.items() if k!='text'} for x in a]))
 edges=[]
 for a,b in P['partial_orders'][f'{case["source_id"]}:{n}']:
  aa=[x['index'] for x in items if x['region']==a and (x['text'] or x['type']=='formula')];bb=[x['index'] for x in items if x['region']==b and (x['text'] or x['type']=='formula')];edges.append(dict(before=a,after=b,before_indices=aa,after_indices=bb,passed=bool(aa and bb) and max(aa)<min(bb)))
 rows.append(dict(source_id=case['source_id'],page=n,regions=regs,partial_order=edges,output_sha256=sha(O/(stem+'.json')),page_image_present=doc.pages[n].image is not None,unassigned_item_refs=[x['ref'] for x in items if x['region'] is None]));print(stem,'text',sum(x['exact_whitespace_match'] for x in regs),'/',len(regs),'order',sum(x['passed'] for x in edges),'/',len(edges))
(R/'corrected-new-results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
