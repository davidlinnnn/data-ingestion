"""UID-fenced, one-shot transition of only the run-owned Activity Deployment."""

import json
from pathlib import Path
import time

import pod_topology_bf as topology
from sentinel import run_yolo_pod_cgroup_p as reviewed


PHASE = 'pod-loss-pod-cgroup-bf'
EVIDENCE = '/q04-evidence/' + topology.EVIDENCE_DIRECTORY_NAME


def wait_old_sample(kube, coordinator: str, requested_at: float,
                    deadline: float, *, attribution: bool = False,
                    check_abort=lambda: None) -> dict:
    path = (EVIDENCE + '/state/' + PHASE + '-measurement/worker-1/'
            'resource-attribution.jsonl.inflight' if attribution else
            EVIDENCE + '/state/' + PHASE + '/worker-1/samples.jsonl')
    program = ("import json,sys;sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
               "from telemetry import read_rows;from pathlib import Path;"
               "rows=read_rows(Path(" + repr(path) + "));"
               "print(json.dumps(rows[-1] if rows else {}))")
    while time.time() < deadline:
        check_abort()
        row = json.loads(kube.exec_python(coordinator, program,
            timeout=reviewed.remaining_timeout(deadline, 10, 'old worker sample')))
        if row.get('time', 0) >= requested_at:
            if not 0 <= time.time() - row['time'] <= 1:
                raise ValueError('old Pod worker sample stale before deletion')
            if attribution and row.get('attribution_complete') is not True:
                raise ValueError('old Pod process attribution incomplete before deletion')
            return row
        time.sleep(.1)
    raise TimeoutError('old Pod lacked a complete sample after drain request')


def hold_owned_parser(kube, old: dict, child_pid: int, *, deadline: float):
    """Freeze only the in-flight parser descended from this exact worker."""
    ready = EVIDENCE + '/state/' + PHASE + '/worker-1/ready.json'
    program = """import json,os,psutil,signal,sys,time
from pathlib import Path
ready=json.loads(Path(sys.argv[1]).read_text());child_pid=int(sys.argv[2])
parent=psutil.Process(ready['pid'])
assert parent.create_time()==ready['created']
assert any('q04/worker_bc.py' in arg for arg in parent.cmdline())
child=psutil.Process(child_pid)
assert parent.pid in [ancestor.pid for ancestor in child.parents()]
assert 'pdf_processing.warm_child' in child.cmdline()
os.kill(child_pid,signal.SIGSTOP)
deadline=time.monotonic()+3
while child.status()!=psutil.STATUS_STOPPED:
 assert time.monotonic()<deadline
 time.sleep(.02)
print(json.dumps({'worker_pid':parent.pid,'parser_pid':child_pid,'parser_stopped':True}))
"""
    held = json.loads(kube.run(['exec', old['pod_name'], '--',
        '/experiment/.venv/bin/python', '-c', program, ready, str(child_pid)],
        timeout=reviewed.remaining_timeout(deadline, 15, 'owned parser hold')))
    if held.get('parser_pid') != child_pid or held.get('parser_stopped') is not True:
        raise ValueError('in-flight owned parser hold unproven')
    return held


def drain_worker(kube, deployment: dict, old: dict, coordinator: str,
                 request: dict, output: Path, *, deadline: float,
                 check_abort=lambda: None) -> tuple[dict, dict]:
    if (request.get('run_id') != 'q04-pod-loss-pod-cgroup-20260925-bf'
            or request.get('kind') != 'drain' or request.get('generation') != 2
            or request.get('old_pod_uid') != old['pod_uid']
            or not isinstance(request.get('child_pid'), int)
            or request['child_pid'] < 1):
        raise ValueError('owned Pod drain request identity changed')
    current = reviewed.validate_pod(kube.json('get', 'pod', old['pod_name']),
        run_label=topology.RUN_LABEL, node_name=topology.NODE,
        image=topology.IMAGE)
    if (current['pod_uid'] != old['pod_uid']
            or current['container_id'] != old['container_id']):
        raise ValueError('old Activity Pod identity changed before deletion')
    check_abort()
    held = hold_owned_parser(kube, old, request['child_pid'], deadline=deadline)
    check_abort()
    sample = wait_old_sample(kube, coordinator, request['requested_at'], deadline,
                             check_abort=check_abort)
    attribution = wait_old_sample(kube, coordinator, request['requested_at'],
                                  deadline, attribution=True,
                                  check_abort=check_abort)
    check_abort()
    deletion = reviewed.cleanup_deployment_and_pod(kube, deployment, old,
        deadline=deadline, deployment_name=topology.DEPLOYMENT,
        namespace=topology.NAMESPACE, node_name=topology.NODE)
    if not (deletion['old_runtime_absent'] and deletion['emptydirs_absent']):
        raise ValueError('old Pod runtime/scratch absence unproven')
    check_abort()
    current_deployment = kube.json('get', 'deployment', topology.DEPLOYMENT)
    if (current_deployment['metadata']['uid'] != deployment['metadata']['uid']
            or current_deployment['spec'].get('replicas') != 0):
        raise ValueError('Activity Deployment changed during Pod drain')
    patch = reviewed.scale_patch(deployment['metadata']['uid'],
        current_deployment['metadata']['resourceVersion'], 0, 1)
    check_abort()
    kube.run(['patch', 'deployment', topology.DEPLOYMENT,
              '--type=json', '-p', json.dumps(patch)],
             timeout=reviewed.remaining_timeout(deadline, 30, 'replacement scale'))
    output.mkdir(exist_ok=False)
    replacement, _ = reviewed.await_worker_pod(kube, deployment, output,
        timeout_seconds=reviewed.remaining_timeout(deadline, 120, 'replacement readiness'),
        run_label=topology.RUN_LABEL, node_name=topology.NODE,
        image=topology.IMAGE)
    if replacement['pod_uid'] == old['pod_uid']:
        raise ValueError('replacement Activity Pod reused old UID')
    check_abort()
    return replacement, {'old_pod_uid': old['pod_uid'],
        'new_pod_uid': replacement['pod_uid'],
        'old_last_sample_time': sample['time'],
        'old_last_attribution_time': attribution['time'],
        'held_parser': held,
        'old_runtime_absent': True, 'old_scratch_absent': True,
        'replacement_ready': True}
