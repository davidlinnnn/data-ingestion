"""One approved native object candidate qualification; retain only on full PASS."""
import importlib.util
import os
import json
from pathlib import Path
import shlex
import signal
import subprocess
import time

ROOT = Path('/private/tmp/t09a-bounds')
import sys
sys.path.insert(0, str(ROOT / 'tests/pdf_processing/t09a_bounds'))
from outer_guard_handoff import handoff_on_guard
import object_policy
from observer_guard import verify_observer, stop_program
from verify_results import qualify
RUNNER = ROOT / 'tests/pdf_processing/q04/sentinel/run_warm_pod_cgroup_dc.py'
OUT = Path('/private/tmp/t09a-normal-topology-20260928-dc')
OUT.mkdir(exist_ok=False)

spec = importlib.util.spec_from_file_location('bo_controlled_runner', RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
base = runner.base
kube = base.Kubectl()
expected = base.lifecycle.CANDIDATES
assert len(expected) == 32
record = {'object_psi_policy':runner.OBJECT_PSI_POLICY,'run_id': runner.RUN_IDENTITY, 'held_deployments': 32,
          'automatic_retry': False, 'samples': [], 'restoration_errors': []}
activated = []
process = None
object_snapshot = None
observer = None
observer_log = None
observer_owner = None


def current():
    items = kube.json('get', 'deployments', '-A')['items']
    by_key = {(x['metadata']['namespace'], x['metadata']['name']): x for x in items}
    rows = []
    for wanted in expected:
        item = by_key[(wanted['namespace'], wanted['name'])]
        if item['metadata']['uid'] != wanted['uid']:
            raise ValueError('recorded Deployment UID changed')
        rows.append(item)
    return rows


def sample():
    row = base.node_vm_sample()
    record['samples'].append({
        'time': row['time'], 'available_bytes': row['available'],
        'oom_kill': row['vm_oom_kill'], 'full_psi_avg10': row['psi_full_avg10'],
    })
    return row


def patch(item, before, after):
    meta = item['metadata']
    operations = base.scale_patch(meta['uid'], meta['resourceVersion'], before, after)
    kube.run(['patch', 'deployment', meta['name'], '-n', meta['namespace'],
              '--type=json', '-p', json.dumps(operations)], timeout=30)


def restore():
    for wanted in reversed(activated):
        try:
            item = kube.json('get', 'deployment', wanted['name'], '-n', wanted['namespace'])
            if item['metadata']['uid'] != wanted['uid']:
                raise ValueError('Deployment UID changed during restoration')
            replicas = item['spec'].get('replicas', 1)
            if replicas == 1:
                patch(item, 1, 0)
            elif replicas != 0:
                raise ValueError(f'unexpected replicas={replicas}')
        except Exception as error:
            record['restoration_errors'].append(f"{wanted['namespace']}/{wanted['name']}: {error!r}")
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            rows = current()
            if all(x['spec'].get('replicas', 1) == 0 and
                   x['status'].get('readyReplicas', 0) == 0 for x in rows):
                pods = kube.json('get', 'pods', '-A')['items']
                owned = [pod for pod in pods for deployment in rows
                         if pod['metadata']['namespace'] == deployment['metadata']['namespace']
                         and deployment['spec']['selector'].get('matchLabels')
                         and all(pod['metadata'].get('labels', {}).get(k) == v
                                 for k, v in deployment['spec']['selector']['matchLabels'].items())]
                if not owned:
                    record['restoration'] = 'verified_zero_replicas_and_no_owned_pods'
                    return
        except Exception as error:
            record['restoration_errors'].append(repr(error))
            break
        time.sleep(2)
    record['restoration_errors'].append('32-Deployment restoration not verified by deadline')


def start_attribution():
    global observer, observer_log, observer_owner
    program = (ROOT / 'tests/pdf_processing/q04/sentinel/node_pressure_attribution_db.py').read_text()
    observer_log = (OUT / 'node-psi-attribution.jsonl').open('x')
    observer = subprocess.Popen(
        ['docker', 'exec', '-i', base.NODE, 'python3', '-u', '-',
         '--seconds', '2500', '--interval', '0.5', '--run-id', runner.RUN_IDENTITY],
        stdin=subprocess.PIPE, stdout=observer_log, stderr=subprocess.PIPE, text=True,
    )
    observer.stdin.write(program)
    observer.stdin.close()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        with (OUT / 'node-psi-attribution.jsonl').open() as stream:
            first = stream.readline()
        if first:
            observer_owner = json.loads(first)
            if observer_owner.get('kind') != 'start' or observer_owner.get('run_id') != runner.RUN_IDENTITY:
                raise ValueError('node attribution start identity changed')
            return
        if observer.poll() is not None:
            raise RuntimeError('node attribution ended before first sample: ' + observer.stderr.read())
        time.sleep(.2)
    raise TimeoutError('node attribution start sample missing')


def stop_attribution():
    if observer is None:
        return
    try:
        subprocess.run(['docker', 'exec', base.NODE, 'python3', '-c',
                        stop_program(runner.RUN_IDENTITY, observer_owner)],
                       check=True, timeout=15)
        result = observer.wait(timeout=25)
        if result != 0:
            raise RuntimeError('node attribution exit ' + str(result) + ': ' + observer.stderr.read())
    finally:
        observer_log.close()



try:
    runner.offline_check()
    assert runner.topology.NODE == "internal-a2a-vs6-local-worker"
    base.NODE = "internal-a2a-vs6-local-worker2"  # Reads shared VM pressure through object node; not independent capacity.
    record["worker_node"] = runner.topology.NODE
    record["outer_guard_node"] = base.NODE
    if runner.OUT.exists() or runner.OBJECT_OUT.exists():
        raise FileExistsError('fresh DC output already exists')
    rows = current()
    if any(x['spec'].get('replicas', 1) != 0 or x['status'].get('readyReplicas', 0) != 0
           for x in rows):
        raise ValueError('recorded Deployments are not all held at zero')
    runner.object_trial.deployment(kube)
    base.t09a_health(kube, OUT / 'health-before-candidate.json', require_idle=True)
    object_snapshot = object_policy.capture(kube)
    pvc_before = kube.json('get', 'pvc', 'object-data')
    record['object_pvc_before'] = {'uid': pvc_before['metadata']['uid'],
                                  'volume': pvc_before['spec']['volumeName']}
    (OUT / 'object-before.json').write_text(json.dumps(object_snapshot, indent=2) + '\n')
    old_pod = runner.object_monitor_bh.object_identity(kube, runner.object_trial.OLD_BYTES)
    object_policy.apply(kube, object_snapshot)
    candidate = object_policy.await_ready(kube, object_policy.LIMIT_BYTES,
                                         excluded_uid=old_pod['pod_uid'])
    base.t09a_health(kube, OUT / 'health-after-rollout.json', require_idle=True)
    kube.run(['delete', 'pod', candidate['pod_name'], '--wait=true'], timeout=60)
    replacement = object_policy.await_ready(kube, object_policy.LIMIT_BYTES,
                                           excluded_uid=candidate['pod_uid'])
    assert object_policy.configuration(kube.json('get', 'deployment', 'objects')) == {
        'resources': object_policy.RESOURCES, 'strategy': object_policy.STRATEGY}
    pvc = kube.json('get', 'pvc', 'object-data')
    assert pvc['status']['phase'] == 'Bound'
    assert pvc['metadata']['uid'] == pvc_before['metadata']['uid']
    assert pvc['spec']['volumeName'] == pvc_before['spec']['volumeName']
    record['candidate_rollout'] = {'old_pod': old_pod, 'first': candidate,
                                   'replacement': replacement,
                                   'object_pvc_uid': pvc['metadata']['uid']}
    # Read one retained source in place; no writes or new prefix for this check.
    program = """import json,boto3
s=boto3.client('s3',endpoint_url='http://objects:9000')
key='t09a/bounds-20260928-db/sources/original-06.pdf'
obj=s.get_object(Bucket='t09a',Key=key)
data=obj['Body'].read();assert data.startswith(b'%PDF-')
print(json.dumps({'key':key,'bytes':len(data),'readable':True}))
"""
    record['existing_object_read'] = json.loads(kube.exec_python('coordinator', program, timeout=30))
    base.t09a_health(kube, OUT / 'health-after-replacement.json', require_idle=True)
    baseline = sample()
    if baseline['vm_oom_kill'] != 0:
        raise ValueError('VM OOM baseline changed')
    record['baseline'] = record['samples'][-1]
    for item in rows:
        activated.append({'namespace': item['metadata']['namespace'],
                          'name': item['metadata']['name'], 'uid': item['metadata']['uid']})
        patch(item, 0, 1)
    deadline = time.monotonic() + 180
    while True:
        rows = current()
        if all(x['spec'].get('replicas', 1) == 1 and
               x['status'].get('readyReplicas', 0) == 1 for x in rows):
            record['all_ready_at'] = time.time()
            break
        row = sample()
        if row['vm_oom_kill'] != baseline['vm_oom_kill'] or row['psi_full_avg10'] != 0:
            raise ValueError('VM OOM or full PSI during topology readiness')
        if time.monotonic() >= deadline:
            raise TimeoutError('32-Deployment readiness deadline')
        time.sleep(2)
    row = sample()
    if (row['available'] < base.OUTER_AVAILABLE_BYTES or
            row['vm_oom_kill'] != baseline['vm_oom_kill'] or row['psi_full_avg10'] != 0):
        raise ValueError('normal-topology admission floor/pressure check failed')
    start_attribution()
    command = shlex.split(runner.exact_command())
    record['runner_command'] = command
    with (OUT / 'workload-controller.log').open('x') as log:
        record['runner_started_at'] = time.time()
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        started = time.monotonic()
        interrupted_at = None
        while process.poll() is None:
            try:
                verify_observer(observer, OUT / 'node-psi-attribution.jsonl')
                row = sample()
                if (row['available'] < base.VM_RUNTIME_FLOOR_BYTES or
                        row['vm_oom_kill'] != baseline['vm_oom_kill'] or
                        row['psi_full_avg10'] != 0):
                    raise ValueError('outer VM runtime memory/OOM/PSI guard breached')
                if time.monotonic() - started > 2100:
                    raise TimeoutError('outer controller runtime deadline')
            except Exception as error:
                if interrupted_at is None:
                    record['outer_interruption'] = repr(error)
                    record['outer_guard_handoff'] = handoff_on_guard(
                        process, runner.OUT / 'controller-stop.json',
                        record['runner_started_at'])
                    interrupted_at = time.monotonic()
            if interrupted_at is not None and time.monotonic() - interrupted_at > 330:
                process.kill()
            elif interrupted_at is not None and time.monotonic() - interrupted_at > 300:
                process.terminate()
            time.sleep(2)
        record['runner_exit_code'] = process.wait()
        record['runner_finished_at'] = time.time()
    record['status'] = ('runner_passed' if record['runner_exit_code'] == 0
                        and not record.get('outer_interruption') else 'runner_failed')
except BaseException as error:
    record['status'] = 'controller_failed'
    record['controller_error'] = repr(error)
finally:
    if process is not None and process.poll() is None:
        record['final_guard_handoff'] = handoff_on_guard(
            process, runner.OUT / 'controller-stop.json',
            record.get('runner_started_at', time.time()))
        try: process.wait(timeout=330)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    try:
        stop_attribution()
    except Exception as error:
        record['restoration_errors'].append('node attribution stop: ' + repr(error))
    if activated:
        restore()
    qualified = False
    if (record.get('status') == 'runner_passed'
            and record.get('restoration') == 'verified_zero_replicas_and_no_owned_pods'
            and not record['restoration_errors']):
        try:
            record['qualification'] = qualify(runner.OUT, runner.OBJECT_OUT, OUT)
            qualified = True
        except Exception as error:
            record['status'] = 'qualification_failed'
            record['qualification_error'] = repr(error)
    if object_snapshot is not None:
        try:
            record['object_decision'] = object_policy.finish(
                kube, object_snapshot, qualified=qualified)
            base.t09a_health(kube, OUT / 'health-after-decision.json', require_idle=True)
        except Exception as error:
            record['restoration_errors'].append('object-service: ' + repr(error))
            # A final health/readiness failure revokes retention as well.
            record['status'] = 'qualification_failed'
            try:
                record['object_decision'] = object_policy.finish(
                    kube, object_snapshot, qualified=False)
            except Exception as rollback:
                record['restoration_errors'].append('object rollback: ' + repr(rollback))
    try:
        obj = runner.object_trial.deployment(kube)
        record['minio_after'] = {'limit': runner.object_trial.limit(obj),
                                 'available': obj['status'].get('availableReplicas', 0)}
    except Exception as error:
        record['restoration_errors'].append('object-service final read: ' + repr(error))
        record['status'] = 'qualification_failed'
        if object_snapshot is not None:
            try:
                record['object_decision'] = object_policy.finish(
                    kube, object_snapshot, qualified=False)
            except Exception as rollback:
                record['restoration_errors'].append('object rollback after final read: ' + repr(rollback))
    record['finished_at'] = time.time()
    (OUT / 'held-topology-controller.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({key: record.get(key) for key in
          ('status', 'run_id', 'runner_exit_code', 'restoration',
           'restoration_errors', 'minio_after')}))

raise SystemExit(0 if record.get('status') == 'runner_passed' and
                 record.get('restoration') == 'verified_zero_replicas_and_no_owned_pods' and
                 not record['restoration_errors'] else 1)
