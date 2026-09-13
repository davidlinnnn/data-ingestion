"""Summarize continuous measurements without promoting observations to support limits."""
import json
from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv)>1 else '/private/tmp/t09a-controller')
rows = []
for path in sorted(root.glob('*-samples.jsonl')):
    samples = [json.loads(line) for line in path.read_text().splitlines()]
    if not samples:continue
    processes = [p for s in samples for p in s['processes']]
    child = [p for p in processes if p['module']!='worker.py']
    row = {'trial':path.name.removesuffix('-samples.jsonl'),'samples':len(samples),
        'start':samples[0]['time'],'end':samples[-1]['time'],
        'maximum_sampling_gap_seconds':max((b['time']-a['time'] for a,b in zip(samples,samples[1:])),default=0),
        'cgroup_current_peak_bytes':max(int(s['memory_current']) for s in samples),
        'cgroup_kernel_peak_bytes':max(int(s['memory_peak']) for s in samples),
        'cgroup_limit_bytes':samples[-1]['memory_max'],'final_memory_events':samples[-1]['memory_events'],
        'child_rss_peak_bytes':max((p['rss'] for p in child),default=0),
        'warm_child_instances':len({(p['pid'],p['created']) for p in child if p['module']=='pdf_processing.warm_child'}),
        'scratch_logical_peak_bytes':max(s['scratch']['bytes'] for s in samples),
        'scratch_allocated_peak_bytes':max(s['scratch']['allocated_bytes'] for s in samples),
        'scratch_final_bytes':samples[-1]['scratch']['bytes'],
        'scratch_minimum_free_bytes':min(s['scratch']['free_bytes'] for s in samples),
        'interpretation':'observations only; correlate complete result, host contention, sampling gaps and configuration before acceptance'}
    pod_samples = []
    for inventory in root.glob(row['trial']+'-*-inventory.jsonl'):
        for line in inventory.read_text().splitlines():
            snapshot = json.loads(line)
            for pod in snapshot.get('node',{}).get('pods',[]):
                ref = pod['podRef']
                if ref['namespace']=='pdf-t09a-validation' and ref['name'].startswith('activities-'):
                    pod_samples.append({'time':snapshot['time'],'memory':pod.get('memory',{}),
                                        'storage':pod.get('ephemeral-storage',{})})
    if pod_samples:
        pod_samples.sort(key=lambda x:x['time'])
        row['whole_pod_samples'] = len(pod_samples)
        row['whole_pod_usage_peak_bytes'] = max(p['memory'].get('usageBytes',0) for p in pod_samples)
        row['whole_pod_working_set_peak_bytes'] = max(p['memory'].get('workingSetBytes',0) for p in pod_samples)
        row['whole_pod_maximum_sampling_gap_seconds'] = max((b['time']-a['time'] for a,b in zip(pod_samples,pod_samples[1:])),default=0)
        row['whole_pod_ephemeral_storage_peak_bytes'] = max(p['storage'].get('usedBytes',0) for p in pod_samples)
    rows.append(row)
print(json.dumps(rows,indent=2))
