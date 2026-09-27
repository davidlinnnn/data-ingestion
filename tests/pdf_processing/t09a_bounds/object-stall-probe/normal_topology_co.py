"""One short normal-topology object diagnostic; no ingestion or automatic retry.

Topology and tracer helpers below are copied from the executed CG controller.
"""
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'tests/pdf_processing/q04'))
from sentinel import run_yolo_pod_cgroup_p as base
from sentinel import object_limit_trial_bh as trial
from ancestor_probe_co import violation
RUN_ID = 'object-normal-co'
OUT = Path('/private/tmp/q44-object-normal-co')
NODE = 'internal-a2a-vs6-local-worker2'
TRACE_CONTAINER = 'q44-object-normal-co'
runner = SimpleNamespace(topology=SimpleNamespace(NODE=NODE), RUN_IDENTITY=RUN_ID)
kube = base.Kubectl()
expected = base.lifecycle.CANDIDATES
record = {'run_id': RUN_ID, 'automatic_retry': False, 'restoration_errors': []}
activated = []
trace = trace_log = trace_owner = None

def current():
    items = kube.json('get', 'deployments', '-A')['items']
    by_key = {(x['metadata']['namespace'], x['metadata']['name']): x for x in items}
    rows = []
    for wanted in expected:
        item = by_key[(wanted['namespace'], wanted['name'])]
        if item['metadata']['uid'] != wanted['uid']:
            raise ValueError('recorded Deployment UID changed')
        rows.append(item)
    return rows

def patch(item, before, after):
    meta = item['metadata']
    operations = base.scale_patch(meta['uid'], meta['resourceVersion'], before, after)
    kube.run(['patch', 'deployment', meta['name'], '-n', meta['namespace'],
              '--type=json', '-p', json.dumps(operations)], timeout=30)

def restore():
    for wanted in reversed(activated):
        try:
            item = kube.json('get', 'deployment', wanted['name'], '-n', wanted['namespace'])
            if item['metadata']['uid'] != wanted['uid']:
                raise ValueError('Deployment UID changed during restoration')
            replicas = item['spec'].get('replicas', 1)
            if replicas == 1:
                patch(item, 1, 0)
            elif replicas != 0:
                raise ValueError(f'unexpected replicas={replicas}')
        except Exception as error:
            record['restoration_errors'].append(f"{wanted['namespace']}/{wanted['name']}: {error!r}")
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            rows = current()
            if all(x['spec'].get('replicas', 1) == 0 and
                   x['status'].get('readyReplicas', 0) == 0 for x in rows):
                pods = kube.json('get', 'pods', '-A')['items']
                owned = [pod for pod in pods for deployment in rows
                         if pod['metadata']['namespace'] == deployment['metadata']['namespace']
                         and deployment['spec']['selector'].get('matchLabels')
                         and all(pod['metadata'].get('labels', {}).get(k) == v
                                 for k, v in deployment['spec']['selector']['matchLabels'].items())]
                if not owned:
                    record['restoration'] = 'verified_zero_replicas_and_no_owned_pods'
                    return
        except Exception as error:
            record['restoration_errors'].append(repr(error))
            break
        time.sleep(2)
    record['restoration_errors'].append('32-Deployment restoration not verified by deadline')

