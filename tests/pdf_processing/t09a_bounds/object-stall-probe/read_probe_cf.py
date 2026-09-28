import json,subprocess,time
from pathlib import Path
ROOT=Path('/private/tmp/t09a-bounds');OUT=Path('/private/tmp/q44-object-read-cf');OUT.mkdir(exist_ok=False)
K=['kubectl','--context','kind-internal-a2a-vs6-local','-n','pdf-t09a-validation']
def kj(*args):return json.loads(subprocess.check_output(K+list(args)+['-o','json'],timeout=15))
pod=next(p for p in kj('get','pods','-l','app=pdf-objects')['items'] if p['status']['phase']=='Running' and all(c['ready'] for c in p['status']['containerStatuses']))
uid=pod['metadata']['uid'];cid=pod['status']['containerStatuses'][0]['containerID'].split('://')[1];node=pod['spec']['nodeName']
probe='''from pathlib import Path
import json
root=Path('/sys/fs/cgroup');matches=[p for p in root.rglob('memory.pressure') if UID.replace('-','_') in str(p) and CID in str(p)]
assert len(matches)==1
p=matches[0];full=next(l for l in p.read_text().splitlines() if l.startswith('full '));c=p.parent
print(json.dumps({'cgroup':str(c),'full':int(next(w[6:] for w in full.split() if w.startswith('total='))),'current':int((c/'memory.current').read_text()),'max':(c/'memory.max').read_text().strip(),'events':(c/'memory.events').read_text()}))
'''.replace('UID',repr(uid)).replace('CID',repr(cid))
def sample():return json.loads(subprocess.check_output(['docker','exec',node,'python3','-c',probe],timeout=15))
image=subprocess.check_output(['docker','inspect','--format','{{.Config.Image}}',node],text=True).strip()
trace=None;log=(OUT/'trace.jsonl').open('x');summary={'prefix':'t09a/bounds-20260927-cb/','bucket':'t09a','pod_uid':uid,'container_id':cid,'mode':'read-only bounded object GET diagnostic, not acceptance','reads':[]}
try:
 summary['before']=sample();assert summary['before']['max']=='536870912'
 trace=subprocess.Popen(['docker','run','--rm','--pull=never','--name','q44-object-read-cf','--pid=host','--cgroupns=host','--network=none','--privileged','--read-only','-i','--entrypoint','sh',image,'-c','mount -t tracefs tracefs /sys/kernel/tracing && exec python3 -u - --run-id object-read-cf --seconds 60'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.PIPE,text=True)
 trace.stdin.write((ROOT/'tests/pdf_processing/t09a_bounds/object-stall-probe/psi_call_trace.py').read_text());trace.stdin.close()
 deadline=time.monotonic()+10
 while not (OUT/'trace.jsonl').stat().st_size:
  if trace.poll() is not None:raise RuntimeError(trace.stderr.read())
  if time.monotonic()>deadline:raise TimeoutError('tracer start')
  time.sleep(.1)
 program = """import boto3,json,time
from botocore.config import Config
c=boto3.client('s3',endpoint_url='http://objects:9000',config=Config(connect_timeout=5,read_timeout=5,retries={'total_max_attempts':1}))
objects=c.list_objects_v2(Bucket='t09a',Prefix='t09a/bounds-20260927-cb/',MaxKeys=128).get('Contents',[])
for o in objects:print(json.dumps({'key':o['Key'],'size':o['Size']}))
"""
 objects=[json.loads(l) for l in subprocess.check_output(K+['exec','coordinator','--','/experiment/.venv/bin/python','-c',program],text=True,timeout=15).splitlines()]
 total=0;deadline=time.monotonic()+30
 for obj in objects:
  if total+obj['size']>32*1024*1024 or time.monotonic()>=deadline:break
  program="""import boto3,json,sys
from botocore.config import Config
c=boto3.client('s3',endpoint_url='http://objects:9000',config=Config(connect_timeout=5,read_timeout=5,retries={'total_max_attempts':1}))
b=c.get_object(Bucket='t09a',Key=sys.argv[1])['Body']
try: print(len(b.read()))
finally: b.close()
"""
  size=int(subprocess.check_output(K+['exec','coordinator','--','/experiment/.venv/bin/python','-c',program,obj['key']],text=True,timeout=12))
  total+=size;row={'time':time.time(),'key':obj['key'],'bytes':size,'pressure':sample()};summary['reads'].append(row)
  if row['pressure']['full']>summary['before']['full']:
   summary['stop']='object full PSI increased';break
 summary['after']=sample();summary['bytes']=total;summary['status']='PSI_REPRODUCED' if summary.get('stop') else 'NO_PSI_IN_BOUNDED_READ'
except BaseException as error:
 summary['error']=repr(error)
finally:
 if trace:
  try:
   summary['trace_exit']=trace.wait(timeout=65);summary['trace_stderr']=trace.stderr.read()
  except subprocess.TimeoutExpired:summary['trace_timeout']=True
 log.close();(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({k:v for k,v in summary.items() if k not in ('reads','before','after')}))
