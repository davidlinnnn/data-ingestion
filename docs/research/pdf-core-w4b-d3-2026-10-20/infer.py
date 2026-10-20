"""Official AutoModel/system_one, audited local PIL path; no gold opened."""
import os
from pathlib import Path
P=Path(__file__).resolve().parent
for k,v in {'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','PYTORCH_ENABLE_MPS_FALLBACK':'0','HF_HOME':str(P/'hf-cache'),'HF_MODULES_CACHE':str(P/'hf-cache/modules'),'TMPDIR':str(P/'tmp')}.items():os.environ[k]=v
(P/'tmp').mkdir(exist_ok=True)
import argparse,datetime,hashlib,json,socket,time,traceback,urllib.request
import sys
sys.path.insert(0,str(P/'runtime-deps'))
import psutil,torch
from PIL import Image
from transformers import AutoModel
ROOT=Path.cwd()
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
arg=argparse.ArgumentParser();arg.add_argument('model',choices=['d3-nano','d3-mini']);arg.add_argument('split',choices=['dev','test']);arg.add_argument('--device',default='mps',choices=['mps','cpu']);a=arg.parse_args()
for n,h in read(P/'freeze.json')['files'].items():assert sha(P/n)==h,n
lock=read(P/'official'/(a.model+'-metadata.json'));modeldir=P/'models'/a.model
assert (P/('weights-'+a.model+'.json')).is_file()
for f in ['modeling_d3.py','d3_runtime.py','d3_format.py','d3_fast.py','d3_kernels.py','d3_engine.py','d3_server.py','pipeline_d3.py']:assert sha(modeldir/f)==sha(P/'official'/a.model/f),f
network_attempts=[];connect=socket.socket.connect
# Guard even an unexpected remote-code branch. Local socket operations remain available to trusted frameworks.
def no_connect(sock,address):
 if sock.family in (socket.AF_INET,socket.AF_INET6):network_attempts.append(str(address));raise RuntimeError('NETWORK_FORBIDDEN_IN_INFERENCE')
 return connect(sock,address)
socket.socket.connect=no_connect
def no_url(*args,**kwargs):network_attempts.append('urllib');raise RuntimeError('NETWORK_FORBIDDEN_IN_INFERENCE')
urllib.request.urlopen=no_url
assert a.device!='mps' or torch.backends.mps.is_available()
torch.set_num_threads(2);torch.set_num_interop_threads(1)
if a.device=='mps':torch.mps.set_per_process_memory_fraction(.45)
def sync():
 if a.device=='mps':torch.mps.synchronize()
base=P/'runs'/a.model/a.split;base.mkdir(parents=True,exist_ok=True)
assert not list(base.glob('*.result.json')),'Single execution per model/split; no automatic retry'
write(P/'active.json',{'model':a.model,'split':a.split,'phase':'load','started_monotonic':time.monotonic()})
t=time.monotonic()
try:
 model=AutoModel.from_pretrained(str(modeldir),trust_remote_code=True,revision=lock['sha'],code_revision=lock['sha'],local_files_only=True,device=a.device,batch_size=1,verify='fast')
 sync()
 assert all(x.device.type==a.device for x in model.backbone.parameters())
 assert all(x.dtype==torch.bfloat16 for x in model.backbone.parameters())
 assert model.runtime.readout.device.type==a.device and model.runtime.readout.dtype==torch.float32
 assert model.runtime.image_contract()['supported'],model.runtime.image_contract()
 write(base/'load.json',{'seconds':time.monotonic()-t,'device':a.device,'all_backbone_and_readout_on_device':True,'backbone_dtype':'bfloat16','readout_dtype':'float32','provenance':model.runtime.provenance(),'available_bytes':psutil.virtual_memory().available,'RSS_bytes':psutil.Process().memory_info().rss})
except Exception as e:
 write(base/'load-error.json',{'type':type(e).__name__,'error':str(e),'traceback':traceback.format_exc(),'network_attempts':network_attempts});raise
selection=read(P/'selection'/a.model/'selection.json') if a.split=='test' else None
if selection:
 for n,h in selection['producer_files'].items():assert sha(P/n)==h,n
rows=[r for r in read(P/'model-inputs.json')['items'] if r['split']==a.split];questions=read(P/'questions.json')
for i,r in enumerate(rows):
 if psutil.virtual_memory().available<8*1024**3:write(base/'stop.json',{'reason':'MEMORY_FENCE','remaining':len(rows)-i});break
 assert set(r['state'])=={'category','reconstruction'}
 images=[]
 for im in r['images']:
  f=ROOT/im['path'];assert sha(f)==im['sha256'];images.append(Image.open(f).convert('RGB'))
 chosen=selection['categories'][r['category']]['question'] if selection else None
 qs={chosen:questions[r['category']][chosen]} if chosen else questions[r['category']]
 write(P/'active.json',{'model':a.model,'split':a.split,'phase':'forward','id':r['id'],'started_monotonic':time.monotonic(),'ordinal':i,'total':len(rows)})
 sync();t=time.monotonic();record={'id':r['id'],'category':r['category'],'split':a.split,'device':a.device,'questions':list(qs),'input_image_sizes':[list(im.size) for im in images]}
 try:
  result=model.system_one(state=r['state'],images=images,questions=qs)
  sync();assert result['usage']['output_tokens']==0
  scores={}
  for name in qs:
   ans=result['answers'][name];score=ans['probabilities']['faithful'] if name=='Q1' else ans['noul'];assert 0<=score<=1
   if name=='Q1':assert set(ans['probabilities'])=={'faithful','minor_difference','meaning_changed','cannot_determine'} and abs(sum(ans['probabilities'].values())-1)<1e-5
   scores[name]=score
  assert not network_attempts
  record.update(state='OK',result=result,safe_scores=scores)
 except Exception as e:record.update(state='FAILED',error_type=type(e).__name__,error=str(e),traceback=traceback.format_exc(),network_attempts=network_attempts)
 record.update(seconds=time.monotonic()-t,RSS_bytes=psutil.Process().memory_info().rss,host_available_bytes=psutil.virtual_memory().available,mps_allocated_bytes=torch.mps.current_allocated_memory() if a.device=='mps' else None,mps_driver_bytes=torch.mps.driver_allocated_memory() if a.device=='mps' else None)
 write(base/(hashlib.sha256(r['id'].encode()).hexdigest()+'.result.json'),record)
 print(json.dumps({'model':a.model,'split':a.split,'completed':i+1,'total':len(rows),'state':record['state'],'seconds':round(record['seconds'],3)}),flush=True)
 if record['state']=='FAILED':write(base/'stop.json',{'reason':'RUNTIME_ERROR','id':r['id'],'error_type':record['error_type']});break
 if a.device=='mps':torch.mps.empty_cache()
write(base/'summary.json',{'expected':len(rows),'completed':len(list(base.glob('*.result.json'))),'network_attempts':network_attempts,'remote_inference_calls':0})
write(P/'active.json',{'phase':'done','model':a.model,'split':a.split})
