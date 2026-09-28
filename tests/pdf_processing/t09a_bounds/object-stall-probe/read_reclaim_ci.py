"""CI: one file-cache-sized reclaim request, capped at384MiB; no retry."""
import json
from pathlib import Path
import subprocess
import time

ROOT = Path('/private/tmp/t09a-bounds')
OUT = Path('/private/tmp/q44-object-reclaim-ci')
K = ['kubectl', '--context', 'kind-internal-a2a-vs6-local', '-n', 'pdf-t09a-validation']


def remote(program, *args):
    return subprocess.check_output(K + ['exec', 'coordinator', '--',
        '/experiment/.venv/bin/python', '-c', program, *args], text=True, timeout=15)


GET = """import boto3,sys
from botocore.config import Config
c=boto3.client('s3',endpoint_url='http://objects:9000',config=Config(connect_timeout=3,read_timeout=5,retries={'total_max_attempts':1}))
b=c.get_object(Bucket='t09a',Key=sys.argv[1])['Body']
try: print(len(b.read()))
finally: b.close()
"""
LIST = """import boto3,json
from botocore.config import Config
c=boto3.client('s3',endpoint_url='http://objects:9000',config=Config(connect_timeout=3,read_timeout=5,retries={'total_max_attempts':1}))
print(json.dumps(c.list_objects_v2(Bucket='t09a',Prefix='t09a/bounds-20260927-cb/',MaxKeys=32).get('Contents',[]),default=str))
"""


