"""Complete-case discrimination plus whole-cohort coverage; no file/cohort reads on import."""
from collections import Counter
from scipy.stats import beta
GRID=[0,.25,.5,.75,.8,.85,.9,.95,.975,.99,1.0]
def ratio(a,b):return a/b if b else None

def exact_ci(k,n):
    if not n:return None
    return [0.0 if k==0 else float(beta.ppf(.025,k,n-k+1)),1.0 if k==n else float(beta.ppf(.975,k+1,n-k))]

def eligible(r):return bool(r.get('primary_label_eligible')) and isinstance(r.get('human_error'),bool)

def needed(r,rule):
    if rule=='primary':return ['a','b','c'] if r['category']=='formula' else ['a','b'] if r['category']=='code' else []
    req=rule.split('&')
    if r['category']!='formula' and 'c' in req:return []
    return req

def decision(r,rule,threshold=.95):
    req=needed(r,rule)
    if not req:return None
    values=[]
    for key in req:
        f=r.get(key,{})
        if f.get('status')!='KNOWN':return None
        if key in ['a','b']:
            if f.get('character_similarity') is None or not isinstance(f.get('operator_sequence_exact'),bool) or not isinstance(f.get('number_sequence_exact'),bool):return None
            values.append(f['character_similarity']>=threshold and f['operator_sequence_exact'] and f['number_sequence_exact'])
        else:
            if not isinstance(f.get('pass'),bool):return None
            values.append(f['pass'])
    return all(values)

def metrics(rows,rule='primary',threshold=.95):
    decisions=[decision(r,rule,threshold) for r in rows]
    evaluable=[(r,v) for r,v in zip(rows,decisions) if eligible(r) and v is not None]
    tp=sum(r['human_error'] and not v for r,v in evaluable);fp=sum(not r['human_error'] and not v for r,v in evaluable)
    fn=sum(r['human_error'] and v for r,v in evaluable);tn=sum(not r['human_error'] and v for r,v in evaluable)
    all_verified=sum(v is True for v in decisions);known_verified=fn+tn
    label_counts=Counter(str(r.get('human_status')) for r in rows)
    n_eligible=sum(eligible(r) for r in rows)
    return {'rule':rule,'threshold':threshold,'whole_cohort_n':len(rows),'verbatim_human_labels':dict(label_counts),'eligible_known_human_n':n_eligible,'feature_known_n':{k:sum(r.get(k,{}).get('status')=='KNOWN' for r in rows) for k in ['a','b','c']},'feature_unknown_or_NA_n':{k:sum(r.get(k,{}).get('status')!='KNOWN' for r in rows) for k in ['a','b','c']},'evaluable_known_human_n':len(evaluable),'no_decision_whole_n':sum(v is None for v in decisions),'no_decision_known_human_n':sum(eligible(r) and v is None for r,v in zip(rows,decisions)),'verified_all_n':all_verified,'verified_known_human_n':known_verified,'verified_excluded_or_unknown_human_n':all_verified-known_verified,'verified_excluded_or_unknown_labels':dict(Counter(str(r.get('human_status')) for r,v in zip(rows,decisions) if v is True and not eligible(r))),'confusion_error_positive':{'TP':tp,'FP':fp,'FN':fn,'TN':tn},'error_precision':ratio(tp,tp+fp),'error_recall':ratio(tp,tp+fn),'pass_as_correct_precision':ratio(tn,tn+fn),'pass_as_correct_recall':ratio(tn,tn+fp),'verified_error':ratio(fn,known_verified),'verified_error_exact95CI':exact_ci(fn,known_verified),'verified_coverage_whole':ratio(all_verified,len(rows)),'verified_coverage_known_human':ratio(known_verified,n_eligible),'verified_coverage_evaluable_known_human':ratio(known_verified,len(evaluable)),'conditional_metrics_are_not_prevalence_or_calibration':True}

def roc(rows,feature):
    pairs=[]
    for r in rows:
        if not eligible(r):continue
        key,mode=feature.split(':');f=r.get(key,{})
        if f.get('status')!='KNOWN':continue
        if mode=='char':
            if f.get('character_similarity') is None:continue
            risk=1-f['character_similarity']
        elif mode=='op':
            if not isinstance(f.get('operator_sequence_exact'),bool):continue
            risk=float(not f['operator_sequence_exact'])
        elif mode=='num':
            if not isinstance(f.get('number_sequence_exact'),bool):continue
            risk=float(not f['number_sequence_exact'])
        elif mode=='pass':
            if not isinstance(f.get('pass'),bool):continue
            risk=float(not f['pass'])
        else:raise ValueError(mode)
        pairs.append((risk,r['human_error']))
    positives=sum(y for _,y in pairs);negatives=len(pairs)-positives
    if not positives or not negatives:return {'feature':feature,'n':len(pairs),'positive_errors':positives,'negative_correct':negatives,'AUROC':None,'reason':'No evaluable rows or only one human class','points':[]}
    thresholds=[None]+sorted({x for x,_ in pairs},reverse=True);pts=[]
    for t in thresholds:
        tp=0 if t is None else sum(y and x>=t for x,y in pairs);fp=0 if t is None else sum(not y and x>=t for x,y in pairs)
        pts.append({'risk_threshold':t,'TPR':tp/positives,'FPR':fp/negatives})
    area=sum((q['FPR']-p['FPR'])*(q['TPR']+p['TPR'])/2 for p,q in zip(pts,pts[1:]))
    return {'feature':feature,'n':len(pairs),'positive_errors':positives,'negative_correct':negatives,'AUROC':area,'points':pts,'threshold_selection':'All observed thresholds, descriptive only; primary .95 unchanged.'}
