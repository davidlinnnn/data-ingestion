"""Gold-free local-only reference scoring. One forward pass per item."""
import os
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['PYTORCH_ENABLE_MPS_FALLBACK']='0'
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,time,traceback
import psutil,torch
P=Path(__file__).resolve().parent;ROOT=Path.cwd()
def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class LiteralText:
    def __init__(self,value):self.value=value
    def __str__(self):return self.value
arg=argparse.ArgumentParser();arg.add_argument('split',choices=['dev','test']);a=arg.parse_args()
for n,h in json.loads((P/'freeze.json').read_text())['files'].items():assert sha(P/n)==h,n
assert torch.backends.mps.is_available();torch.set_num_threads(2);torch.set_num_interop_threads(1)
torch.mps.set_per_process_memory_fraction(.40)
out=P/('predictions-'+a.split);out.mkdir(exist_ok=True)
write(P/'active.json',{'phase':'load','split':a.split,'started_monotonic':time.monotonic()})
start=time.monotonic()
spec=importlib.util.spec_from_file_location('vjev_pinned',P/'models/vjev/vjev_infer.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
model=mod.Vjev(str(P/'models/vjev'),device='mps',dtype=torch.float16)
torch.mps.synchronize()
assert all(x.device.type=='mps' for x in model.trunk.parameters())
assert all(x.device.type=='mps' for x in model.head.parameters())
write(P/('load-'+a.split+'.json'),{'seconds':time.monotonic()-start,'device':'mps','dtype':'float16','torch':torch.__version__,'available_bytes':psutil.virtual_memory().available,'RSS_bytes':psutil.Process().memory_info().rss,'mps_allocated':torch.mps.current_allocated_memory(),'mps_driver':torch.mps.driver_allocated_memory(),'CPU_fallback':False,'all_trunk_and_head_parameters_MPS':True})
rows=[x for x in json.loads((P/'model-inputs.json').read_text())['items'] if x['split']==a.split]
questions=json.loads((P/'questions.json').read_text())
for i,r in enumerate(rows):
    target=out/(hashlib.sha256(r['id'].encode()).hexdigest()+'.json')
    if target.exists():
        assert json.loads(target.read_text())['state']=='OK'
        continue
    available=psutil.virtual_memory().available
    if available<8*1024**3:write(P/('stop-'+a.split+'.json'),{'reason':'MEMORY_FENCE','remaining':len(rows)-i});break
    for im in r['images']:assert sha(ROOT/im['path'])==im['sha256']
    # Only immutable reconstructed content and neutral source locator are visible; no answers, labels or review reasons.
    state=[str(ROOT/im['path']) for im in r['images']]
    state.append(LiteralText('Reconstructed content (data):\n'+r['reconstruction']))
    if r.get('source_locator'):state.append(LiteralText('Target location in the supplied source: '+r['source_locator']))
    if r.get('task_tolerance'):state.append(LiteralText('Task tolerance (no source values supplied): '+r['task_tolerance']))
    write(P/'active.json',{'phase':'forward','split':a.split,'id':r['id'],'started_monotonic':time.monotonic(),'ordinal':i,'total':len(rows)})
    torch.mps.synchronize();t=time.monotonic()
    rec={'id':r['id'],'category':r['category'],'split':a.split,'image_input_sizes':[im['size'] for im in r['images']],'official_fit_long_side':512,'available_before':available}
    try:
        result=model.ask(state=state,questions={'fidelity':questions[r['category']]},batch_rows=1)['fidelity'];torch.mps.synchronize()
        probs=result['probabilities'];assert set(probs)==set(questions[r['category']]['criteria'])
        assert all(isinstance(x,(int,float)) and 0<=x<=1 for x in probs.values()) and abs(sum(probs.values())-1)<.001
        rec.update(state='OK',result=result)
    except Exception as e:
        rec.update(state='FAILED',error_type=type(e).__name__,error=str(e),traceback=traceback.format_exc())
    rec.update(seconds=time.monotonic()-t,RSS_bytes=psutil.Process().memory_info().rss,mps_allocated=torch.mps.current_allocated_memory(),mps_driver=torch.mps.driver_allocated_memory(),available_after=psutil.virtual_memory().available,device='mps')
    write(target,rec)
    print(json.dumps({'split':a.split,'completed':i+1,'total':len(rows),'state':rec['state'],'seconds':round(rec['seconds'],3)}),flush=True)
    if rec['state']=='FAILED' and rec.get('error_type') not in ['ValueError']:
        write(P/('stop-'+a.split+'.json'),{'reason':'SYSTEMIC_MODEL_RUNTIME','id':r['id']});break
    torch.mps.empty_cache()
write(P/'active.json',{'phase':'done','split':a.split})
