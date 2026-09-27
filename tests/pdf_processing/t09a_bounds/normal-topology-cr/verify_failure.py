"""Replay CR's retained protection, actual PSI guard and cancellation ordering."""
from datetime import datetime
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).parent
E=ROOT/'first-window-evidence'
load=lambda p:json.loads(p.read_text())
a=load(E/'pressure-attribution.json')
before,first=a['first_object_psi']['before'],a['first_object_psi']['first']
stop=a['controller_stop']
p=load(E/'protection-analysis.json')
assert p['readiness_seconds']>=125 and p['all_sampled_ancestors_protected']
calls=[c for c in a['target_calls'] if c['time']<stop['time']]
assert len(calls)==1 and calls[0]['caller']=='__alloc_pages_noprof'
assert 'ext4_readdir' in calls[0]['stack'] and 'try_charge_memcg' not in calls[0]['stack']
assert before['time']<calls[0]['time']<first['time']<stop['time']
assert first['object_full_total_us']==89
assert first['memory_current']<805306368<first['memory_max']
assert first['ancestors'][0]['events_local']['low']==30
assert all(not any(v['events_local'][k] for k in ['high','max','oom','oom_kill']) for v in first['ancestors'])
assert first['vmstat']['compact_stall']==before['vmstat']['compact_stall']
assert first['vmstat']['allocstall_movable']>before['vmstat']['allocstall_movable']
spec=importlib.util.spec_from_file_location('cr_guard',ROOT.parents[1]/'q04/sentinel/run_warm_pod_cgroup_cr.py')
run=importlib.util.module_from_spec(spec);spec.loader.exec_module(run)
run.monitor=SimpleNamespace(error=None,samples=[a['first_sample'],first])
try:
    run.verify_sample(a['vm_sample_at_stop'],0)
except ValueError as error:
    assert str(error)=='object-service max/full-PSI event during mixed warm run'
else:
    raise AssertionError('actual CR trigger accepted')
r=load(E/'temporal-reconciliation.json')
assert len(r)==5 and all(v['business']['processing_complete'] and v['local_verified'] for v in r[:4])
last=r[-1]
assert not last['business']['processing_complete'] and last['business']['registered_pages']==5
assert last['business']['error']['code']=='activity_budget_exhausted'
assert last['events'].get('EVENT_TYPE_ACTIVITY_TASK_FAILED',0)==0
assert stop['time']<datetime.fromisoformat(last['cancellation_time']).timestamp()
assert load(E/'independent-cleanup.json')['memory_low']['verified_restored']
print('PASS: protection persisted; exact allocator stall precedes PSI89us, actual guard stop and cancellation; cleanup passed')
