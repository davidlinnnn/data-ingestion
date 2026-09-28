"""Replay CP's real guard and check captured read-wait -> stop -> cancellation ordering."""
from collections import Counter
from datetime import datetime
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parent
EVIDENCE = ROOT/'first-window-evidence'
load = lambda p: json.loads(p.read_text())
a = load(EVIDENCE/'pressure-attribution.json')
first = a['first_object_psi']['first']
before = a['first_object_psi']['before']
stop = a['controller_stop']
assert before['time'] < first['time'] < stop['time']
assert first['object_full_total_us'] == 155
assert first['memory_current'] < first['memory_max']
assert all(not any(level['events_local'][k] for k in ['high','max','oom','oom_kill'])
           for level in first['ancestors'])
assert all(first['vmstat'][k]==before['vmstat'][k]
           for k in ['pgscan_direct','pgscan_kswapd','compact_stall','oom_kill'])
calls = [c for c in a['target_calls'] if c['time'] < stop['time']]
assert len(calls)==14 and not a['unattributed_calls']
assert all(before['time'] < c['time'] < first['time'] for c in calls)
assert Counter(c['caller'] for c in calls)=={'read_pages':8,'folio_wait_bit_common':6}
assert all('ext4_file_read_iter' in c['stack'] and c['task']['tgid']==860747 for c in calls)
spec = importlib.util.spec_from_file_location('cp_guard',ROOT.parents[1]/'q04/sentinel/run_warm_pod_cgroup_cp.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
run.monitor = SimpleNamespace(error=None,samples=[a['first_sample'],first])
try:
    run.verify_sample(a['vm_sample_at_stop'],0)
except ValueError as error:
    assert 'object-service max/full-PSI' in str(error)
else:
    raise AssertionError('actual CP trigger accepted')
results = load(EVIDENCE/'temporal-reconciliation.json')
assert len(results)==4
assert all(r['business']['processing_complete'] and r['local_verified'] for r in results[:3])
native = results[3]
assert native['business']['processing_complete'] is False
assert native['business']['error']['code']=='activity_budget_exhausted'
assert native['events'].get('EVENT_TYPE_ACTIVITY_TASK_FAILED',0)==0
assert stop['time'] < datetime.fromisoformat(native['cancellation_time']).timestamp()
assert load(EVIDENCE/'independent-cleanup.json')['status']=='PASS'
print('PASS: 14 attributed read-wait/readahead calls precede PSI155us, actual guard stop and Temporal cancellation; cleanup passed')
