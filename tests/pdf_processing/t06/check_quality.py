"""Check complete prior-source-reviewed text/type/order through final handoff.

The oracle is from S2 prior to this implementation. This preserves its accepted
source-specific uncertainty, not a claim of literal mathematical correctness.
"""
import hashlib,json
from pathlib import Path
H=lambda text:hashlib.sha256(json.dumps(text,ensure_ascii=False).encode()).hexdigest()
root=Path('/tmp/t06-results');oracle=json.loads(Path('/tmp/quality-oracle.json').read_text());results=[]
for page in oracle['pages']:
 report=json.loads((root/(page['source_id']+'-evidence.json')).read_text())
 items=[]
 for node in report['items']:
  regions=[g for g in node['regions'] if g['page']==page['processed_page']]
  if not regions:continue
  if page['source_id']=='08' and len({g['page'] for g in node['regions']})>1:
   # Non-contiguous source derivatives can induce a cross-page paragraph merge.
   # Use original charspan provenance, never attach the later margin note to prose.
   spans=[g['provenance']['charspan'] for g in regions]
   text=' '.join(node['text'][a:b] for a,b in spans)
   items.append({**node,'text':text,'regions':regions})
  else:items.append(node)
 expected_items=page['items']
 if page['source_id']=='08':
  # Marginalia has no total body reading-order guarantee; compare complete typed
  # page contents, keeping full within-CodeItem sequence and caption checks.
  items=sorted(items,key=lambda x:(x['actual_type'],H(x['text'])))
  expected_items=sorted(expected_items,key=lambda x:(x['type'],x['text_sha256']))
 typed={x['ref']:x for x in report['items']}
 assert len(items)==len(page['items'])
 for actual,expected in zip(items,expected_items):
  assert actual['actual_type']==expected['type'] and H(actual['text'])==expected['text_sha256']
  assert [H(typed[c['$ref']]['text']) for c in actual['captions']]==expected['caption_text_hashes']
  assert len(actual['regions'])==len(expected['boxes'])
  for region,box in zip(actual['regions'],expected['boxes']):
   actual_box=region['provenance']['bbox'];assert actual_box['coord_origin']==box['coord_origin']
   # PDF page import changes size by ~1e-5pt; no text/symbol normalization.
   assert all(abs(actual_box[k]-box[k])<.01 for k in ('l','t','r','b'))
 results.append({'source_id':page['source_id'],'physical_page':page['original_page'],'complete_typed_text_and_caption_match':True,'body_order_checked':page['source_id']=='09','items':len(items)})
# Explicit within-item left->right continuation on ACL original page 3.
r=json.loads((root/'09-evidence.json').read_text());cross=[x for x in r['items'] if len(x['regions'])==2 and x['regions'][0]['page']==2]
assert len(cross)==1
item=cross[0];assert item['regions'][0]['bbox_top_left_points'][0]<300<item['regions'][1]['bbox_top_left_points'][0]
assert item['text'].index('The knowledge distillation loss')<item['text'].index('distillation losses with')
assert r['representation_observations'] # Do not promote unchanged symbol errors to exact source math.
(root/'quality-comparison.json').write_text(json.dumps({'pages':results,'cross_column_continuation':True,'text_normalization':'none','aima_derivative_association':{'status':'unconfirmed','ref':'#/texts/73','original_pages':[87,104],'charspans':[[0,282],[283,301]],'explanation':'Non-contiguous derivative joins later margin note to earlier paragraph; content/provenance retained, association not qualified'}},indent=2))
print('AIMA full typed content/captions passed (order unqualified); ACL full typed content/captions and multi-column order passed',flush=True)
