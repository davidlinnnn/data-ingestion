import json,subprocess,time
from pathlib import Path
OUT=Path('/private/tmp/q44-object-limit-cl');OUT.mkdir(exist_ok=False)
prior=json.loads(Path('/private/tmp/q44-object-idle-ck/summary.json').read_text());base=json.loads(Path('/private/tmp/q44-object-reclaim-ci/summary.json').read_text());path=base['before']['cgroup'];node='internal-a2a-vs6-local-worker2'
program="""from pathlib import Path
import json,time,sys
p=Path(sys.argv[1]);s=dict(l.split() for l in (p/'memory.stat').read_text().splitlines());e=dict(l.split() for l in (p/'memory.events').read_text().splitlines());full=next(l for l in (p/'memory.pressure').read_text().splitlines() if l.startswith('full '))
print(json.dumps({'time':time.time(),'current':int((p/'memory.current').read_text()),'max':int((p/'memory.max').read_text()),'full':int(next(w[6:] for w in full.split() if w.startswith('total='))),'events':{k:int(v) for k,v in e.items()},'stat':{k:int(s[k]) for k in ['anon','file','pgscan_direct','pgscan_kswapd','workingset_refault_file']}}))
"""
def sample():return json.loads(subprocess.check_output(['docker','exec',node,'python3','-c',program,path],text=True,timeout=10))
def change(before,after):
 script="from pathlib import Path;import sys;p=Path(sys.argv[1]);assert p.name.endswith('.scope');f=p/'memory.max';assert int(f.read_text())==int(sys.argv[2]);f.write_text(sys.argv[3]);assert int(f.read_text())==int(sys.argv[3])"
 subprocess.run(['docker','exec',node,'python3','-c',script,path,str(before),str(after)],check=True,timeout=10)
r={'run_id':'object-limit-cl','container_id':base['container_id'],'pod_uid':base['pod_uid'],'intervention':'same process/cache; temporary cgroup max512Mi to1Gi for30s, then restore512Mi','samples':[]};attempted=False
try:
 r['before']=sample();assert r['before']['max']==536870912
 assert r['before']['stat']['anon']<268435456
 assert r['before']['events']['oom']==0 and r['before']['events']['oom_kill']==0
 attempted=True;change(536870912,1073741824);r['raised']=sample();end=time.monotonic()+30
 while time.monotonic()<end:
  row=sample();r['samples'].append(row);assert row['max']==1073741824
  if row['full']>r['raised']['full'] or row['events']['oom_kill']>r['before']['events']['oom_kill']:
   r['stop']='PSI/OOM increased under1Gi';break
  time.sleep(.5)
 r['observed']=sample();r['status']='OBSERVED_NO_NEW_PSI' if r['observed']['full']==r['raised']['full'] else 'PSI_INCREASE'
finally:
 if attempted:
  actual=sample()['max']
  if actual==1073741824:change(1073741824,536870912)
  elif actual!=536870912:raise ValueError('unexpected memory max during restoration')
 r['restored']=sample();assert r['restored']['max']==536870912
 (OUT/'summary.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='samples'}))
