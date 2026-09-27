"""Replay CO guards and report ancestor/caller evidence without cluster access."""
from collections import Counter
import gzip
import json
from pathlib import Path
import re
import sys
from ancestor_probe_co import full, violation

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('co-normal')


def read(name):
    p = root/name
    return p.read_text() if p.exists() else gzip.decompress(Path(str(p)+'.gz').read_bytes()).decode()


r = json.loads(read('summary.json'))
rows = [json.loads(x) for x in read('samples.jsonl').splitlines()]
trace = [json.loads(x) for x in read('object-stall-trace.jsonl').splitlines()]
baseline = r['baseline']
observed = [row for row in rows if row['time'] >= baseline['time'] and row['phase'] != 'restored']
failures = [(row['phase'], violation(row,baseline,4831838208 if row['phase']=='admission' else 1610612736)) for row in observed]
failures = [x for x in failures if x[1]]
if r['status'] == 'NO_PSI_IN_BOUNDED_WINDOW':
    assert not failures and r['all_ready_at'] < r['observed']['time']
    idle = [row for row in observed if row['phase']=='idle']
    assert idle[-1]['time']-idle[0]['time'] >= 29
    assert r['reads'] and sum(x['bytes'] for x in r['reads']) == r['read_bytes'] <= 32*1024**2
else:
    assert r['status']=='STOPPED' and 'trigger' in r and failures
assert r['restoration']=='verified_zero_replicas_and_no_owned_pods'
assert not r['restoration_errors']
assert r['identity']==r['final_object']
assert all(x['max']=='536870912' for x in r['restored']['levels'][:2])
assert json.loads(read('independent-cleanup.json'))['status'] == 'PASS'
assert trace[0]['kind']=='start' and trace[-1]['kind']=='end'
for stats in trace[-1]['buffer_stats'].values():
    fields = dict(x.split(':',1) for x in stats.splitlines())
    assert all(int(fields[k])==0 for k in ['overrun','commit overrun','dropped events'])
identities, callers, target = {}, Counter(), []
for row in trace:
    if row.get('identity'):
        identities[row['identity']['tid']] = row['identity']
    line = row.get('line','')
    match = re.search(r'-(\d+)\s+\[.*?\s(\d+\.\d+): psi_memstall_enter <-(\S+)',line)
    if not match:
        continue
    tid, stamp, caller = match.groups()
    wall = trace[0]['time']+float(stamp)-trace[0]['monotonic']
    if not baseline['time'] <= wall <= observed[-1]['time']:
        continue
    callers[caller] += 1
    identity = identities.get(int(tid),{})
    if r['identity']['container_id'] in identity.get('cgroup',''):
        target.append({'time':wall,'caller':caller,'identity':identity})
last = observed[-1]
result = {'status':r['status'],'guard_failures':failures,
    'measured_seconds':last['time']-baseline['time'],
    'minimum_vm_available':min(row['vm']['available'] for row in observed),
    'maximum_object_bytes':max(row['levels'][0]['current'] for row in observed),
    'vm_stat_delta':{k:last['vm']['stat'][k]-v for k,v in baseline['vm']['stat'].items()},
    'ancestor_deltas':[{'path':b['path'], 'max':b['max'],
        'full_psi_us':full(a['pressure'])['total']-full(b['pressure'])['total'],
        'events_local':{k:a['events_local'][k]-v for k,v in b['events_local'].items()},
        'stat':{k:a['stat'][k]-v for k,v in b['stat'].items()}}
        for b,a in zip(baseline['levels'],last['levels'])],
    'vm_callers':dict(callers),'target_calls':target,'read_bytes':r.get('read_bytes')}
print(json.dumps(result,indent=2))
