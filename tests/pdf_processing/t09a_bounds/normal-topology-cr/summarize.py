"""Retain CR trigger, direct task attribution, business outcomes and cleanup."""
import base64
from collections import Counter
import gzip
import json
from pathlib import Path
import re
import shutil

RAW = Path('/private/tmp/t09a-bounds-20260927-cr')
OUTER = Path('/private/tmp/t09a-normal-topology-20260927-cr')
OBJECT = Path('/private/tmp/t09a-bounds-object-20260927-cr')
DEST = Path(__file__).parent/'first-window-evidence'


def read(path):
    return json.loads(path.read_text())


def write(name, value):
    (DEST/name).write_text(json.dumps(value,indent=2)+'\n')


def direct_calls(trace, container_id):
    identities, target, unknown = {}, [], []
    current = None
    for row in trace:
        if row.get('identity'):
            identities[row['identity']['tid']] = row['identity']
        line = row.get('line','')
        match = re.search(r'-(\d+)\s+\[.*?\s(\d+\.\d+): psi_memstall_enter <-(\S+)',line)
        if match:
            tid, mono, caller = match.groups()
            task = identities.get(int(tid),{})
            wall = trace[0]['time']+float(mono)-trace[0]['monotonic']
            current = None
            if container_id in task.get('cgroup',''):
                current = {'time':wall,'caller':caller,'task':task,'stack':[]}
                target.append(current)
            elif not task.get('cgroup'):
                unknown.append({'time':wall,'tid':int(tid),'caller':caller})
        elif '<stack trace>' in line:
            tid = int(re.search(r'-(\d+)\s+\[',line)[1])
            if current and current['task']['tid'] != tid:
                current = None
        elif line.startswith(' => ') and current is not None:
            current['stack'].append(line[4:])
        elif line and not line.startswith(' => '):
            current = None
    return target, unknown


def main():
    DEST.mkdir(exist_ok=True)
    controller = read(OUTER/'held-topology-controller.json')
    objects = [json.loads(line) for line in (OBJECT/'object-pressure.jsonl').read_text().splitlines()]
    samples = [r for r in objects if r['kind']=='sample']
    identity = objects[0]
    onset = next((i for i,r in enumerate(samples) if r['object_full_total_us']>samples[0]['object_full_total_us']),None)
    trace = [json.loads(line) for line in (OUTER/'object-stall-trace.jsonl').read_text().splitlines()]
    assert trace[0]['kind']=='start' and trace[-1]['kind']=='end'
    for stats in trace[-1]['buffer_stats'].values():
        fields = dict(line.split(':',1) for line in stats.splitlines())
        assert all(int(fields[k])==0 for k in ['overrun','commit overrun','dropped events'])
    target, unknown = direct_calls(trace,identity['container_id'])
    analysis = {'controller_status':controller['status'],'samples':len(samples),
        'max_gap_seconds':max(b['time']-a['time'] for a,b in zip(samples,samples[1:])),
        'maximum_object_bytes':max(r['memory_current'] for r in samples),
        'object_full_delta_us':samples[-1]['object_full_total_us']-samples[0]['object_full_total_us'],
        'target_calls':target,'unattributed_calls':unknown,
        'first_object_psi':{'before':samples[max(0,onset-1)],'first':samples[onset]} if onset is not None else None,
        'first_sample':samples[0],'last_sample':samples[-1]}
    if (RAW/'controller-stop.json').exists():
        analysis['controller_stop'] = read(RAW/'controller-stop.json')
    vm_path = RAW/'vm-controller.jsonl'
    vm = ([json.loads(line) for line in vm_path.read_text().splitlines()]
          if vm_path.exists() else read(OBJECT/'protection-readiness.json'))
    boundary = analysis.get('controller_stop',{}).get('time',vm[-1]['time'])
    analysis['vm_sample_at_stop'] = next(row for row in reversed(vm) if row['time']<=boundary)
    analysis['worker_max_bytes'] = max((row['memory_current'] for row in vm if 'memory_current' in row),default=None)
    analysis['vm_minimum_available_bytes'] = min(row['available'] for row in vm)
    write('pressure-attribution.json',analysis)
    evidence = RAW/('evidence' if controller['runner_exit_code']==0 else 'failure-evidence')
    results = []
    for directory in sorted((evidence/'state/bounds-pod-cgroup-cr').glob('warm-*')):
        history = next((p for p in [directory/'history.json',directory/'failure-history.json'] if p.exists()),None)
        if history is None:
            continue
        events = read(history)['events']
        completed = next((e for e in reversed(events) if e['eventType']=='EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED'),None)
        result = json.loads(base64.b64decode(completed['workflowExecutionCompletedEventAttributes']['result']['payloads'][0]['data'])) if completed else {}
        results.append({'fixture':directory.name,'events':dict(Counter(e['eventType'] for e in events)),
            'business':{k:result.get(k) for k in ['status','processing_complete','canonical_accepted','registered_pages','registered_components','selected_components','error']},
            'local_verified':read(directory/'accepted.json')['verified'] if (directory/'accepted.json').exists() else False,
            'terminal_time':completed['eventTime'] if completed else None,
            'cancellation_time':next((e['eventTime'] for e in events if e['eventType']=='EVENT_TYPE_WORKFLOW_EXECUTION_CANCEL_REQUESTED'),None)})
    write('temporal-reconciliation.json',results)
    for source,name in [(RAW/'pod-pre-inference-gates.json','pre-inference-gates.json'),
        (OBJECT/'protection-readiness.json','protection-readiness.json'),
        (RAW/'outer-cleanup.json','outer-cleanup.json'),(OBJECT/'trial-cleanup.json','object-trial-cleanup.json'),
        (OUTER/'held-topology-controller.json','held-topology-controller.json'),
        (evidence/'cleanup-complete.json','cleanup-complete.json'),
        (evidence/'durable-terminal-manifest.json','durable-terminal-manifest.json')]:
        if source.exists():shutil.copyfile(source,DEST/name)
    for source,name in [(OBJECT/'object-pressure.jsonl','object-pressure.jsonl.gz'),
        (OUTER/'object-stall-trace.jsonl','object-stall-trace.jsonl.gz')]:
        (DEST/name).write_bytes(gzip.compress(source.read_bytes(),mtime=0))
    if (OBJECT/'memory-low').exists():
        shutil.copytree(OBJECT/'memory-low',DEST/'memory-low',dirs_exist_ok=True)
    print(json.dumps({k:analysis[k] for k in ['controller_status','samples','max_gap_seconds','maximum_object_bytes','object_full_delta_us']}))
    print('target calls:',len(target),'unattributed calls:',len(unknown),'business results:',len(results))


if __name__=='__main__':
    main()
