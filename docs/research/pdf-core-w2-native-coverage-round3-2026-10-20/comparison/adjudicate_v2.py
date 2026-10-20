"""Expand explicitly page-reviewed V2 source identities; never infer a fix from removal."""
from pathlib import Path
import json,hashlib,collections
ROOT=Path(__file__).resolve().parent.parent
HERE=ROOT/'comparison'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 cases=json.loads((HERE/'V2-official-changed-cases.json').read_text());rules=json.loads((HERE/'V2-semantic-decisions.json').read_text());records=[]
 for c in cases:
  matches=[]
  for r in rules:
   if r['job_id']!=c['job_id'] or r['direction']!=c['direction']:continue
   if r.get('kinds') and c['kind'] not in r['kinds']:continue
   if r.get('anchor_ids') and not set(c['candidate'].get('anchor_ids',[]))&set(r['anchor_ids']):continue
   if r.get('pages') and not set(c['candidate'].get('pages',[]))<=set(r['pages']):continue
   matches.append(r)
  assert len(matches)<=1,(c['identity'],matches)
  if not matches:continue
  r=matches[0];pages=r.get('affected_pages',c['candidate']['pages']);imgs=[str((ROOT/'adjudication/pages'/c['job_id']/f'p{p:03d}.png').resolve()) for p in pages];assert all(Path(x).exists() for x in imgs)
  variant_dir=ROOT/'runs/V2-official/jobs'/c['job_id'];base_dir=Path(json.loads((ROOT/'baseline-inputs.json').read_text())[c['job_id']])
  records.append({'variant':'V2-official','direction':c['direction'],'job_id':c['job_id'],'kind':c['kind'],'identity':c['identity'],'candidate_id':c['candidate']['id'],'anchor_ids':c['candidate'].get('anchor_ids',[]),'pages':c['candidate']['pages'],'affected_pages':pages,'page_images':imgs,'semantic_verdict':r['semantic_verdict'],'source_rootcause_group':r['group_id'],'failure_type':r.get('failure_type','unclassified'),'F01_blocking':r.get('F01_blocking',False),'F02_blocking':r.get('F02_blocking',False),'q4_fixed':r['semantic_verdict']=='CONFIRMED_FIXED','q4_new_bad':r['semantic_verdict']=='CONFIRMED_NEW_BLOCKING','metadata_only':r.get('metadata_only',False),'source_oracle_error':r.get('source_oracle_error',False),'source_reason':r['source_reason'],'baseline_reason':r['baseline_reason'],'variant_reason':r['variant_reason'],'reviewed_visual':True,'reviewed_native_and_markdown':True,'artifact_hashes':{name+':'+file:hashlib.sha256((folder/file).read_bytes()).hexdigest() for name,folder in [('baseline',base_dir),('V2-official',variant_dir)] for file in ['document.json','document.md']}})
 dump(HERE/'V2-semantic-records.json',records)
 groups=[]
 for g in sorted({r['source_rootcause_group'] for r in records}):
  rr=[r for r in records if r['source_rootcause_group']==g];verdicts=sorted(set(r['semantic_verdict'] for r in rr));assert len(verdicts)==1
  groups.append({'source_rootcause_group':g,'job_id':rr[0]['job_id'],'semantic_verdict':verdicts[0],'change_rows':len(rr),'failure_type':rr[0].get('failure_type','unclassified'),'pages':sorted({p for r in rr for p in r['affected_pages']}),'source_reason':rr[0]['source_reason'],'baseline_reason':rr[0]['baseline_reason'],'variant_reason':rr[0]['variant_reason']})
 dump(HERE/'V2-semantic-groups.json',groups);dump(HERE/'V2-semantic-progress.json',{'scope':'Owned original28 papers excluding P07/P08 and recovery6; other agents cover remaining191 rows.','owned_expected_rows':139,'owned_pending_rows':139-len(records),'global_merge_reference':'semantic-summary.json','global_catalog_rows':len(cases),'changed_rows':len(cases),'adjudicated_rows':len(records),'pending_rows':len(cases)-len(records),'pending_rows_definition':'Global catalog rows delegated to the other two agents, not unfinished owned reviews.','row_verdict_counts':dict(collections.Counter(r['semantic_verdict'] for r in records)),'source_group_verdict_counts':dict(collections.Counter(r['semantic_verdict'] for r in groups)),'groups':len(groups),'not_a_whole_variant_pass_claim':True})
if __name__=='__main__':main()
