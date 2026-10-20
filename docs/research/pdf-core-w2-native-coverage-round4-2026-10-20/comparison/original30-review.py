"""Inventory and page-reviewed decision expansion for original30 only; no inference."""
from pathlib import Path
import argparse,json,hashlib,collections
ROOT=Path(__file__).resolve().parent.parent
OLD=ROOT.parent/'pdf-core-w2-native-coverage-round3-2026-10-20'
def read(p):return json.loads(Path(p).read_text())
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def identity(x):return (x['direction'],x['job_id'],json.dumps(x['identity'],sort_keys=True))
def owned_jobs():return set(read(ROOT/'adjudication/original30-baseline-checklist.json')['original30_job_ids'])
def main():
 p=argparse.ArgumentParser();p.add_argument('--changes',required=True);p.add_argument('--decisions');a=p.parse_args();allcases=read(a.changes);owned=[x for x in allcases if x['job_id'] in owned_jobs()]
 assert len({identity(c)for c in owned})==len(owned),'duplicate source identity'
 inv={'scope':'Original30 only; recovery6 excluded','global_catalog_rows':len(allcases),'owned_rows':len(owned),'owned_pages':len({(x['job_id'],p)for x in owned for p in x['candidate'].get('pages',[])}),'input_sha256':hashlib.sha256(Path(a.changes).read_bytes()).hexdigest(),'per_job':[{ 'job_id':j,'rows':sum(x['job_id']==j for x in owned),'pages':sorted({p for x in owned if x['job_id']==j for p in x['candidate'].get('pages',[])})}for j in sorted(owned_jobs())]}
 dump(ROOT/'comparison/original30-inventory.json',inv)
 if not a.decisions:print(json.dumps(inv));return
 decisions=read(a.decisions);by={identity(x):x for x in decisions};assert len(by)==len(decisions)
 extra=set(by)-{identity(c)for c in owned};assert not extra,extra
 for x in decisions:
  assert x['reviewed_visual'] and x['reviewed_native_and_markdown']
  assert x['source_reason'] and x['baseline_reason'] and x['variant_reason'] and x['source_rootcause_group']
  assert x['page_images'] and all(Path(p).exists()for p in x['page_images'])
 dump(ROOT/'comparison/original30-semantic-records.json',decisions)
 dump(ROOT/'comparison/original30-progress.json',dict(inv,adjudicated_rows=len(decisions),pending_rows=len(owned)-len(decisions),complete_identity_coverage=len(owned)==len(decisions),row_verdict_counts=dict(collections.Counter(x['semantic_verdict']for x in decisions))))
 print('owned',len(owned),'reviewed',len(decisions),'pending',len(owned)-len(decisions))
if __name__=='__main__':main()
