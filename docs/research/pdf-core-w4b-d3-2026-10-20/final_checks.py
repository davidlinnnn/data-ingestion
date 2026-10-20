"""Read-only closeout checks, no inference or fitting."""
from pathlib import Path
from collections import Counter
import csv,hashlib,importlib.util,json,math
P=Path(__file__).resolve().parent;ROOT=Path.cwd();checks=[]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(n,v):assert v,n;checks.append(n)
s=importlib.util.spec_from_file_location('devcal',P/'calibrate.py');cal=importlib.util.module_from_spec(s);s.loader.exec_module(cal)
f=read(P/'freeze.json');check('pre-inference freeze unchanged',sha(P/'freeze.json')=='336461e7b277447e9a49e9a8fd379c84c405db9214f2d22219f1175454f527b9' and f['model_outputs_seen']==0 and all(sha(P/n)==h for n,h in f['files'].items()))
check('all read W4 evidence unchanged',all(sha(ROOT/n)==h for n,h in read(P/'source-integrity.json').items()))
inputs=read(P/'model-inputs.json')['items'];gold=read(P/'gold.json')['items'];old=read(ROOT/read(P/'gold.json')['source_file'])['items'];g={r['id']:r for r in gold};i={r['id']:r for r in inputs}
check('exact266 items and same81/185 split',len(gold)==len(inputs)==266 and Counter(r['split'] for r in inputs)=={'dev':81,'test':185} and {r['id']:r['split'] for r in old}=={r['id']:r['split'] for r in gold})
check('all labels unchanged',all(g[r['id']]['label']==r['label'] for r in old))
check('state only category+unchanged reconstruction',all(set(r['state'])=={'category','reconstruction'} and r['state']['reconstruction']==next(x['reconstruction'] for x in old if x['id']==r['id']) for r in inputs))
check('all manual locator and per-item answer hints absent',all(not any(k in r for k in ['source_locator','task_tolerance','label','adjudication_evidence','expected']) for r in inputs))
check('two prior hinted items retained on same test split',all(i[x]['split']=='test' and set(i[x]['state'])=={'category','reconstruction'} for x in ['R5:A2-022','R5:A2-026']))
check('input image integrity and area cap',all(sha(ROOT/im['path'])==im['sha256'] and im['supplied_size'][0]*im['supplied_size'][1]<=1600000 for r in inputs for im in r['images']))
check('no shared source group across splits',not {r['split_group'] for r in inputs if r['split']=='dev'}&{r['split_group'] for r in inputs if r['split']=='test'})
models=['d3-nano','d3-mini'];total=0;weightbytes=0
for model in models:
 sel=read(P/'selection'/model/'selection.json');launch=read(P/'selection'/model/'test-launch.json');check(model+' selection frozen before test',sel['test_model_outputs_seen']==0 and launch['test_outputs_seen']==0 and sha(P/'selection'/model/'selection.json')==launch['selection_SHA256'])
 check(model+' producer hashes unchanged',all(sha(P/n)==h for n,h in sel['producer_files'].items()))
 check(model+' dev receipts sealed unchanged',all(sha(P/'runs'/model/'dev'/n)==h for n,h in sel['dev_receipt_hashes'].items()))
 records={}
 for split,n in [('dev',81),('test',185)]:
  base=P/'runs'/model/split;rows=[read(x) for x in base.glob('*.result.json')];records[split]={r['id']:r for r in rows};check(model+' '+split+' complete unique IDs',len(rows)==len(set(r['id'] for r in rows))==n and set(r['id'] for r in rows)=={r['id'] for r in gold if r['split']==split})
  check(model+' '+split+' valid MPS official outputs',all(r['state']=='OK' and r['device']=='mps' and r['result']['usage']['output_tokens']==0 for r in rows))
  check(model+' '+split+' explicit prob not entropy confidence',all(all(abs(r['safe_scores'][q]-(r['result']['answers'][q]['probabilities']['faithful'] if q=='Q1' else r['result']['answers'][q]['noul']))<1e-12 for q in r['questions']) for r in rows))
  check(model+' '+split+' only registered design questions',all(r['questions']==['Q1','Q2'] if split=='dev' else r['questions']==[sel['categories'][r['category']]['question']] for r in rows))
  total+=sum(len(r['questions']) for r in rows)
  sup=read(base/'supervisor.json');check(model+' '+split+' memory+deadline+no network stop',sup['exit_code']==0 and sup['stop'] is None and sup['min_host_available_bytes']>=8*1024**3 and read(base/'summary.json')['network_attempts']==[])
  ld=read(base/'load.json');check(model+' '+split+' fixed BF16/FP32 device numerics',ld['all_backbone_and_readout_on_device'] and ld['backbone_dtype']=='bfloat16' and ld['readout_dtype']=='float32')
 for cat,c in sel['categories'].items():
  binary=[r for r in gold if r['split']=='dev' and r['category']==cat and r['label']!='minor'];aucs={q:cal.auc([int(r['label']=='correct') for r in binary],[records['dev'][r['id']]['safe_scores'][q] for r in binary]) for q in ['Q1','Q2']};q='Q1' if aucs['Q1'] is not None and (aucs['Q2'] is None or aucs['Q1']>aucs['Q2']) else 'Q2';check(model+' '+cat+' question chosen by DEV only',c['question']==q and c['dev_AUROC']==aucs)
  if c['calibrator']['state']=='FIT':
   rs=[r for r in gold if r['split']=='dev' and r['category']==cat];ps=[cal.apply(c['calibrator'],records['dev'][r['id']]['safe_scores'][q]) for r in rs];ys=[int(r['label']!='meaning_changed') for r in rs];expected=cal.threshold(ps,ys);check(model+' '+cat+' DEV max-coverage risk rule',all(c[k]==expected[k] for k in ['threshold','dev_verified','dev_changed','dev_error_rate']))
  else:check(model+' '+cat+' single-class fail closed',cat in ['chart','caption'] and c['threshold'] is None)
 weights=read(P/('weights-'+model+'.json'));weightbytes+=weights['bytes']
 check(model+' pinned revision',weights['revision']==read(P/'official'/(model+'-metadata.json'))['sha'])
 check(model+' all downloaded hashes including readout',all(sha(P/'models'/model/r['file'])==r['sha256'] for r in weights['files']))
 check(model+' audited code identical',all(sha(P/'models'/model/n)==sha(P/'official'/model/n) for n in ['modeling_d3.py','d3_runtime.py','d3_format.py','d3_fast.py','d3_kernels.py','d3_engine.py','d3_server.py','pipeline_d3.py']))
 check(model+' calibrated TEST output traced to frozen selector',all(r['question']==sel['categories'][r['category']]['question'] and r['threshold']==sel['categories'][r['category']]['threshold'] for r in read(P/'evaluation'/model/'items.json')))
