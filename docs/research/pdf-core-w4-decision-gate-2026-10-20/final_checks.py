"""Offline verification only; never loads or executes model."""
from pathlib import Path
import hashlib,json,csv
from collections import Counter
P=Path(__file__).resolve().parent;ROOT=Path.cwd();checks=[]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(n,v):assert v,n;checks.append(n)
f=read(P/'freeze.json')
check('pre-model freeze SHA',sha(P/'freeze.json')=='a51ca0bb1f17897b4ff61f81e9b3eaa554800a5edfba9c36a3bb2d58f3971e6d')
check('all pre-model frozen inputs unchanged',all(sha(P/n)==h for n,h in f['files'].items()))
g=read(P/'test-gate.json')
check('test gate and producers unchanged',g['passed'] and g['test_model_outputs_seen']==0 and all(sha(P/n)==h for n,h in g['files'].items()))
check('all read upstream JSON files unchanged',all(sha(ROOT/n)==h for n,h in read(P/'source-integrity.json').items()))
items=read(P/'items-with-gold.json')['items'];inputs=read(P/'model-inputs.json')['items']
check('266 unique eligible items',len(items)==len(set(r['id'] for r in items))==266)
check('model input omits label/expected fields; no-hints not implied',len(inputs)==266 and all('label' not in r and 'adjudication_evidence' not in r and 'expected' not in r for r in inputs))
check('split counts81/185',Counter(r['split'] for r in items)=={'dev':81,'test':185})
check('no source-page split group leakage',not {r['split_group'] for r in items if r['split']=='dev'}&{r['split_group'] for r in items if r['split']=='test'})
images={im['path']:im['sha256'] for r in inputs for im in r['images']}
check('all supplied source images unchanged',all(sha(ROOT/n)==h for n,h in images.items()))
check('71 W3 human-packet identities unchanged',read(P/'W3-adjudication-integrity.json')['all_supplied_checks_passed'] and len(read(P/'W3-adjudication-integrity.json')['records'])==71)
check('cross-render page screen no matches',not read(P/'cross-render-page-audit.json')['matches'])
for split,n in [('dev',81),('test',185)]:
 rows=[read(x) for x in (P/('predictions-'+split)).glob('*.json')]
 check(split+' complete once per id',len(rows)==n and len(set(x['id'] for x in rows))==n and set(x['id'] for x in rows)=={x['id'] for x in items if x['split']==split})
 check(split+' probability shapes valid',all(x['state']=='OK' and set(x['result']['probabilities'])=={'faithful','minor_difference','meaning_changed','cannot_determine'} and all(0<=v<=1 for v in x['result']['probabilities'].values()) and abs(sum(x['result']['probabilities'].values())-1)<.001 for x in rows))
 check(split+' MPS outputs',all(x['device']=='mps' for x in rows))
 sup=read(P/('supervisor-'+split+'.json'))
 check(split+' memory and wall supervisor no stop',sup['stop'] is None and sup['exit_code']==0 and sup['min_host_available_bytes']>=8*1024**3)
check('model all parameters MPS no CPU fallback',read(P/'load-test.json')['all_trunk_and_head_parameters_MPS'] and not read(P/'runtime-summary.json')['CPU_fallback'])
metric=read(P/'test-metrics.json')['categories']
check('all five categories represented',set(metric)=={'formula','code','caption','description','chart'})
check('verified empty is undefined risk, not zero',all(r['verified']==0 and r['verified_error_rate'] is None and r['verified_coverage']==0 for r in metric.values()))
check('fixed 21 thresholds and0.8 boundary',all(len(r['threshold_curve'])==21 and r['threshold_curve'][16]['threshold']==.8 and r['verified_threshold']==.8 for r in metric.values()))
check('caption single class AUROC undefined',metric['caption']['AUROC_changed_vs_correct'] is None)
check('source subgroup code confounding disclosed',read(P/'test-source-subgroups.json')['code:W3:']['gold_counts']=={'meaning_changed':3} and read(P/'test-source-subgroups.json')['code:R5:']['gold_counts']=={'correct':25})
joined=read(P/'test-item-results.json');check('all185 test outcomes remain unverified',len(joined)==185 and all(r['split_group'] in {i['split_group'] for i in items if i['split']=='test'} and r['gate_state']=='unverified' for r in joined))
check('38 eligible W3b test join rows',len(list(csv.DictReader((P/'w3b-test-join.csv').open())))==38)
check('both exported plots and curves exist',all((P/n).stat().st_size>1000 for n in ['reliability.svg','reliability.png','threshold-curves.svg','threshold-curves.png','threshold-curves.csv']))
# Weights were compared with publisher SHA before inference; verify actual bytes again at closeout.
weights=read(P/'weights-integrity.json')
for r in weights['files']:
    check('pinned model file '+r['file'],sha(P/'models/vjev'/r['file'])==r['sha256'])
check('downloaded model under40GB',weights['bytes_total']<40_000_000_000 and not (P/'models/jev-omni').exists())
check('two oracle-assisted test locators transparently retained',len(read(P/'input-hint-audit.json')['affected_test_items'])==2 and read(P/'input-hint-audit.json')['no_prompt_changes_or_rerun'])
result={'all_passed':True,'checks':checks,'count':len(checks),'unique_input_images_verified':len(images),'source_files_verified':len(read(P/'source-integrity.json')),'remote_inference_calls':0}
(P/'final-check-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
