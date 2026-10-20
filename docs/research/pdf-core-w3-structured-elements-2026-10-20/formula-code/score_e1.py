"""E1 assessment on fixed E0 source/item alignment and actual completed batch refs."""
from pathlib import Path
import json,hashlib,collections,importlib.util,copy
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[3];W3=ROOT.parent
spec=importlib.util.spec_from_file_location('scores',ROOT/'scoring.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
mpath=REPO/'docs/research/pdf-core-w2-native-coverage-round4-2026-10-20/mapper/map_documents.py';spec=importlib.util.spec_from_file_location('frozen_mapper',mpath);mapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(mapper)
def read(p):return json.loads(p.read_text())
def resolve(doc,ref):
 try:k,n=ref.split('/')[-2:];return doc[k][int(n)]
 except(KeyError,IndexError,ValueError):return None

def render(doc,folder):
 folder.mkdir(parents=True,exist_ok=True);m=mapper.map_document(doc);html,md=mapper.render(m);s.dump(folder/'mapped.json',m);(folder/'mapped.html').write_text(html);(folder/'mapped.md').write_text(md);return m

def md_presence(text,md):
 n=s.norm(text);return bool(n)and n in s.norm(md)

def delivery(record,doc,rawmd,mapped):
 refs=record['matched_refs'];mi={u['ref']:u for u in mapped['units']};raw=[];mp=[]
 for ref in refs:
  item=resolve(doc,ref)
  if item is None:continue
  txt=item.get('text','');mu=mi.get(ref);raw.append({'ref':ref,'text_nonempty':bool(txt.strip()),'official_md_normalized_text_present':md_presence(txt,rawmd),'native_label':item.get('label')});mp.append({'ref':ref,'rendered_once':mu is not None,'channel':mu.get('channel')if mu else None,'source':mu.get('source')if mu else None,'nonempty':bool(mu and mu['text'].strip())})
 return {'RAW_official_markdown':{'refs':raw,'all_nonempty_active_items_present':bool(raw)and all(x['text_nonempty']and x['official_md_normalized_text_present']for x in raw)},'MAPPED_rendered':{'refs':mp,'all_refs_rendered_once':bool(mp)and all(x['rendered_once']for x in mp),'all_ref_text_nonempty':bool(mp)and all(x['nonempty']for x in mp),'picture_uncertain_refs':[x['ref']for x in mp if x['channel']=='picture_native_uncertain'],'orig_fallback_refs':[x['ref']for x in mp if x['source']=='orig']},'note':'RAW presence uses normalized literal locator only; MAPPED rendered_once is actual saved mapper output with provenance, not semantic equivalence.'}

def completed():
 result={}
 for stage in ['E1_pilot','E1_sampled_v2']:
  fd=W3/'runs'/stage/'jobs'
  if not fd.exists():continue
  for j in fd.iterdir():
   cf=j/'conversion.json'
   if cf.exists()and read(cf).get('status')=='success'and(j/'document.json').exists():result[j.name]=j
 return result

def main():
 oracle=read(ROOT/'oracle.json');byunit={u['id']:u for u in oracle['units']};e0=read(ROOT/'e0-scores.json');e0by={u['unit_id']:u for u in e0};plan=read(W3/'plans/E1_sampled.json');frozen=set(oracle['sampling']['formula_if_cost_over_2hours']+oracle['sampling']['all_code_algorithm']);out=[];inputhashes={};allbase=[];processed_registry={};processed_labels={}
 e0root=REPO/'docs/research/pdf-core-w2-native-coverage-round3-2026-10-20/runs/V3_B/jobs'
 for job,fd in sorted(completed().items()):
  doc=read(fd/'document.json');rawmd=(fd/'document.md').read_text();base=read(e0root/job/'document.json');batches=read(fd/'enrichment-batches.json')if(fd/'enrichment-batches.json').exists()else[];processed={i['ref']for b in batches if'outputs'in b for i in b.get('inputs',[])};processed_registry[job]=sorted(processed);processed_labels[job]=dict(collections.Counter((resolve(doc,ref)or{}).get('label','unknown')for ref in processed))
  mapped=render(doc,ROOT/'E1-mapped'/job);inputhashes[job]={'folder':str(fd),'document_sha256':s.sha((fd/'document.json').read_bytes()),'markdown_sha256':s.sha((fd/'document.md').read_bytes()),'processed_refs':sorted(processed)}
  for old in e0:
   if old['job_id']!=job:continue
   u=byunit[old['unit_id']];r=copy.deepcopy(old);r['variant']='E1';r['fixed_E0_alignment']=True;r['alignment_integrity_issues']=[];items=[]
   for ref in old['matched_refs']:
    before=resolve(base,ref);after=resolve(doc,ref)
    if after is None:r['alignment_integrity_issues'].append({'ref':ref,'reason':'item_missing'});continue
    if before.get('orig')!=after.get('orig')or before.get('prov')!=after.get('prov'):r['alignment_integrity_issues'].append({'ref':ref,'reason':'orig_or_prov_changed_requires_manual_identity_check'})
    items.append(after)
   items=s.ordered_items(doc,items)
   proc=sorted(set(old['matched_refs'])&processed);eligible=old['eligible_enrichment_refs'];r['actual_processed_refs']=proc;r['actual_processed_formula_refs']=[x for x in proc if(resolve(doc,x)or{}).get('label')=='formula'];r['actual_processed_code_refs']=[x for x in proc if(resolve(doc,x)or{}).get('label')=='code'];r['source_in_frozen_sample']=u['id']in frozen
   r['processing_status']='ACTUAL_PROCESSED_ELIGIBLE_ALL'if proc and set(eligible)<=processed else'ACTUAL_PROCESSED_PARTIAL'if proc else'NO_ELIGIBLE_DETECTION'if not eligible else'NOT_SELECTED_OR_NOT_PROCESSED'
   r['native_order_policy']='body_tree_children_picture_caption_refs_deduplicated'
   r['reconstruction_ref_order']=[t['self_ref']for t in items]
   r['native_items']=[{'ref':t['self_ref'],'label':t.get('label'),'parent':t.get('parent'),'pages':sorted(s.page_set(t)),'active_text':t.get('text',''),'orig':t.get('orig',''),'prov':t.get('prov',[])}for t in items]
   expected=s.math_tokens(u['raw'])if u['kind']=='formula'else s.code_tokens(s.text_source(u))
   for channel in ['RAW','MAPPED']:
    text='\n'.join(s.active(t,channel)for t in items);tt=s.math_tokens(text)if u['kind']=='formula'else s.code_tokens(text);score=s.ratio(expected,tt);exact=bool(expected)and expected==tt;status='EXACT_CANONICAL'if exact else'NEAR_CANONICAL'if score>=.75 else'ERROR_OR_MISSING'
    if not r['known_gold_denominator']:status='UNKNOWN_GOLD_SCOPE'
    if r['alignment_integrity_issues']:status='UNKNOWN_ITEM_IDENTITY'
    r['channels'][channel]={'canonical_ratio':score,'status':status,'canonical_exact':exact,'delivered_text':text,'empty':not text.strip(),'orig_fallback_refs':[t['self_ref']for t in items if channel=='MAPPED'and not t.get('text','').strip()and t.get('orig','').strip()],'meaning_preservation':'UNADJUDICATED'}
   r['delivery_modes']=delivery(r,doc,rawmd,mapped);r['markdown_literal_normalized_presence']=md_presence(s.text_source(u)if u['kind']!='formula'else u['raw'],rawmd);out.append(r)
  print(job,'processed',len(processed),flush=True)
 # E0 renderer evidence on all36, once per immutable baseline hash.
 for job in oracle['jobs']:
  j=job['job_id'];fd=e0root/j;doc=read(fd/'document.json');rawmd=(fd/'document.md').read_text();mf=ROOT/'E0-mapped'/j/'mapped.json'
  mapped=read(mf)if mf.exists()else render(doc,mf.parent)
  for old in e0:
   if old['job_id']==j:
    rr=copy.deepcopy(old);u=byunit[old['unit_id']];items=s.ordered_items(doc,[resolve(doc,ref)for ref in old['matched_refs']if resolve(doc,ref)is not None]);expected=s.math_tokens(u['raw'])if u['kind']=='formula'else s.code_tokens(s.text_source(u))
    for channel in ['RAW','MAPPED']:
     text='\n'.join(s.active(t,channel)for t in items);tt=s.math_tokens(text)if u['kind']=='formula'else s.code_tokens(text);score=s.ratio(expected,tt);exact=bool(expected)and expected==tt;status='EXACT_CANONICAL'if exact else'NEAR_CANONICAL'if score>=.75 else'ERROR_OR_MISSING'
     if not rr['known_gold_denominator']:status='UNKNOWN_GOLD_SCOPE'
     rr['channels'][channel]={'canonical_ratio':score,'status':status,'canonical_exact':exact,'delivered_text':text,'empty':not text.strip(),'meaning_preservation':'UNADJUDICATED'}
    rr['reconstruction_ref_order']=[t['self_ref']for t in items];rr['delivery_modes']=delivery(rr,doc,rawmd,mapped);rr['analysis_version']='v2-fixed-refs-body-tree-format-only';allbase.append(rr)
 s.dump(ROOT/'e0-delivery-scores.json',allbase);s.dump(ROOT/'e1-scores.json',out);s.dump(ROOT/'e1-input-hashes.json',inputhashes)
 population=[r for r in out if r['kind']=='formula'and r['known_gold_denominator']and r['source_in_frozen_sample']and r['actual_processed_formula_refs']and r['channels']['MAPPED']['status']in{'NEAR_CANONICAL','ERROR_OR_MISSING'}]
 for r in population:r['audit_hash']=s.sha((SEED+'|audit50|'+r['unit_id']).encode())
 near=sorted([r for r in population if r['channels']['MAPPED']['status']=='NEAR_CANONICAL'],key=lambda r:r['audit_hash']);error=sorted([r for r in population if r['channels']['MAPPED']['status']=='ERROR_OR_MISSING'],key=lambda r:r['audit_hash']);chosen=near[:25]+error[:25];remaining=sorted([r for r in population if r['unit_id']not in{c['unit_id']for c in chosen}],key=lambda r:r['audit_hash']);chosen+=remaining[:max(0,50-len(chosen))]
 s.dump(ROOT/'audit50-current-selection.json',{'protocol_sha256':s.sha((ROOT/'audit-protocol-amendment.json').read_bytes()),'final':False,'completed_jobs':sorted(inputhashes),'population':len(population),'near':len(near),'error':len(error),'selected_count':len(chosen),'selection':[{'unit_id':r['unit_id'],'job_id':r['job_id'],'pages':r['gold_pages'],'hash':r['audit_hash'],'stratum':r['channels']['MAPPED']['status'],'actual_processed_refs':r['actual_processed_formula_refs']}for r in sorted(chosen,key=lambda r:r['audit_hash'])]})
 summary={'analysis_version':'v2-fixed-refs-body-tree-format-only','completed_jobs':len(inputhashes),'jobs':sorted(inputhashes),'source_units_in_completed_jobs':len(out),'actual_processed_native_refs':sum(len(v)for v in processed_registry.values()),'actual_processed_native_refs_by_label':dict(sum((collections.Counter(v)for v in processed_labels.values()),collections.Counter())),'actual_processed_native_label_counts_by_job':processed_labels,'source_units_with_actual_processed_refs':sum(bool(r['actual_processed_refs'])for r in out),'known_source_units_with_actual_processed_refs':sum(r['known_gold_denominator']and bool(r['actual_processed_refs'])for r in out),'alignment_integrity_issues':sum(bool(r['alignment_integrity_issues'])for r in out),'audit50_current_population':len(population),'audit50_current_selected':len(chosen),'by_kind':{k:{'known_actual_processed_source_units':sum(r['kind']==k and r['known_gold_denominator']and bool(r['actual_processed_refs'])for r in out),'RAW':dict(collections.Counter(r['channels']['RAW']['status']for r in out if r['kind']==k and r['known_gold_denominator']and r['actual_processed_refs'])),'MAPPED':dict(collections.Counter(r['channels']['MAPPED']['status']for r in out if r['kind']==k and r['known_gold_denominator']and r['actual_processed_refs']))}for k in['formula','code','algorithm']},'delivery_by_family':[],'no_automatic_Q4_claim':True}
 for variant,rs in [('E0',allbase),('E1',out)]:
  for family in sorted({r['family']for r in rs}):
   rr=[r for r in rs if r['family']==family and r['known_gold_denominator']];summary['delivery_by_family'].append({'variant':variant,'family':family,'known_source_units':len(rr),'official_MD_all_active_items_present_candidates':sum(r['delivery_modes']['RAW_official_markdown']['all_nonempty_active_items_present']for r in rr),'MAPPED_all_refs_rendered_once':sum(r['delivery_modes']['MAPPED_rendered']['all_refs_rendered_once']for r in rr),'MAPPED_all_text_nonempty':sum(r['delivery_modes']['MAPPED_rendered']['all_ref_text_nonempty']for r in rr),'MAPPED_picture_uncertain_source_units':sum(bool(r['delivery_modes']['MAPPED_rendered']['picture_uncertain_refs'])for r in rr),'MAPPED_orig_fallback_source_units':sum(bool(r['delivery_modes']['MAPPED_rendered']['orig_fallback_refs'])for r in rr)})
 s.dump(ROOT/'e1-summary.json',summary);print(json.dumps({k:v for k,v in summary.items()if k!='delivery_by_family'},ensure_ascii=False))
SEED='W3-formula-code-source-v1-20261020'
if __name__=='__main__':main()