check('694 question forwards total no test repeats',total==694)
check('30GB download budget respected, flash absent',weightbytes==13556210856 and weightbytes<30_000_000_000 and not (P/'models/d3-flash').exists())
check('12 statistical controls passed',read(P/'control-results.json')['all_passed'])
check('76 matched W3b TEST join rows',len(list(csv.DictReader((P/'w3b-test-join.csv').open())))==76)
check('visual reviewed real errors no label changes',read(P/'visual-review.json')['no_source_crop_identity_failure_detected'] and not read(P/'visual-review.json')['answers_changed'])
check('baseline untouched outputs recalculated not rerun',read(P/'vjev-comparison-baseline.json')['formula']['published_AUROC_risk_score']==0.7607655502392344)
check('standalone plots and CSV outputs exist',all((P/n).stat().st_size>1000 for n in ['reliability-comparison.png','reliability-comparison.svg','quality-cost.png','quality-cost.svg','comparison.csv']))
(P/'final-check-results.json').write_text(json.dumps({'all_passed':True,'count':len(checks),'checks':checks,'remote_inference_API_calls':0,'question_forwards':total,'model_payload_bytes':weightbytes},indent=2)+'\n');print(json.dumps({'all_passed':True,'count':len(checks),'forwards':total,'bytes':weightbytes}))
