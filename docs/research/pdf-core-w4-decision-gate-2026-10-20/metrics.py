"""Frozen test metrics, no fitting or threshold choice."""
from pathlib import Path
from collections import Counter
import json,math,statistics,hashlib
P=Path(__file__).resolve().parent

def auc(y,score):
    pos=[s for a,s in zip(y,score) if a==1];neg=[s for a,s in zip(y,score) if a==0]
    if not pos or not neg:return None
    return sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg))
def wilson(k,n):
    if n==0:return None
    z=1.959963984540054;p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,c-h),min(1,c+h)]
def percentile(a,q):
    if not a:return None
    a=sorted(a);x=(len(a)-1)*q;i=int(x);j=min(i+1,len(a)-1);return a[i]+(x-i)*(a[j]-a[i])
def binned(rows):
    bins=[]
    for i in range(10):
        rs=[r for r in rows if min(9,int(r['p_faithful']*10))==i]
        bins.append({'lower':i/10,'upper':(i+1)/10,'count':len(rs),'mean_confidence':statistics.mean(r['p_faithful'] for r in rs) if rs else None,'acceptable_fraction':sum(r['label']!='meaning_changed' for r in rs)/len(rs) if rs else None})
    ece=sum(b['count']*abs(b['mean_confidence']-b['acceptable_fraction']) for b in bins if b['count'])/len(rows) if rows else None
    return bins,ece

def calculate(rows):
    ok=[r for r in rows if r['state']=='OK'];strict=[r for r in ok if r['label']!='minor']
    verified=[r for r in ok if r['p_faithful']>=.8];errors=sum(r['label']=='meaning_changed' for r in verified)
    bins,ece=binned(ok)
    curve=[]
    for i in range(21):
        t=i/20;v=[r for r in ok if r['p_faithful']>=t];e=sum(r['label']=='meaning_changed' for r in v)
        curve.append({'threshold':t,'verified':len(v),'meaning_changed':e,'error_rate':e/len(v) if v else None,'coverage':len(v)/len(rows) if rows else None,'error_Wilson95':wilson(e,len(v))})
    return {'eligible_test':len(rows),'valid_probabilities':len(ok),'failed':len(rows)-len(ok),'gold_counts':dict(Counter(r['label'] for r in rows)),'source_page_groups':len(set(r['split_group'] for r in rows)),'AUROC_changed_vs_correct':auc([int(r['label']=='meaning_changed') for r in strict],[r['p_changed'] for r in strict]),'AUROC_counts':dict(Counter(r['label'] for r in strict)),'ECE':ece,'reliability':bins,'verified_threshold':.8,'verified':len(verified),'verified_changed':errors,'verified_error_rate':errors/len(verified) if verified else None,'verified_error_Wilson95':wilson(errors,len(verified)),'verified_coverage':len(verified)/len(rows) if rows else None,'gate_state_counts':dict(Counter(r['gate_state'] for r in rows)),'latency_seconds':{'median':statistics.median(r['seconds'] for r in ok) if ok else None,'p95':percentile([r['seconds'] for r in ok],.95),'max':max([r['seconds'] for r in ok],default=None),'sum':sum(r['seconds'] for r in ok)},'threshold_curve':curve}

def main():
    frozen=json.loads((P/'freeze.json').read_text())
    for n,h in frozen['files'].items():assert hashlib.sha256((P/n).read_bytes()).hexdigest()==h,n
    gold=json.loads((P/'items-with-gold.json').read_text())['items'];joined=[]
    for r in gold:
        if r['split']!='test':continue
        f=P/'predictions-test'/(hashlib.sha256(r['id'].encode()).hexdigest()+'.json')
        d=json.loads(f.read_text()) if f.exists() else {'state':'NOT_RUN'}
        row={'id':r['id'],'category':r['category'],'split_group':r['split_group'],'label':r['label'],'adjudication_evidence':r['adjudication_evidence'],'state':d['state'],'seconds':d.get('seconds')}
        if d['state']=='OK':
            prob=d['result']['probabilities'];pf=prob['faithful'];pw=prob['meaning_changed'];row.update(probabilities=prob,p_faithful=pf,p_changed=pw,gate_state='verified' if pf>=.8 else 'disputed' if pw>=.5 else 'unverified')
        else:row.update(gate_state='failed',runtime_error=d.get('error'))
        joined.append(row)
    cats=sorted(set(r['category'] for r in joined));result={c:calculate([r for r in joined if r['category']==c]) for c in cats}
    (P/'test-item-results.json').write_text(json.dumps(joined,ensure_ascii=False,indent=2)+'\n')
    (P/'test-metrics.json').write_text(json.dumps({'model':'yah01/vjev-vision','split':'test_only','categories':result,'no_threshold_selected':True,'no_calibration_fit':True,'clustered_finite_DEV_source_set':True},indent=2)+'\n')
    # No pooled score, because slice populations, task types and repeated chart images differ.
    print(json.dumps({c:{k:v for k,v in r.items() if k not in ['reliability','threshold_curve']} for c,r in result.items()},indent=2))

if __name__=='__main__':main()