def start_trace():
    global trace, trace_log, trace_owner
    program = (ROOT / 'tests/pdf_processing/t09a_bounds/object-stall-probe/psi_call_trace.py').read_text()
    trace_log = (OUT / 'object-stall-trace.jsonl').open('x')
    image = subprocess.check_output(
        ['docker', 'inspect', '--format', '{{.Config.Image}}', runner.topology.NODE],
        text=True, timeout=15,
    ).strip()
    trace = subprocess.Popen(
        ['docker', 'run', '--rm', '--pull=never', '--name', TRACE_CONTAINER,
         '--label', 'q04-run=' + runner.RUN_IDENTITY,
         '--pid=host', '--cgroupns=host', '--network=none', '--privileged', '--read-only', '-i',
         '--entrypoint', 'sh', image, '-c',
         'mount -t tracefs tracefs /sys/kernel/tracing && '
         'exec python3 -u - --run-id "$1" --seconds 2500',
         'trace', runner.RUN_IDENTITY],
        stdin=subprocess.PIPE, stdout=trace_log, stderr=subprocess.PIPE, text=True,
    )
    trace.stdin.write(program)
    trace.stdin.close()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        with (OUT / 'object-stall-trace.jsonl').open() as stream:
            first = stream.readline()
        if first:
            trace_owner = json.loads(first)
            if (trace_owner.get('kind') != 'start'
                    or trace_owner.get('run_id') != runner.RUN_IDENTITY
                    or trace_owner.get('self_cgroup') in (None, '0::/')):
                raise ValueError('object-stall trace start identity changed')
            return
        if trace.poll() is not None:
            raise RuntimeError('object-stall trace ended before start: ' + trace.stderr.read())
        time.sleep(.2)
    raise TimeoutError('object-stall trace start missing')

def stop_trace():
    if trace is None:
        return
    if trace_owner is not None and trace.poll() is None:
        program = '''import os,signal,sys
from pathlib import Path
pid=int(sys.argv[1]);expected=int(sys.argv[2]);path=Path('/proc')/str(pid)/'stat'
if path.exists():
 raw=path.read_text();actual=int(raw[raw.rfind(')')+1:].split()[19])
 if actual!=expected: raise ValueError('trace PID identity changed')
 os.kill(pid,signal.SIGTERM)
'''
        subprocess.run(['docker', 'exec', TRACE_CONTAINER, 'python3', '-c', program,
                        str(trace_owner['pid']), str(trace_owner['start_ticks'])],
                       check=True, timeout=15)
    try:
        result = trace.wait(timeout=25)
        if result != 0:
            raise RuntimeError('object-stall trace exit ' + str(result) + ': ' + trace.stderr.read())
    finally:
        trace_log.close()


def sample(phase):
    program = Path(__file__).with_name('ancestor_probe_co.py').read_text()
    row = json.loads(subprocess.check_output(['docker','exec',NODE,'python3','-c',
        program,identity['pod_uid'],identity['container_id']],text=True,timeout=10))
    row['phase'] = phase
    with (OUT/'samples.jsonl').open('a') as stream:
        stream.write(json.dumps(row)+'\n')
    return row


def limits(value):
    program = """from pathlib import Path
import sys
p=Path(sys.argv[1]); value=sys.argv[2]
assert p.name=='cri-containerd-'+sys.argv[3]+'.scope'
assert sys.argv[4].replace('-','_') in p.parent.name
for q in ([p.parent,p] if value=='1073741824' else [p,p.parent]):
 f=q/'memory.max'; assert f.read_text().strip() in ['536870912','1073741824']
 f.write_text(value)
 assert f.read_text().strip()==value
"""
    subprocess.run(['docker','exec',NODE,'python3','-c',program,
        record['before']['levels'][0]['path'],str(value),
        identity['container_id'],identity['pod_uid']],check=True,timeout=15)


def checked(phase, floor=None):
    row = sample(phase)  # Persist the trigger before checking it.
    reason = violation(row, record['baseline'], floor or base.VM_RUNTIME_FLOOR_BYTES)
    if reason:
        record['trigger'] = row
        raise ValueError(reason)
    if trace.poll() is not None:
        raise RuntimeError('tracer exited before observation ended')
    return row


def object_request(program, *args):
    return subprocess.check_output(['kubectl','--context',base.CONTEXT,'-n',base.NAMESPACE,
        'exec','coordinator','--','/experiment/.venv/bin/python','-c',
        'import signal;signal.alarm(8)\n'+program,*args],text=True,timeout=10)


