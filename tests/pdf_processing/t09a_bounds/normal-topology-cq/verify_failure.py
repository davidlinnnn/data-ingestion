"""Replay CQ's actual protection-contract failure from retained samples."""
import gzip
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).parent
EVIDENCE = ROOT/'first-window-evidence'
load = lambda p: json.loads(p.read_text())
a = load(EVIDENCE/'pressure-attribution.json')
rows = [json.loads(line) for line in gzip.decompress((EVIDENCE/'object-pressure.jsonl.gz').read_bytes()).decode().splitlines()]
rows = [r for r in rows if r['kind']=='sample']
low = 768*1024**2
index = next(i for i,r in enumerate(rows) if any(int(v['memory_low'])!=low for v in r['ancestors']))
before, first = rows[index-1], rows[index]
changed = [v for v in first['ancestors'] if int(v['memory_low'])!=low]
assert len(changed)==1 and changed[0]['cgroup'].endswith('kubelet-kubepods-burstable.slice')
assert changed[0]['memory_low']=='0'
assert before['time'] < first['time'] < a['controller_stop']['time']
assert a['object_full_delta_us']==0 and not a['target_calls']
spec = importlib.util.spec_from_file_location('cq_guard',ROOT.parents[1]/'q04/sentinel/run_warm_pod_cgroup_cq.py')
run = importlib.util.module_from_spec(spec);spec.loader.exec_module(run)
run.monitor = SimpleNamespace(error=None,samples=[rows[0],first])
try:
    run.verify_sample(a['vm_sample_at_stop'],0)
except ValueError as error:
    assert str(error)=='object memory.low contract changed'
else:
    raise AssertionError('actual CQ trigger accepted')
assert load(EVIDENCE/'outer-cleanup.json')['disposition']=='CLEANED_WITH_PVC_RETAINED_WORKLOAD_NOT_STARTED'
assert load(EVIDENCE/'temporal-reconciliation.json')==[]
assert load(EVIDENCE/'independent-cleanup.json')['memory_low']['verified_restored']
print('PASS: exact ancestor reset triggers actual guard before workload; zero target PSI; restoration verified')
