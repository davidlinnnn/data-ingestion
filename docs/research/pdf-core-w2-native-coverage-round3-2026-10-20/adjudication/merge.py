"""Merge disjoint manual review work; missing IDs fail instead of becoming clean."""
from pathlib import Path
import argparse,collections,hashlib,json
ROOT=Path(__file__).resolve().parent

def read(p):return json.loads(p.read_text())
def dump(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--old30',action='store_true');args=parser.parse_args()
 cat=read(ROOT/('catalog-v3.json' if args.old30 else 'catalog-baseline36.json'))
 paths=[ROOT/'nonfurniture-records.json',ROOT/'furniture/records-old335.json']
 if not args.old30:paths += [ROOT/'recovery-records.json',ROOT/'furniture/records-new126.json']
 records=[r for path in paths for r in read(path)];expected={c['id'] for c in cat};ids=[r['candidate_id'] for r in records]
 assert len(ids)==len(set(ids)), 'duplicate review IDs'
 assert set(ids)==expected,{'missing':sorted(expected-set(ids)),'unexpected':sorted(set(ids)-expected)}
 for r in records:
  assert r['status'] in {'CONFIRMED_BLOCKING','CLEAN_AFTER_ADJUDICATION','UNKNOWN'}
  assert r['source_reason'] and r['output_reason'] and r['pages']
  assert r.get('reviewed_visual'),r['candidate_id']
  assert r['page_images'] and all(Path(p).exists() for p in r['page_images']),r['candidate_id']
 summaries=read(ROOT.parent/'analysis/baseline/summary.json');old_job_ids={r['job_id'] for r in records}
 if args.old30:
  inputs=read(ROOT.parent/'baseline-inputs.json');summaries=[s for s in summaries if 'round2' in inputs[s['id']]]
 papers=[]
 for s in summaries:
  rr=[r for r in records if r['job_id']==s['id']];cc=[c for c in cat if c['job_id']==s['id']];assert len(rr)==len(cc)
  blocking=[r for r in rr if r['status']=='CONFIRMED_BLOCKING'];unknown=[r for r in rr if r['status']=='UNKNOWN'];no_oracle=not s.get('trusted_prose')
  status='CONFIRMED_BLOCKING' if blocking else 'UNKNOWN' if unknown or no_oracle or s.get('metric_status')!='SCORED_CANDIDATES' else 'CLEAN_AFTER_ADJUDICATION'
  papers.append({'job_id':s['id'],'set':s['set'],'family':s['family'],'pages':s['selected_pages'],'candidate_count':len(cc),'adjudicated_count':len(rr),'status':status,'F01_blocking':any(r.get('F01_blocking',r.get('q4_blocking',False)) for r in blocking),'F02_blocking':any(r.get('F02_blocking',False) for r in blocking),'confirmed_candidate_ids':[r['candidate_id'] for r in blocking],'unknown_candidate_ids':[r['candidate_id'] for r in unknown],'confirmed_source_groups':sorted({r.get('shared_evidence_group',r.get('root_cause_group',r['candidate_id'])) for r in blocking}),'confirmed_affected_pages':sorted({pg for r in blocking for pg in r.get('affected_pages',r['pages'])}),'confirmed_source_candidate_pages':sorted({pg for r in blocking for pg in r['pages']}),'trusted_prose_anchors':s.get('trusted_prose'),'scope':'All generated baseline F01/F02 candidates adjudicated. CLEAN means no blocking issue among these candidates; sparse anchors do not establish full-document word-for-word semantic equivalence. Heading and mathematical-quality risks are separate.'})
 suffix='-old30' if args.old30 else ''
 generated_status_counts={status:sum(p['status']==status for p in papers) for status in ['CONFIRMED_BLOCKING','CLEAN_AFTER_ADJUDICATION','UNKNOWN']}
 incidental=read(ROOT/'incidental-outside-oracle.json') if not args.old30 and (ROOT/'incidental-outside-oracle.json').exists() else []
 for event in incidental:
  assert event['outside_frozen_candidate_catalog'] and event['reviewed_visual'] and event['status']=='CONFIRMED_BLOCKING'
  paper=next(p for p in papers if p['job_id']==event['job_id']);paper['status']='CONFIRMED_BLOCKING';paper['F01_blocking']|=event.get('F01_blocking',False);paper['F02_blocking']|=event.get('F02_blocking',False);paper['confirmed_affected_pages']=sorted(set(paper['confirmed_affected_pages']+event.get('affected_pages',event['pages'])));paper['confirmed_source_groups']=sorted(set(paper['confirmed_source_groups']+[event['shared_evidence_group']]));paper.setdefault('outside_oracle_confirmed_events',[]).append(event['event_id'])
 groups=[]
 for group in sorted({r.get('shared_evidence_group',r.get('root_cause_group',r['candidate_id'])) for r in records if r['status']=='CONFIRMED_BLOCKING'}):
  rr=[r for r in records if r['status']=='CONFIRMED_BLOCKING' and r.get('shared_evidence_group',r.get('root_cause_group',r['candidate_id']))==group]
  groups.append({'group_id':group,'job_id':rr[0]['job_id'],'candidate_ids':[r['candidate_id'] for r in rr],'candidate_count':len(rr),'source_anchor_ids':sorted({a['anchor_id'] for r in rr for a in r.get('source_anchors',[])}),'source_candidate_pages':sorted({pg for r in rr for pg in r['pages']}),'confirmed_affected_pages':sorted({pg for r in rr for pg in r.get('affected_pages',r['pages'])}),'source_reason':rr[0]['source_reason'],'output_reason':rr[0]['output_reason'],'page_images':sorted({im for r in rr for im in r['page_images']}),'counting_note':'One shared source root cause; multiple metric alerts/anchor witnesses are not independent defect events. A group is fixed only if all necessary source instances are resolved; otherwise report partial improvement.'})
 for event in incidental:
  groups.append({'group_id':event['shared_evidence_group'],'event_id':event['event_id'],'job_id':event['job_id'],'candidate_ids':[],'candidate_count':0,'source_anchor_ids':[],'source_candidate_pages':[],'confirmed_affected_pages':event.get('affected_pages',event['pages']),'source_reason':event['source_reason'],'output_reason':event['output_reason'],'page_images':event['page_images'],'outside_frozen_candidate_catalog':True,'counting_note':'Incidental original-page finding outside the frozen generated candidate set; do not add a candidate or change oracle denominators.'})
 family=[]
 for name in sorted({p['family'] for p in papers}):
  pp=[p for p in papers if p['family']==name];family.append({'family':name,'papers':len(pp),'pages':sum(p['pages'] for p in pp),'candidates':sum(p['candidate_count'] for p in pp),'status_counts':dict(collections.Counter(p['status'] for p in pp)),'F01_blocking_papers':sum(p['F01_blocking'] for p in pp),'F02_blocking_papers':sum(p['F02_blocking'] for p in pp),'confirmed_affected_job_pages':sum(len(p['confirmed_affected_pages']) for p in pp)})
 summary={'papers':len(papers),'selected_pages':sum(p['pages'] for p in papers),'candidates':len(records),'candidate_alert_job_pages':len({(x['job_id'],p) for x in records for p in x['pages']}),'confirmed_source_candidate_job_pages':sum(len(p['confirmed_source_candidate_pages']) for p in papers),'candidate_coverage_complete':True,'generated_candidate_only_status_counts':generated_status_counts,'incidental_outside_oracle_count':len(incidental),'status_counts':{status:sum(p['status']==status for p in papers) for status in ['CONFIRMED_BLOCKING','CLEAN_AFTER_ADJUDICATION','UNKNOWN']},'confirmed_source_root_group_count':len(groups),'confirmed_affected_job_pages':sum(len(p['confirmed_affected_pages']) for p in papers),'candidate_status_counts':dict(collections.Counter(r['status'] for r in records)),'F01_blocking_papers':sum(p['F01_blocking'] for p in papers),'F02_blocking_papers':sum(p['F02_blocking'] for p in papers),'confirmed_source_groups':sorted({g for p in papers for g in p['confirmed_source_groups']}),'input_records_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'catalog_sha256':hashlib.sha256((ROOT/('catalog-v3.json' if args.old30 else 'catalog-baseline36.json')).read_bytes()).hexdigest(),'definition':'Paper class uses blocking > unresolved/unknown > clean after all candidate adjudications. No arbitrary pass rate.'}
 dump(ROOT/('root-groups'+suffix+'.json'),groups);dump(ROOT/('families'+suffix+'.json'),family)
 dump(ROOT/('records'+suffix+'.json'),records);dump(ROOT/('papers'+suffix+'.json'),papers);dump(ROOT/('summary'+suffix+'.json'),summary)
 print(json.dumps({k:v for k,v in summary.items() if k not in ('input_records_sha256','confirmed_source_groups')},ensure_ascii=False))
if __name__=='__main__':main()
