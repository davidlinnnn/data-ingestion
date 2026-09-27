"""Replay the actual guard and compare retained CD/CG memory counters offline."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

Q04 = Path(__file__).resolve().parents[2] / 'q04'
sys.path.insert(0, str(Q04))
spec = importlib.util.spec_from_file_location('cg_guard', Q04/'sentinel/run_warm_pod_cgroup_cg.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
rows = []
for tag in ('cd', 'cg'):
    vm = [json.loads(line) for line in Path(f'/private/tmp/t09a-bounds-20260927-{tag}/vm-controller.jsonl').read_text().splitlines()]
    objects = [row for line in Path(f'/private/tmp/t09a-bounds-object-20260927-{tag}/object-pressure.jsonl').read_text().splitlines()
               if (row := json.loads(line))['kind'] == 'sample']
    guard.monitor = SimpleNamespace(error=None, samples=[objects[0], objects[-1]])
    verdict, error = 'PASS', None
    try:
        guard.verify_sample(vm[-1], vm[0]['vm_oom_kill'])
    except ValueError as exception:
        verdict, error = 'FAIL', str(exception)
    row = {'run': tag, 'guard_replay': verdict, 'guard_error': error,
           'duration_seconds': vm[-1]['time']-vm[0]['time'],
           'minimum_available_bytes': min(r['available'] for r in vm),
           'maximum_worker_bytes': max(r['memory_current'] for r in vm),
           'maximum_object_bytes': max(r['memory_current'] for r in objects),
           'object_full_psi_delta_us': objects[-1]['object_full_total_us']-objects[0]['object_full_total_us']}
    for group in ('node_vmstat', 'memory_stat'):
        row[group + '_delta'] = {key: vm[-1][group][key]-vm[0][group][key]
            for key in ('pgscan_direct','pgscan_kswapd','workingset_refault_file','compact_stall','allocstall_movable','thp_fault_alloc')
            if key in vm[0][group]}
    rows.append(row)
assert rows[0]['guard_replay'] == 'FAIL' and 'object-service' in rows[0]['guard_error']
assert rows[1]['guard_replay'] == 'PASS'
output = {'comparison': rows, 'limitation': 'CD stopped before the last document completed; durations and completed work differ. Counter differences are correlations, not causal proof.'}
Path(__file__).with_name('cd-cg-comparison.json').write_text(json.dumps(output, indent=2)+'\n')
print('CD: FAIL object PSI; CG: PASS; actual guard replay verified')
