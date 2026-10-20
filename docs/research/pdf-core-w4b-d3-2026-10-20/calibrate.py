"""Only DEV outcomes may select questions, fit calibrators and thresholds."""
from pathlib import Path
import hashlib,json,math,sys
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit,logit
P=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def auc(y,s):
 a=[v for k,v in zip(y,s) if k==1];b=[v for k,v in zip(y,s) if k==0]
 return sum((x>z)+.5*(x==z) for x in a for z in b)/(len(a)*len(b)) if a and b else None

def fit(scores,labels):
 if len(set(labels))<2:return {'state':'UNFITTABLE_SINGLE_CLASS','a':None,'b':None}
 x=logit(np.clip(np.array(scores,dtype=float),1e-6,1-1e-6));y=np.array(labels,dtype=float)
 def fn(ab):
  a,b=ab;z=a*x+b;err=expit(z)-y
  return float(np.sum(np.logaddexp(0,z)-y*z)+.5*a*a),np.array([np.dot(err,x)+a,np.sum(err)])
 opt=minimize(fn,[1,float(logit(y.mean()))],jac=True,method='L-BFGS-B',bounds=[(0,None),(None,None)],options={'maxiter':1000,'ftol':1e-12,'gtol':1e-8})
 if not opt.success:return {'state':'FIT_FAILED','message':str(opt.message),'a':None,'b':None}
 return {'state':'FIT','a':float(opt.x[0]),'b':float(opt.x[1]),'objective':float(opt.fun),'n':len(y),'positives':int(y.sum()),'negatives':int(len(y)-y.sum()),'L2_lambda':1,'monotonic_slope_nonnegative':True}

def apply(cal,p):
 if cal['state']!='FIT':return None
 return float(expit(cal['a']*logit(np.clip(p,1e-6,1-1e-6))+cal['b']))

def threshold(probs,labels):
 admissible=[]
 for t in sorted(set(probs)):
  chosen=[y for p,y in zip(probs,labels) if p>=t];bad=sum(y==0 for y in chosen)
  if chosen and bad/len(chosen)<=.02:admissible.append((len(chosen),t,bad))
 if not admissible:return {'threshold':None,'dev_verified':0,'dev_changed':0,'dev_error_rate':None,'reason':'NO_NONEMPTY_DEV_ADMISSIBLE_SET'}
 n,t,bad=max(admissible,key=lambda x:(x[0],x[1]));return {'threshold':t,'dev_verified':n,'dev_changed':bad,'dev_error_rate':bad/n,'reason':'MAX_DEV_COVERAGE_WITH_EMPIRICAL_RISK_LE_2_PERCENT'}

def main():
 model=sys.argv[1];assert model in ('d3-nano','d3-mini')
 base=P/'runs'/model/'dev';out=P/'selection'/model;out.mkdir(parents=True,exist_ok=True);target=out/'selection.json';assert not target.exists()
 gold=json.loads((P/'gold.json').read_text())['items'];items=[r for r in gold if r['split']=='dev'];records={r['id']:r for r in [json.loads(f.read_text()) for f in base.glob('*.result.json')]}
 assert len(records)==81 and set(records)=={r['id'] for r in items}
 result={}
 for c in sorted(set(r['category'] for r in items)):
  rs=[r for r in items if r['category']==c and records[r['id']]['state']=='OK'];binary=[r for r in rs if r['label']!='minor'];aucs={q:auc([int(r['label']=='correct') for r in binary],[records[r['id']]['safe_scores'][q] for r in binary]) for q in ('Q1','Q2')}
  q='Q1' if aucs['Q1'] is not None and (aucs['Q2'] is None or aucs['Q1']>aucs['Q2']) else 'Q2'
  labels=[int(r['label']!='meaning_changed') for r in rs];scores=[records[r['id']]['safe_scores'][q] for r in rs];cal=fit(scores,labels)
  gate=threshold([apply(cal,s) for s in scores],labels) if cal['state']=='FIT' else {'threshold':None,'dev_verified':0,'dev_changed':0,'dev_error_rate':None,'reason':cal['state']}
  result[c]={'question':q,'dev_AUROC':aucs,'dev_n':len(rs),'dev_label_counts':{v:sum(r['label']==v for r in rs) for v in sorted(set(r['label'] for r in rs))},'calibrator':cal,**gate}
 # This script deliberately has no test-input or test-result read path.
 data={'model':model,'categories':result,'test_model_outputs_seen':0,'producer_files':{n:sha(P/n) for n in ['freeze.json','infer.py','supervise.py','calibrate.py','questions.json','protocol.json']},'dev_receipt_hashes':{f.name:sha(f) for f in base.glob('*.result.json')},'no_test_selection':True}
 target.write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data['categories'],indent=2))
if __name__=='__main__':main()