def read_window():
    client = """import boto3,json,sys
from botocore.config import Config
c=boto3.client('s3',endpoint_url='http://objects:9000',config=Config(connect_timeout=3,read_timeout=3,retries={'total_max_attempts':1}))
"""
    checked('before-list')
    objects = json.loads(object_request(client+"print(json.dumps([{'key':o['Key'],'size':o['Size']} for o in c.list_objects_v2(Bucket='t09a',Prefix='t09a/bounds-20260927-cb/',MaxKeys=128).get('Contents',[])]))"))
    checked('after-list')
    end = time.monotonic()+30
    record['reads'] = []
    total = 0
    for obj in objects:
        if time.monotonic() >= end or len(record['reads']) >= 20:
            break
        if total+obj['size'] > 32*1024*1024:
            break
        checked('before-get')
        size = int(object_request(client+"body=c.get_object(Bucket='t09a',Key=sys.argv[1])['Body']\ntry: print(len(body.read()))\nfinally: body.close()",obj['key']))
        total += size
        record['reads'].append({'key':obj['key'],'bytes':size,'completed_at':time.time()})
        checked('after-get')
    record['read_bytes'] = total


if __name__ == '__main__':
    OUT.mkdir(exist_ok=False)
    changed = False
    def interrupt(*_):
        raise KeyboardInterrupt('diagnostic interrupted')
    signal.signal(signal.SIGTERM, interrupt)
    try:
        base.verify_held_deployments(kube)
        snapshot = trial.capture(kube)
        identity = snapshot['old_pod']
        record['identity'] = identity
        record['before'] = sample('preflight')
        assert all(x['max']=='536870912' for x in record['before']['levels'][:2])
        assert record['before']['vm']['stat']['oom_kill']==0
        assert record['before']['vm']['available'] >= base.OUTER_AVAILABLE_BYTES
        start_trace()
        identify = """from pathlib import Path
import json,sys
rows=[]
for p in Path('/proc').glob('[0-9]*'):
 try:
  if sys.argv[1] in (p/'cgroup').read_text() and (p/'comm').read_text().strip()=='minio':
   rows.append({'pid':int(p.name),'argv':(p/'cmdline').read_bytes().decode().split('\\0')[:-1]})
 except (FileNotFoundError,ProcessLookupError):pass
print(json.dumps(rows))
"""
        record['server_processes'] = json.loads(subprocess.check_output(['docker','exec',TRACE_CONTAINER,'python3','-c',identify,identity['container_id']],text=True,timeout=10))
        assert len(record['server_processes'])==1
        assert record['server_processes'][0]['argv']==['minio','server','/data']
        changed = True
        limits(1073741824)
        record['baseline'] = sample('raised-budget')
        checked('before-activation')
        for item in current():
            activated.append({'namespace':item['metadata']['namespace'],
                'name':item['metadata']['name'],'uid':item['metadata']['uid']})
            patch(item,0,1)
            checked('activation')
        deadline = time.monotonic()+180
        while True:
            checked('readiness')
            rows = current()
            if all(x['spec']['replicas']==1 and x['status'].get('readyReplicas',0)==1 for x in rows):
                record['all_ready_at'] = time.time()
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('32-Deployment readiness deadline')
            time.sleep(1)
        checked('admission',base.OUTER_AVAILABLE_BYTES)
        end = time.monotonic()+30
        while time.monotonic() < end:
            checked('idle');time.sleep(.5)
        read_window()
        record['observed'] = checked('window-complete')
        record['status'] = 'NO_PSI_IN_BOUNDED_WINDOW'
    except BaseException as error:
        record['status'] = 'STOPPED'
        record['error'] = repr(error)
    finally:
        for action in [stop_trace, restore]:
            try:
                action()
            except BaseException as error:
                record['restoration_errors'].append(repr(error))
        if changed:
            try:
                limits(536870912)
                record['restored'] = sample('restored')
                assert all(x['max']=='536870912' for x in record['restored']['levels'][:2])
            except BaseException as error:
                record['restoration_errors'].append(repr(error))
        try:
            base.verify_held_deployments(kube)
            after = trial.capture(kube)
            assert after['old_pod']==record['identity']
            record['final_object'] = after['old_pod']
        except BaseException as error:
            record['restoration_errors'].append(repr(error))
        record['finished_at'] = time.time()
        (OUT/'summary.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps({k:record.get(k) for k in ['status','error','restoration','restoration_errors','read_bytes']}))
    raise SystemExit(0 if record['status']=='NO_PSI_IN_BOUNDED_WINDOW' and not record['restoration_errors'] else 1)
