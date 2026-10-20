"""Parent owns hard wall and host-memory fence independently of model kernels."""
from pathlib import Path
import datetime,json,os,signal,subprocess,sys,time
import psutil
P=Path(__file__).resolve().parent;split=sys.argv[1]
assert split in ['dev','test']
log=(P/('inference-'+split+'.log')).open('x')
env=dict(os.environ);env['HF_HUB_OFFLINE']='1';env['TRANSFORMERS_OFFLINE']='1';env['PYTORCH_ENABLE_MPS_FALLBACK']='0'
child=subprocess.Popen([sys.executable,'-B',str(P/'infer.py'),split],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
start=time.monotonic();minimum=psutil.virtual_memory().available;maxrss=0;samples=[];reason=None
while child.poll() is None:
    now=time.monotonic();av=psutil.virtual_memory().available;minimum=min(minimum,av)
    try:rss=psutil.Process(child.pid).memory_info().rss;maxrss=max(maxrss,rss)
    except psutil.NoSuchProcess:rss=0
    samples.append({'elapsed':round(now-start,3),'available':av,'RSS':rss})
    if av<8*1024**3:reason='MEMORY_FENCE_BELOW_8_GiB'
    elif datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime(2026,10,20,13,43,3,tzinfo=datetime.timezone.utc):reason='TASK_TIME_FENCE_WITH_REPORT_RESERVE'
    else:
        try:active=json.loads((P/'active.json').read_text())
        except (FileNotFoundError,ValueError):active={}
        if active.get('split')==split and active.get('phase') in ['forward','load'] and now-active.get('started_monotonic',now)>180:reason='HARD_180S_PHASE_DEADLINE'
    if reason:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait(timeout=5);break
    time.sleep(.25)
log.close()
(P/('supervisor-'+split+'.json')).write_text(json.dumps({'exit_code':child.returncode,'stop':reason,'elapsed_seconds':time.monotonic()-start,'min_host_available_bytes':minimum,'max_RSS_bytes':maxrss,'samples':samples,'model_network':'HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE','CPU_fallback':False},indent=2)+'\n')
print(json.dumps({'split':split,'exit_code':child.returncode,'stop':reason,'elapsed':time.monotonic()-start,'min_host_available_GiB':minimum/1024**3,'max_RSS_GiB':maxrss/1024**3}))
