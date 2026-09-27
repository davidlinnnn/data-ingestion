import json,subprocess,time
from pathlib import Path
ROOT=Path('/private/tmp/t09a-bounds');OUT=Path('/private/tmp/q44-object-idle-ck');OUT.mkdir(exist_ok=False)
prior=json.loads(Path('/private/tmp/q44-object-reclaim-ci/summary.json').read_text());path=prior['before']['cgroup'];cid=prior['container_id'];node='internal-a2a-vs6-local-worker2'
program="""from pathlib import Path
import json,time,sys
p=Path(sys.argv[1])
def fields(n):return {k:int(v) for k,v in (l.split() for l in (p/n).read_text().splitlines())}
s=fields('memory.stat');full=next(l for l in (p/'memory.pressure').read_text().splitlines() if l.startswith('full '))
print(json.dumps({'time':time.time(),'full':int(next(w[6:] for w in full.split() if w.startswith('total='))),'current':int((p/'memory.current').read_text()),'max':int((p/'memory.max').read_text()),'swap':int((p/'memory.swap.current').read_text()),'events':fields('memory.events'),'stat':{k:s[k] for k in ['anon','file','pgscan_direct','pgscan_kswapd','workingset_refault_file']}}))
"""
def sample():return json.loads(subprocess.check_output(['docker','exec',node,'python3','-c',program,path],text=True,timeout=8))
image=subprocess.check_output(['docker','inspect','--format','{{.Config.Image}}',node],text=True).strip();result={'run_id':'object-idle-ck','mode':'read-only idle observation, no object requests or reclaim','container_id':cid,'pod_uid':prior['pod_uid'],'samples':[]};trace=None
with (OUT/'trace.jsonl').open('x') as log:
 try:
  result['before']=sample()
  trace=subprocess.Popen(['docker','run','--rm','--pull=never','--name','q44-object-idle-ck','--pid=host','--cgroupns=host','--network=none','--privileged','--read-only','-i','--entrypoint','sh',image,'-c','mount -t tracefs tracefs /sys/kernel/tracing && exec python3 -u - --run-id object-idle-ck --seconds 75'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.PIPE,text=True)
  trace.stdin.write((ROOT/'tests/pdf_processing/t09a_bounds/object-stall-probe/psi_call_trace.py').read_text());trace.stdin.close()
  deadline=time.monotonic()+10
  while not (OUT/'trace.jsonl').stat().st_size:
   if trace.poll() is not None:raise RuntimeError(trace.stderr.read())
   if time.monotonic()>deadline:raise TimeoutError('trace start')
   time.sleep(.1)
  identify="""from pathlib import Path
import json,sys
rows=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  if sys.argv[1] not in (p/'cgroup').read_text():continue
  if (p/'comm').read_text().strip()!='minio':continue
  rows.append({'pid':int(p.name),'argv':(p/'cmdline').read_bytes().decode().split('\\0')[:-1]})
 except (FileNotFoundError,ProcessLookupError):pass
print(json.dumps(rows))
"""
  result['server_processes']=json.loads(subprocess.check_output(['docker','exec','q44-object-idle-ck','python3','-c',identify,cid],text=True,timeout=10))
  end=time.monotonic()+60
  while time.monotonic()<end:
   row=sample();result['samples'].append(row)
   if row['full']>result['before']['full']:
    result['status']='IDLE_PSI_INCREASE';break
   if trace.poll() is not None:raise RuntimeError('trace exited early')
   time.sleep(.5)
  else:result['status']='NO_NEW_PSI_IN_60_SECONDS'
 finally:
  if trace and trace.poll() is None:
   owner=json.loads((OUT/'trace.jsonl').read_text().splitlines()[0]);stop="import os,signal,sys;from pathlib import Path;p=int(sys.argv[1]);assert int(Path(f'/proc/{p}/stat').read_text().rsplit(') ',1)[1].split()[19])==int(sys.argv[2]);os.kill(p,signal.SIGTERM)";subprocess.run(['docker','exec','q44-object-idle-ck','python3','-c',stop,str(owner['pid']),str(owner['start_ticks'])],check=True,timeout=10)
  if trace:result['trace_exit']=trace.wait(timeout=15);result['trace_stderr']=trace.stderr.read()
  result['after']=sample();(OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='samples'}))
