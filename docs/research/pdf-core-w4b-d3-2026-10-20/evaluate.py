"""Frozen DEV selection -> one TEST evaluation; never alters thresholds."""
from pathlib import Path
from collections import Counter
import hashlib,json,math,statistics,sys
import importlib.util
P=Path(__file__).resolve().parent;ROOT=Path.cwd()
s=importlib.util.spec_from_file_location('devcal',P/'calibrate.py');cal=importlib.util.module_from_spec(s);s.loader.exec_module(cal)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def wilson(k,n):
 if not n:return None
 z=1.959963984540054;p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;return [max(0,c-h),min(1,c+h)]
def bins(rows,field):
 rows=[r for r in rows if r.get(field) is not None];out=[]
 for i in range(10):
  rs=[r for r in rows if min(9,int(r[field]*10))==i]
  out.append({'lower':i/10,'upper':(i+1)/10,'n':len(rs),'mean_probability':statistics.mean(r[field] for r in rs) if rs else None,'meaning_preserved':sum(r['label']!='meaning_changed' for r in rs)/len(rs) if rs else None})
 return out,sum(b['n']*abs(b['mean_probability']-b['meaning_preserved']) for b in out if b['n'])/len(rows) if rows else None

def percentile(xs,q):
 if not xs:return None
 xs=sorted(xs);x=(len(xs)-1)*q;i=int(x);return xs[i]+(x-i)*(xs[min(i+1,len(xs)-1)]-xs[i])
def summarize(rows):
 ok=[r for r in rows if r['state']=='OK'];binary=[r for r in ok if r['label']!='minor'];verified=[r for r in ok if r['gate_state']=='verified'];bad=sum(r['label']=='meaning_changed' for r in verified);before,eb=bins(ok,'raw_safe');after,ea=bins(ok,'calibrated_safe');times=[r['seconds'] for r in ok]
 return {'test_n':len(rows),'valid':len(ok),'failed_or_NOT_RUN':len(rows)-len(ok),'label_counts':dict(Counter(r['label'] for r in rows)),'source_page_groups':len(set(r['split_group'] for r in rows)),'AUROC_raw':cal.auc([int(r['label']=='correct') for r in binary],[r['raw_safe'] for r in binary]),'AUROC_calibrated':cal.auc([int(r['label']=='correct') for r in binary],[r['calibrated_safe'] for r in binary]) if binary and all(r.get('calibrated_safe') is not None for r in binary) else None,'ECE_before':eb,'ECE_after':ea,'reliability_before':before,'reliability_after':after,'verified':len(verified),'verified_changed':bad,'verified_error_rate':bad/len(verified) if verified else None,'verified_error_Wilson95':wilson(bad,len(verified)),'coverage':len(verified)/len(rows) if rows else None,'status_counts':dict(Counter(r['gate_state'] for r in rows)),'latency_seconds':{'median':statistics.median(times) if times else None,'p95':percentile(times,.95),'max':max(times) if times else None,'sum':sum(times)}}

def baseline():
 w=ROOT/'docs/research/pdf-core-w4-decision-gate-2026-10-20';old=read(w/'test-item-results.json');published=read(w/'test-metrics.json')['categories'];out={}
 for c in sorted(set(r['category'] for r in old)):
  rs=[r for r in old if r['category']==c and r['label']!='minor'];out[c]={'published_AUROC_risk_score':published[c]['AUROC_changed_vs_correct'],'harmonized_AUROC_faithful_score':cal.auc([int(r['label']=='correct') for r in rs],[r['p_faithful'] for r in rs]),'ECE_uncalibrated':published[c]['ECE'],'verified_fixed_threshold':.8,'verified':0,'coverage':0,'verified_error_rate':None,'test_n':published[c]['eligible_test'],'note':'Saved W4 outputs only; old two numeric locators and512px preprocessing remain baseline limitations. No refit/rerun.'}
 (P/'vjev-comparison-baseline.json').write_text(json.dumps(out,indent=2)+'\n')
 return out

def main():
 model=sys.argv[1];base=P/'runs'/model/'test';selection=read(P/'selection'/model/'selection.json');launch=read(P/'selection'/model/'test-launch.json');assert sha(P/'selection'/model/'selection.json')==launch['selection_SHA256']
 for n,h in read(P/'freeze.json')['files'].items():assert sha(P/n)==h,n
 gold=[r for r in read(P/'gold.json')['items'] if r['split']=='test'];records={r['id']:r for r in [read(x) for x in base.glob('*.result.json')]};assert set(records)<=set(r['id'] for r in gold);joined=[]
 for r in gold:
  d=records.get(r['id'],{'state':'NOT_RUN'});spec=selection['categories'][r['category']];row={**r,'state':d['state'],'question':spec['question'],'seconds':d.get('seconds'),'raw_safe':None,'calibrated_safe':None,'threshold':spec['threshold']}
  if d['state']=='OK':
   assert d['questions']==[spec['question']];raw=d['safe_scores'][spec['question']];pc=cal.apply(spec['calibrator'],raw);t=spec['threshold'];status='verified' if pc is not None and t is not None and pc>=t else 'disputed' if raw<.5 else 'unverified';row.update(raw_safe=raw,calibrated_safe=pc,gate_state=status)
  else:row.update(gate_state='failed',error=d.get('error'))
  joined.append(row)
 result={}
 for category,spec in selection['categories'].items():result[category]={**summarize([r for r in joined if r['category']==category]),'question':spec['question'],'dev_AUROC':spec['dev_AUROC'],'dev_verified':spec['dev_verified'],'dev_error_rate':spec['dev_error_rate'],'threshold':spec['threshold'],'calibration_state':spec['calibrator']['state']}
 out=P/'evaluation'/model;out.mkdir(parents=True,exist_ok=True)
 (out/'items.json').write_text(json.dumps(joined,ensure_ascii=False,indent=2)+'\n');(out/'metrics.json').write_text(json.dumps({'model':model,'categories':result,'test_inputs':185,'selection_SHA256':sha(P/'selection'/model/'selection.json'),'no_test_threshold_selection':True},indent=2)+'\n')
 sub={}
 for cat in ['formula','code']:
  for origin in ['W3:','R5:']:sub[cat+origin]=summarize([r for r in joined if r['category']==cat and r['id'].startswith(origin)])
 (out/'source-subgroups.json').write_text(json.dumps(sub,indent=2)+'\n');baseline()
 print(json.dumps({c:{k:v for k,v in d.items() if not k.startswith('reliability')} for c,d in result.items()},indent=2))
if __name__=='__main__':main()
