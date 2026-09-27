"""Independent, read-only CS restoration check after the controller finishes."""
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
Q04 = Path(__file__).resolve().parents[2]/'q04'
sys.path.insert(0,str(Q04))
from sentinel import run_yolo_pod_cgroup_p as base
from sentinel import object_limit_trial_bh as trial
from sentinel import object_monitor_bh as monitor
from sentinel import object_memory_low_cs as protection

kube = base.Kubectl()
base.verify_held_deployments(kube)
deployments = kube.json('get','deployments','-A')['items']
by = {(d['metadata']['namespace'],d['metadata']['name']):d for d in deployments}
held = [by[e['namespace'],e['name']] for e in base.lifecycle.CANDIDATES]
pods = kube.json('get','pods','-A')['items']
owned = [p['metadata']['name'] for p in pods for d in held
    if p['metadata']['namespace']==d['metadata']['namespace']
    and d['spec']['selector'].get('matchLabels')
    and all(p['metadata'].get('labels',{}).get(k)==v for k,v in d['spec']['selector']['matchLabels'].items())]
assert not owned
assert not kube.json('get','pods','-l','q04-run=t09a-bounds-cs')['items']
object_state = trial.capture(kube)
health = kube.run(['exec','coordinator','--','/experiment/.venv/bin/python','-c',
    'import urllib.request;print(urllib.request.urlopen("http://objects:9000/minio/health/live",timeout=5).status)'],timeout=15)
assert health.strip()=='200'
pvcs = kube.json('get','pvc','--field-selector','metadata.name=t09a-bounds-cs-evidence-20260928')['items']
if pvcs:
    assert len(pvcs)==1 and pvcs[0]['status']['phase']=='Bound'
else:
    assert not Path('/private/tmp/t09a-bounds-20260928-cs').exists(), 'PVC missing after workload setup began'
observer_path = Path('/private/tmp/t09a-bounds-object-20260928-cs/object-pressure.jsonl')
needles = ['t09a-bounds-20260928-cs','','']  # Before start, match any observer for this run.
if observer_path.exists() and observer_path.stat().st_size:
    start = json.loads(observer_path.read_text().splitlines()[0])
    needles[1:] = [start['pod_uid'],start['container_id']]
monitor.verify_remote_absence(needles)
containers = subprocess.check_output(['docker','ps','-a','--format','{{.Names}}'],text=True,timeout=15).splitlines()
assert not [n for n in containers if n.startswith('q44-')]
node = 'internal-a2a-vs6-local-worker2'
image = subprocess.check_output(['docker','inspect','--format','{{.Config.Image}}',node],text=True).strip()
instances = subprocess.check_output(['docker','run','--rm','--pull=never','--network=none',
    '--privileged','--read-only','--entrypoint','sh',image,'-c',
    'mount -t tracefs tracefs /sys/kernel/tracing && ls /sys/kernel/tracing/instances'],text=True,timeout=15).splitlines()
assert not [n for n in instances if n.startswith('q44')]
protection_result = protection.host('verify-restored',Path('/private/tmp/t09a-bounds-object-20260928-cs/memory-low'))
result = {'memory_low':protection_result,'status':'PASS','held_deployments':32,'held_owned_pods':owned,
    'object_limit':object_state['old_limit'],'object_ready':True,'object_health_http':200,
    'worker_pod_absent':True,'evidence_pvc':pvcs[0]['metadata']['name'] if pvcs else None,
    'evidence_pvc_phase':'Bound' if pvcs else 'not_created',
    'object_observer_absent':True,'diagnostic_containers_absent':True,'private_trace_instances_absent':True}
destination = Path(__file__).parent/'first-window-evidence'
destination.mkdir(exist_ok=True)
(destination/'independent-cleanup.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
