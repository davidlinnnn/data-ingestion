"""Artifact-only complete typed-graph audit. Literal scores are diagnostics, not thresholds."""
from pathlib import Path
import json,hashlib,difflib
R=Path(__file__).resolve().parent;L=R/'local';norm=lambda x:''.join(x.split());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rows=[]
for case in json.loads((L/'new-source-oracle.json').read_text()):
 stem=f'{case["source_id"]}-{case["page"]}';j=json.loads((L/(stem+'.json')).read_text());h=j['pages'][str(case['page'])]['size']['height'];objects={x['self_ref']:x for k in ('texts','pictures','tables','groups') for x in j.get(k,[])};items=[]
 def visit(x):
  if x.get('prov'):
   p=x['prov'][0];b=p['bbox'];box=[b['l'],h-b['t'],b['r'],h-b['b']] if b['coord_origin']=='BOTTOMLEFT' else [b['l'],b['t'],b['r'],b['b']];items.append(dict(ref=x['self_ref'],type=x['label'],text=x.get('text',''),bbox=box,layer=x.get('content_layer'),captions=x.get('captions',[])))
  for c in x.get('children',[]):visit(objects[c['$ref']])
 visit(j['furniture']);visit(j['body']);regs=[]
 for r in case['regions']:
  def hit(x):
   b=x['bbox'];a=r['bbox'];return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))>0
  selected=[x for x in items if hit(x) and x['text']];a=norm(r['expected_text']);b=norm('\n'.join(x['text'] for x in selected));diff=[dict(op=t,expected=a[i:k],actual=b[v:w]) for t,i,k,v,w in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes() if t!='equal'];(L/f'{stem}-{r["id"]}-graph-diff.json').write_text(json.dumps(diff,ensure_ascii=False,indent=2))
  regs.append(dict(id=r['id'],type=r['type'],expected_sha256=hashlib.sha256(r['expected_text'].encode()).hexdigest(),literal_whitespace_exact=a==b,expected_contained=bool(a) and a in b,overlapping_refs=[x['ref'] for x in selected],difference_blocks=len(diff),note='Overlap can include adjacent regions or cross-column merged paragraphs; differences require source review, not an automatic failure.'))
 (L/f'{stem}-graph-items.json').write_text(json.dumps(items,ensure_ascii=False,indent=2));rows.append(dict(source_id=case['source_id'],physical_page=case['page'],output_sha256=sha(L/(stem+'.json')),regions=regs,typed_item_count=len(items)))
(R/'graph-audit-summary.json').write_text(json.dumps(rows,indent=2))