def main():
    OUT.mkdir(exist_ok=False)
    pods = json.loads(subprocess.check_output(K + ['get', 'pods', '-l', 'app=pdf-objects', '-o', 'json']))['items']
    ready = [p for p in pods if p['status']['phase'] == 'Running'
             and all(c['ready'] for c in p['status']['containerStatuses'])]
    assert len(ready) == 1
    pod = ready[0]; uid = pod['metadata']['uid']
    cid = pod['status']['containerStatuses'][0]['containerID'].split('://')[1]
    node = pod['spec']['nodeName']
    probe = """from pathlib import Path
import json,time
paths=[p.parent for p in Path('/sys/fs/cgroup').rglob('memory.pressure') if UID.replace('-','_') in str(p) and CID in str(p)]
assert len(paths)==1
p=paths[0]
def fields(name):return {k:int(v) for k,v in (l.split() for l in (p/name).read_text().splitlines())}
pressure=next(l for l in (p/'memory.pressure').read_text().splitlines() if l.startswith('full '))
stat=fields('memory.stat')
print(json.dumps({'time':time.time(),'cgroup':str(p),'current':int((p/'memory.current').read_text()),'max':int((p/'memory.max').read_text()),'swap':int((p/'memory.swap.current').read_text()),'full':int(next(w[6:] for w in pressure.split() if w.startswith('total='))),'events':fields('memory.events'),'stat':{k:stat[k] for k in ['anon','file','workingset_refault_file','pgscan_direct','pgscan_kswapd','pgmajfault']}}))
""".replace('UID', repr(uid)).replace('CID', repr(cid))
    def sample():
        return json.loads(subprocess.check_output(['docker', 'exec', node, 'python3', '-c', probe], text=True, timeout=10))
    result = {'run_id': 'object-reclaim-ci', 'mode': 'diagnostic-only', 'pod_uid': uid,
              'container_id': cid, 'automatic_retry': False, 'reads': []}
    trace = None
    log = (OUT/'trace.jsonl').open('x')
    try:
        baseline = sample(); result['before'] = baseline
        assert baseline['max'] == 536870912 and baseline['swap'] == 0
        assert baseline['stat']['file'] >= 16*1024*1024
        assert all(baseline['events'][k] == 0 for k in ('max','oom','oom_kill'))
        image = subprocess.check_output(['docker','inspect','--format','{{.Config.Image}}',node],text=True).strip()
        trace = subprocess.Popen(['docker','run','--rm','--pull=never','--name','q44-object-reclaim-ci',
            '--pid=host','--cgroupns=host','--network=none','--privileged','--read-only','-i',
            '--entrypoint','sh',image,'-c','mount -t tracefs tracefs /sys/kernel/tracing && '
            'exec python3 -u - --run-id object-reclaim-ci --seconds 90'],
            stdin=subprocess.PIPE,stdout=log,stderr=subprocess.PIPE,text=True)
        trace.stdin.write((ROOT/'tests/pdf_processing/t09a_bounds/object-stall-probe/psi_call_trace.py').read_text())
        trace.stdin.close()
        deadline = time.monotonic()+10
        while not (OUT/'trace.jsonl').stat().st_size:
            if trace.poll() is not None: raise RuntimeError(trace.stderr.read())
            if time.monotonic()>deadline: raise TimeoutError('trace start')
            time.sleep(.1)
        selected=[]; total=0
        for obj in json.loads(remote(LIST)):
            if total+obj['Size']>4*1024*1024: break
            selected.append(obj);total+=obj['Size']
        assert selected
        result['selected_count']=len(selected);result['bytes_per_pass']=total
        deadline=time.monotonic()+60
        for phase in ('control','after_reclaim'):
            if phase == 'after_reclaim':
                result['pre_reclaim']=sample()
                reclaim = """from pathlib import Path
import json,time,sys
p=Path(sys.argv[1]);assert p.name.endswith('.scope')
assert int((p/'memory.max').read_text())==536870912
assert (p/'memory.swap.max').read_text().strip()=='0'
stat=dict(l.split() for l in (p/'memory.stat').read_text().splitlines())
requested=int(stat['file'])+1048576
assert 8388608 <= requested <= 402653184
r={'requested_bytes':requested,'swappiness':0,'time':time.time(),'file_bytes_before':int(stat['file'])}
try:(p/'memory.reclaim').write_text(str(requested)+' swappiness=0')
except OSError as e:r['errno']=e.errno;r['error']=str(e)
print(json.dumps(r))
"""
                result['reclaim']=json.loads(subprocess.check_output(['docker','exec',node,'python3','-c',reclaim,baseline['cgroup']],text=True,timeout=15))
            for obj in selected:
                if time.monotonic()>deadline: raise TimeoutError('bounded read deadline')
                if trace.poll() is not None: raise RuntimeError('tracer exited early')
                size=int(remote(GET,obj['Key'])); row=sample()
                result['reads'].append({'phase':phase,'key':obj['Key'],'bytes':size,'sample':row})
                if row['full']>baseline['full'] or any(row['events'][k]>baseline['events'][k] for k in ('max','oom','oom_kill')):
                    result['stop_phase']=phase;result['status']='GUARD_EVENT_REPRODUCED';return
        result['status']='NO_GUARD_EVENT_IN_BOUNDED_PROBE'
    except BaseException as error:
        result['error']=repr(error)
    finally:
        try: result['after']=sample()
        except Exception as error: result['final_sample_error']=repr(error)
        if trace:
            owner=json.loads((OUT/'trace.jsonl').read_text().splitlines()[0])
            stop="import os,signal,sys;from pathlib import Path;pid=int(sys.argv[1]);assert int(Path(f'/proc/{pid}/stat').read_text().rsplit(') ',1)[1].split()[19])==int(sys.argv[2]);os.kill(pid,signal.SIGTERM)"
            if trace.poll() is None:
                subprocess.run(['docker','exec','q44-object-reclaim-ci','python3','-c',stop,str(owner['pid']),str(owner['start_ticks'])],check=True,timeout=10)
            result['trace_exit']=trace.wait(timeout=15);result['trace_stderr']=trace.stderr.read()
        log.close();(OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k not in ('reads','before','after','pre_reclaim')}))


if __name__ == '__main__':
    main()
