"""UID-fenced, one-shot transition of only the run-owned Activity Deployment."""

import json
from pathlib import Path
import time

import pod_topology_bh as topology
from sentinel import run_yolo_pod_cgroup_p as reviewed


PHASE = 'pod-loss-pod-cgroup-bh'
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


def hold_owned_parser(kube, coordinator: str, old: dict, child_pid: int,
                      *, deadline: float, check_abort=lambda: None):
    """Ask the already-sampled Activity supervisor to freeze its owned parser."""
    measurement = EVIDENCE + '/state/' + PHASE + '-measurement/worker-1'
    request = {'run_id': 'q04-pod-loss-pod-cgroup-20260926-bh',
               'generation': 1, 'child_pid': child_pid,
               'old_pod_uid': old['pod_uid'], 'requested_at': time.time()}
    write = ("import json,sys;from pathlib import Path;"
             "sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
             "from pod_durable_evidence import write_once;"
             "write_once(Path(" + repr(measurement + '/hold-request.json')
             + "),json.loads(sys.stdin.read()),volume_root=Path("
             + repr(EVIDENCE) + "))")
    check_abort()
    kube.run(['exec', '-i', coordinator, '--',
        '/experiment/.venv/bin/python', '-c', write],
        input=json.dumps(request),
        timeout=reviewed.remaining_timeout(deadline, 15, 'owned parser hold request'))
    read = ("import json;from pathlib import Path;p=Path("
            + repr(measurement + '/held-parser.json')
            + ");print(p.read_text() if p.exists() else '{}')")
    while time.time() < deadline:
        check_abort()
        held = json.loads(kube.exec_python(coordinator, read,
            timeout=reviewed.remaining_timeout(deadline, 10,
                'owned parser hold proof')))
        if held:
            if (held.get('run_id') != request['run_id']
                    or held.get('generation') != 1
                    or held.get('old_pod_uid') != old['pod_uid']
                    or held.get('parser_pid') != child_pid
                    or held.get('parser_stopped') is not True
                    or held.get('held_at', 0) < request['requested_at']):
                raise ValueError('in-flight owned parser hold unproven')
            return held
        time.sleep(.1)
    raise TimeoutError('in-flight owned parser hold deadline')


def drain_worker(kube, deployment: dict, old: dict, coordinator: str,
                 request: dict, output: Path, *, deadline: float,
                 check_abort=lambda: None) -> tuple[dict, dict]:
    if (request.get('run_id') != 'q04-pod-loss-pod-cgroup-20260926-bh'
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
    held = hold_owned_parser(kube, coordinator, old, request['child_pid'],
                             deadline=deadline, check_abort=check_abort)
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
