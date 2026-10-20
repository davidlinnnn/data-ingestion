from pathlib import Path
import datetime,json,os,signal,subprocess,sys,time
import psutil
P=Path(__file__).resolve().parent;model,split=sys.argv[1:3];device=sys.argv[3] if len(sys.argv)>3 else 'mps'
assert model in ('d3-nano','d3-mini') and split in ('dev','test') and device in ('mps','cpu')
base=P/'runs'/model/split;base.mkdir(parents=True,exist_ok=True);log=(base/'log.txt').open('x')
child=subprocess.Popen([sys.executable,'-B',str(P/'infer.py'),model,split,'--device',device],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
t=time.monotonic();samples=[];minimum=psutil.virtual_memory().available;maximum=0;reason=None
while child.poll() is None:
 now=time.monotonic();av=psutil.virtual_memory().available;minimum=min(minimum,av)
 try:rss=psutil.Process(child.pid).memory_info().rss;maximum=max(maximum,rss)
 except psutil.NoSuchProcess:rss=0
 samples.append({'elapsed':now-t,'available':av,'RSS':rss})
 if av<8*1024**3:reason='MEMORY_FENCE'
 elif datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime(2026,10,20,13,43,16,tzinfo=datetime.timezone.utc):reason='TASK_TIME_FENCE_REPORT_RESERVE'
 else:
  try:active=json.loads((P/'active.json').read_text())
  except (FileNotFoundError,ValueError):active={}
  if active.get('model')==model and active.get('split')==split and active.get('phase') in ('load','forward') and now-active.get('started_monotonic',now)>180:reason='HARD_180S_PHASE_TIMEOUT'
 if reason:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  child.wait(timeout=5);break
 time.sleep(.25)
log.close();out={'exit_code':child.returncode,'stop':reason,'elapsed_seconds':time.monotonic()-t,'min_host_available_bytes':minimum,'max_RSS_bytes':maximum,'samples':samples,'device':device}
(base/'supervisor.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='samples'}))
