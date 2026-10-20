"""Expand explicitly reviewed shared causes into per-candidate adjudication records."""
from pathlib import Path
import json,hashlib,collections,re,unicodedata
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parents[1]/'pdf-core-w2-native-coverage-round2-2026-10-20'
def dump(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def main():
 jobmap=json.loads((ROOT.parent/'baseline-inputs.json').read_text());docs={}
 def normalize(t):return ''.join(ch for ch in unicodedata.normalize('NFKD',t).casefold() if ch.isalnum())
 cat=json.loads((ROOT/'catalog-baseline36.json').read_text());rules=json.loads((ROOT/'decisions.json').read_text());records=[]
 for c in cat:
  if c['kind']=='furniture_in_body':continue
  matched=[]
  for rule in rules:
   if rule['job_id']!=c['job_id']:continue
   if rule.get('kinds') and c['kind'] not in rule['kinds']:continue
   if rule.get('pages') and not set(c.get('pages',[]))<=set(rule['pages']):continue
   if rule.get('anchor_ids') and not set(c.get('anchor_ids',[]))&set(rule['anchor_ids']):continue
   if rule.get('candidate_ids') and c['id'] not in rule['candidate_ids']:continue
   matched.append(rule)
  assert len(matched)<=1,(c['id'],[r['group_id'] for r in matched])
  if not matched:continue
  rule=matched[0];source=[];ars=json.loads((ROOT.parent/'analysis/baseline'/c['job_id']/'anchors.json').read_text());ar={a['anchor_id']:a for a in ars}
  for aid in c.get('anchor_ids',[]):
   a=ar.get(aid)
   if a:source.append({k:a[k] for k in ('anchor_id','text','source_file','source_line','source_offset','pdf_pages')})
  pages=c.get('pages',[]);affected_pages=rule.get('affected_pages',pages);images=[str((ROOT/'pages'/c['job_id']/f'p{p:03d}.png').resolve()) for p in sorted(set(pages+affected_pages))]
  assert all(Path(im).exists() for im in images)
  if c['job_id'] not in docs:docs[c['job_id']]=json.loads((Path(jobmap[c['job_id']])/'document.json').read_text())
  doc=docs[c['job_id']];orig_evidence=[];needles=[normalize(' '.join(re.findall(r'[A-Za-z]+',a['text'])[:5])) for a in source]
  explicit_refs={ref for aid in c.get('anchor_ids',[]) if aid in ar for occ in ar[aid].get('native_all_layers',[]) for ref in occ['itemrefs']}
  for item in doc.get('texts',[]):
   if not any(p['page_no'] in pages for p in item.get('prov',[])):continue
   original=item.get('orig','');matches=[n for n in needles if len(n)>12 and n in normalize(original)]
   empty_formula=(item.get('label')=='formula' and not item.get('text') and original and c['kind']=='missing_anchor')
   if item['self_ref'] in explicit_refs or matches or empty_formula:
    orig_evidence.append({'ref':item['self_ref'],'label':item.get('label'),'text':item.get('text'),'orig':original,'prov':item.get('prov',[]),'selected_by':'same_page_empty_formula_orig' if empty_formula else 'aligned_item_or_source_prefix_in_orig'})
  record={'candidate_id':c['id'],'job_id':c['job_id'],'kind':c['kind'],'pages':pages,'affected_pages':affected_pages,'page_images':images,'shared_evidence_group':rule['group_id'],'status':rule['status'],'q4_blocking':rule['status']=='CONFIRMED_BLOCKING','F01_blocking':rule.get('F01_blocking',False),'F02_blocking':rule.get('F02_blocking',False),'oracle_scope_error':rule.get('oracle_scope_error',False),'actual_formula_loss':rule.get('actual_formula_loss',False),'F13_only':rule.get('F13_only',False),'F13_scope_pending':rule.get('F13_scope_pending',False),'adjudication_scope':'F01/F02 under D3; math candidates retain separate F13 limitations','source_oracle_error':rule.get('source_oracle_error',False),'metadata_only':rule.get('metadata_only',False),'source_reason':rule['source_reason'],'output_reason':rule['output_reason'],'source_anchors':source,'candidate_excerpt':c.get('text') or c.get('item_text'),'native_orig_evidence':orig_evidence,'native_json_vs_markdown':rule.get('native_json_vs_markdown','Both native and Markdown checked; see output reason.'),'reviewed_visual':True,'reviewer':'oracle/adjudication agent; full original page PNG and native/Markdown; shared cause expanded per ID'}
  records.append(record)
 dump(ROOT/'nonfurniture-records.json',records);dump(ROOT/'progress.json',{'catalog_candidates':len(cat),'nonfurniture_total':sum(c['kind']!='furniture_in_body' for c in cat),'nonfurniture_adjudicated':len(records),'counts':dict(collections.Counter(r['status'] for r in records)),'pending_ids':[c['id'] for c in cat if c['kind']!='furniture_in_body' and c['id'] not in {r['candidate_id'] for r in records}]})
if __name__=='__main__':main()
