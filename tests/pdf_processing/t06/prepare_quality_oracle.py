"""Freeze hashes of the *prior source-audited S2* graph, not this implementation.

No source text/images are copied into version control. Full unchanged text hashes
include symbol differences already given source-specific disposition by S2.
"""
import hashlib,json
from pathlib import Path
S2=Path('/Users/david/work/data-ingestion/.scratch/worktrees/pdf-s2-profile-quality/docs/prototypes/pdf-profile-quality-spike')
H=lambda b:hashlib.sha256(b).hexdigest()
result={'origin_commit':'7b3d5ac7a3515758956c10dd1f67a0895e98f7d1','scope':'prior S2 source-reviewed typed content/order; not a fresh source transcript','pages':[]}
for sid,pages,folder in [('08',[86,87,104],'native-2026-09-13/local'),('09',[2,3,4],'bounded-validation-2026-09-13/local')]:
 for processed,page in enumerate(pages,1):
  path=S2/folder/f'{sid}-{page}.json';doc=json.loads(path.read_text());idx={x['self_ref']:x for k in ('texts','pictures','tables','groups') for x in doc.get(k,[])};items=[]
  def visit(node):
   if node.get('prov'):
    items.append({'type':node['label'],'text_sha256':H(json.dumps(node.get('text'),ensure_ascii=False).encode()),
      'boxes':[p['bbox'] for p in node['prov']],
      'caption_text_hashes':[H(json.dumps(idx[c['$ref']].get('text'),ensure_ascii=False).encode()) for c in node.get('captions',[])]})
   for child in node.get('children',[]):visit(idx[child['$ref']])
  visit(doc['body']);visit(doc['furniture'])
  result['pages'].append({'source_id':sid,'processed_page':processed,'original_page':page,'prior_artifact_sha256':H(path.read_bytes()),'items':items})
Path(__file__).with_name('quality-oracle.json').write_text(json.dumps(result,indent=2))
