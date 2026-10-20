from pathlib import Path
import json,sys,hashlib,collections
W=Path(__file__).resolve().parents[1];sys.path.insert(0,str(W/'signals'))
from character_helpers import agreement
from statistics_helpers import metrics,roc,GRID
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths=[W/'signals'/n for n in ['cohort-w3-formula.json','cohort-w3-code-utf16-v2.json','cohort-r1-round5-strict.json']];rows=[]
for p in paths:rows+=read(p)['rows']
# Pair source-only, nonempty complete physical glyph sets; no terminal-tag/text-similarity pairing.
def indices(r):
 if not r.get('primary_scope_compatible'):return None
 e=r.get('native_evidence',{});p=e.get('path')
 if e.get('kind')!='ALIGNED_TEXT_LAYER_GLYPHS' or not p:return None
 d=read(Path(p));glyphs=d.get('glyphs',d.get('characters'))
 if glyphs is None:glyphs=[dict(g,page=reg['page']) for reg in d.get('regions',[]) for g in reg.get('glyphs',[])]
 result=frozenset((g.get('page'),i) for g in glyphs if g.get('text','').strip() for i in g.get('raw_char_indices',[g.get('raw_char_index',g.get('raw_index'))]))
 if not result or any(a is None or b is None for a,b in result):return None
 return result
index={r['row_id']:indices(r) for r in rows};pairs=[];overlaps=[]
for i,left in enumerate(rows):
 for right in rows[i+1:]:
  if left.get('model')==right.get('model') or left.get('pdf_sha256')!=right.get('pdf_sha256') or not left.get('pdf_sha256') or left['category']!=right['category']:continue
  a=index[left['row_id']];b=index[right['row_id']]
  if a and b and a&b:overlaps.append({'left':left['row_id'],'right':right['row_id'],'intersection':len(a&b),'left_n':len(a),'right_n':len(b),'fullset_equal':a==b})
  if not a or a!=b:continue
  if any(x.get('copied_native_or_orig_fallback') for r in [left,right] for x in r.get('reconstruction',{}).get('mixed_enrichment_refs',[])):continue
  lt=left.get('reconstruction',{}).get('visible_text');rt=right.get('reconstruction',{}).get('visible_text')
  if lt is None or rt is None:continue
  f=agreement(lt,rt,left['category']);f.update({'paired_row_ids':[right['row_id']],'pairing_provenance':'Independent models, same frozen PDF SHA, identical nonempty original physical visible-character index set AND both full human-unit scope compatible; no terminal-tag pairing.','physical_visible_char_count':len(a),'evidence_paths':[left['native_evidence']['path'],right['native_evidence']['path']]})
  if left['b']['status']=='KNOWN':raise ValueError('multiple independent outputs need predeclared aggregator')
  left['b']=f;right['b']={**f,'paired_row_ids':[left['row_id']]};pairs.append({'left':left['row_id'],'right':right['row_id'],'b':f})
(W/'signals/source-region-pairs.json').write_text(json.dumps({'pairs':pairs,'overlaps_not_pairable':overlaps,'policy':'Exact nonempty physical source index set equality; complete human units only. Same model, orig fallback, local substring of larger block excluded.'},indent=2))
combined={'schema_version':'w3b-signals-cohort-v1','inputs':[{'path':str(p),'sha256':sha(p)} for p in paths],'rows':rows,'pair_count':len(pairs),'notes':['Cohorts are separate purposive/adjudicated strata, not random population samples; no prevalence/calibration claim.','R1 additional obligations may overlap original44; no global accuracy pooling.','Code labels aggregate literal/Q4 faithfulness, not all executable logic.']}
(W/'signals/cohort-combined.json').write_text(json.dumps(combined,ensure_ascii=False,indent=2))
groups={name:[r for r in rows if r['cohort']==name] for name in sorted({r['cohort'] for r in rows})}
# R1_OLD44 contains original mixed mathematical/code semantic groups; category splits descriptive, not new labels.
for category in ['formula','code']:groups['R1_OLD44_'+category]=[r for r in rows if r['cohort']=='R1_OLD44' and r['category']==category]
allstats={}
for name,rs in groups.items():
 rules=['a','b','c','a&b','a&c','b&c','a&b&c','primary'];stats=[metrics(rs,rule) for rule in rules]
 rocs=[roc(rs,f) for f in ['a:char','a:op','a:num','b:char','b:op','b:num','c:pass']]
 allstats[name]={'n':len(rs),'eligible_human_error_n':sum(r.get('primary_label_eligible') and r.get('human_error') is True for r in rs),'eligible_human_preserved_n':sum(r.get('primary_label_eligible') and r.get('human_error') is False for r in rs),'excluded_or_unknown_human_n':sum(not r.get('primary_label_eligible') for r in rs),'prediction_group_n':len({r['prediction_group_id'] for r in rs if r.get('prediction_group_id')}),'prediction_group_missing_n':sum(not r.get('prediction_group_id') for r in rs),'native_available_n':sum(r.get('native_evidence',{}).get('status')=='AVAILABLE' for r in rs),'second_available_n':sum(r['b']['status']=='KNOWN' for r in rs),'render_actual_available_n':sum(bool(r.get('c',{}).get('renderstatus') or r.get('c',{}).get('render_evidence',{}).get('renderstatus')) for r in rs),'metrics':stats,'fixed_threshold_sensitivity':[metrics(rs,'primary',t) for t in GRID],'a_threshold_sensitivity':[metrics(rs,'a',t) for t in GRID],'ROC':rocs,'fixed_rule_binary_ROC':[{'rule':v['rule'],'n':v['evaluable_known_human_n'],'AUROC':((v['error_recall']+(v['confusion_error_positive']['TN']/(v['confusion_error_positive']['TN']+v['confusion_error_positive']['FP'])))/2) if v['error_recall'] is not None and (v['confusion_error_positive']['TN']+v['confusion_error_positive']['FP']) else None,'points':([{'FPR':0,'TPR':0},{'FPR':v['confusion_error_positive']['FP']/(v['confusion_error_positive']['TN']+v['confusion_error_positive']['FP']),'TPR':v['error_recall']},{'FPR':1,'TPR':1}] if v['error_recall'] is not None and (v['confusion_error_positive']['TN']+v['confusion_error_positive']['FP']) else []),'note':'Binary fixed .95 rule; a single operating point plus endpoints, not a tuned continuous ROC or probabilistic calibration.'} for v in stats]}
out={'cohorts':allstats,'paired_source_regions':len(pairs),'scope_and_dependency_notes':combined['notes'],'primary_threshold':.95,'unknown_is_no_decision':True,'statistical_warning':'Exact binomial intervals are conditional descriptive intervals; correlated/overlapping prediction groups violate independent population sampling assumptions. No general deployment calibration guarantee.'}
(W/'signals/metrics.json').write_text(json.dumps(out,indent=2));print('rows',len(rows),'pairs',len(pairs));print(json.dumps([{ 'cohort':k,'n':v['n'],'primary':next(x for x in v['metrics'] if x['rule']=='primary'),'a':next(x for x in v['metrics'] if x['rule']=='a')} for k,v in allstats.items()],indent=2))
