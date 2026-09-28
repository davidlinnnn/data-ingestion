"""Replay the approved object policy and unchanged VM stop against CS evidence."""
from datetime import datetime
import gzip
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).parent
E=ROOT/'first-window-evidence'
load=lambda p:json.loads(p.read_text())
a=load(E/'pressure-attribution.json')
rows=[json.loads(x) for x in gzip.decompress((E/'object-pressure.jsonl.gz').read_bytes()).decode().splitlines()]
rows=[r for r in rows if r['kind']=='sample']
assert a['object_full_delta_us']==117 and a['maximum_object_full_avg10']==0
assert not a['original_zero_object_full_psi_passed']
assert a['controller_stop']['reason']=='VM PSI guard breached'
assert a['vm_sample_at_stop']['psi_full_avg10']==0.18
assert a['vm_sample_at_stop']['vm_oom_kill']==0
spec=importlib.util.spec_from_file_location('cs_guard',ROOT.parents[1]/'q04/sentinel/run_warm_pod_cgroup_cs.py')
run=importlib.util.module_from_spec(spec);spec.loader.exec_module(run)
run.monitor=SimpleNamespace(error=None,samples=rows);run.checked_samples=0
run.verify_object_monitor()  # All object samples accepted without deleting cumulative PSI.
assert run.checked_samples==len(rows)
try:
    run.verify_sample(a['vm_sample_at_stop'],0)
except ValueError as error:
    assert str(error)=='VM PSI guard breached'
else:
    raise AssertionError('VM trigger accepted')
w=load(E/'vm-pressure-windows.json')['largest_windows'][0]
assert w['delta']==22894
assert w['row']['node_vmstat']['compact_stall']==w['before_row']['node_vmstat']['compact_stall']
stage=load(E/'active-stage.json')
assert stage['stage']=='component_ocr' and stage['worker_alloc_calls']==173 and stage['threads']==18
r=load(E/'temporal-reconciliation.json');assert len(r)==1
result=r[0]
assert result['business']['processing_complete'] is False and result['business']['registered_pages']==28
assert result['business']['error']['code']=='activity_budget_exhausted'
assert result['events'].get('EVENT_TYPE_ACTIVITY_TASK_FAILED',0)==0
assert a['first_object_psi']['first']['time']<a['controller_stop']['time']<datetime.fromisoformat(result['cancellation_time']).timestamp()
assert load(E/'independent-cleanup.json')['memory_low']['verified_restored']
print('PASS:117us object PSI allowed/retained; VM0.18 guard rejected; allocation-wave and cancellation ordering retained; cleanup passed')
