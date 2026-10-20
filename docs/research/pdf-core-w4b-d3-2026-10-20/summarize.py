from pathlib import Path
from collections import Counter
import csv,hashlib,json,statistics,sys
import importlib.metadata as md
P=Path(__file__).resolve().parent;ROOT=Path.cwd()
def read(p):return json.loads(p.read_text())
def pct(xs,q):
 a=sorted(xs);x=(len(a)-1)*q;i=int(x);return a[i]+(x-i)*(a[min(i+1,len(a)-1)]-a[i])
inputs={r['id']:r for r in read(P/'model-inputs.json')['items']};runtime={};comparisons=[];errors=[];joins=[]
for model in ['d3-nano','d3-mini']:
 metrics=read(P/'evaluation'/model/'metrics.json')['categories'];base=P/'runs'/model/'test';rows=[read(x) for x in base.glob('*.result.json')];sup=read(base/'supervisor.json');load=read(base/'load.json');times=[r['seconds'] for r in rows if r['state']=='OK']
 runtime[model]={'device':sup['device'],'backbone':'bfloat16','readout':'float32','test_completed':len(rows),'test_failed':sum(r['state']!='OK' for r in rows),'all_parameters_on_device':load['all_backbone_and_readout_on_device'],'p50_seconds':statistics.median(times),'p95_seconds':pct(times,.95),'max_seconds':max(times),'forward_seconds_sum':sum(times),'test_wall_seconds_with_load':sup['elapsed_seconds'],'load_seconds':load['seconds'],'sampled_peak_RSS_GiB':sup['max_RSS_bytes']/1024**3,'max_recorded_MPS_allocated_GiB':max(r['mps_allocated_bytes'] for r in rows)/1024**3,'max_recorded_MPS_driver_GiB':max(r['mps_driver_bytes'] for r in rows)/1024**3,'min_host_available_GiB':sup['min_host_available_bytes']/1024**3,'network_attempts':read(base/'summary.json')['network_attempts'],'CPU_fallback':False}
 for cat,d in metrics.items():comparisons.append({'model':model,'category':cat,'test_n':d['test_n'],'question':d['question'],'AUROC':d['AUROC_raw'],'ECE_before':d['ECE_before'],'ECE_after':d['ECE_after'],'verified':d['verified'],'changed_in_verified':d['verified_changed'],'verified_error_rate':d['verified_error_rate'],'coverage':d['coverage'],'threshold':d['threshold'],'p50_seconds':d['latency_seconds']['median'],'p95_seconds':d['latency_seconds']['p95']})
 for r in read(P/'evaluation'/model/'items.json'):
  if r['id'].startswith('W3:'):joins.append({'model':model,'unit_id':r['id'][3:],**{k:r[k] for k in ['category','label','question','raw_safe','calibrated_safe','threshold','gate_state','split_group']}})
  if r['gate_state']=='verified' and r['label']=='meaning_changed':errors.append({**r,'state_input':inputs[r['id']]['state'],'source_images':inputs[r['id']]['images']})
write=lambda name,x:(P/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
write('runtime-summary.json',{'hardware':'Apple M5 Pro48GiB','models':runtime,'notes':['RSS and MPS buffers overlap in unified memory: do not sum.','GPU driver figures are post-forward maxima; parentRSS/available sampled4Hz.','Sequential one process/model/phase; CPUthreads2; no CPU inference fallback.','MPS timing explicitly synchronized before/after system_one.','No production GPU or concurrent-load SLO measured.','Current allocated MPS snapshots do not reflect the full weight footprint; capacity uses RSS and driver memory.','Per-judgement timing excludes outer PIL open/SHA; phase wall includes these and warm-file-cache model loading.'],'dependencies':{n:md.version(n) for n in ['torch','transformers','torchvision','huggingface-hub','numpy','scipy','psutil']}})
write('comparison.json',comparisons);write('false-verified-evidence.json',errors)
for name,data in [('comparison.csv',comparisons),('w3b-test-join.csv',joins)]:
 with (P/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
write('official-GPU-estimate.json',{'source':'Official pinned model cards on AMD Instinct MI325X, AutoModel one new image1.6MP/one question, warm, no network','nano':{'published_p50_ms':90.2,'published_p90_ms':90.7,'ideal_serial_requests_per_second':1000/90.2,'published_AutoModel_peak_GiB':9.1},'mini':{'published_p50_ms':112,'published_p90_ms':113,'ideal_serial_requests_per_second':1000/112,'published_AutoModel_peak_GiB':14.8},'qualification':'Company GPU unknown and not tested. Reciprocal of p50 is a rough serial reference, not a rigorous throughput bound. Document throughput=judgements_per_second/Njudgements_per_document; sharedGPU/batching/IO changes it. Do not substitute318textrequests/s for image throughput.'})
print(json.dumps(runtime,indent=2));print('false verified',Counter((r['question'],r['category']) for r in errors))
