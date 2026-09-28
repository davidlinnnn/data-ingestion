"""One approved terminal-VM-boundary qualification; retain only on full PASS."""
import importlib.util
import os
import json
from pathlib import Path
import shlex
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE))
from controller_io import retained_object, start_trace as start_native, finish_trace as finish_native
sys.path.insert(0, str(ROOT / 'tests/pdf_processing/t09a_bounds'))
from outer_guard_handoff import handoff_on_guard
import object_policy
sys.path.append(str(ROOT / 'tests/pdf_processing/t09a_bounds/normal-topology-dc'))
from observer_guard import verify_observer, stop_program
from qualify_baseline import qualify
sys.path.insert(0, str(ROOT / 'tests/pdf_processing/t09a_bounds/normal-topology-dh'))
from terminal_vm_guard import runtime_psi_is_telemetry, terminal_proofs
RUNNER = HERE / 'runner.py'
OUT = Path('/private/tmp/t09b-controller-20260928-a5')
OUT.mkdir(exist_ok=False)

spec = importlib.util.spec_from_file_location('bo_controlled_runner', RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner = runner.runner
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
trace = None
trace_log = None
trace_owner = None
native_trace = None
TRACE_CONTAINER = 't09b-a5-object-stall'
TRACE_INSTANCE = 'q44_' + runner.RUN_IDENTITY.replace('-', '_')


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


def start_trace():
    global trace, trace_log, trace_owner
    program = (ROOT / 'tests/pdf_processing/t09a_bounds/object-stall-probe/psi_call_trace.py').read_text()
    trace_log = (OUT / 'object-stall-trace.jsonl').open('x')
    image = subprocess.check_output(
        ['docker', 'inspect', '--format', '{{.Config.Image}}', runner.topology.NODE],
        text=True, timeout=15,
    ).strip()
    trace = subprocess.Popen(
        ['docker', 'run', '--rm', '--pull=never', '--name', TRACE_CONTAINER,
         '--label', 'q04-run=' + runner.RUN_IDENTITY,
         '--pid=host', '--cgroupns=host', '--network=none', '--privileged', '--read-only', '-i',
         '--entrypoint', 'sh', image, '-c',
         'mount -t tracefs tracefs /sys/kernel/tracing && '
         'exec python3 -u - --run-id "$1" --seconds 2500',
         'trace', runner.RUN_IDENTITY],
        stdin=subprocess.PIPE, stdout=trace_log, stderr=subprocess.PIPE, text=True,
    )
    trace.stdin.write(program)
    trace.stdin.close()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        with (OUT / 'object-stall-trace.jsonl').open() as stream:
            first = stream.readline()
        if first:
            trace_owner = json.loads(first)
            if (trace_owner.get('kind') != 'start'
                    or trace_owner.get('run_id') != runner.RUN_IDENTITY
                    or trace_owner.get('self_cgroup') in (None, '0::/')):
                raise ValueError('object-stall trace start identity changed')
            return
        if trace.poll() is not None:
            raise RuntimeError('object-stall trace ended before start: ' + trace.stderr.read())
        time.sleep(.2)
    raise TimeoutError('object-stall trace start missing')


def stop_trace():
    errors = []
    try:
        if trace is not None and trace.poll() is None and trace_owner is not None:
            program = '''import os,signal,sys
from pathlib import Path
pid=int(sys.argv[1]);expected=int(sys.argv[2]);path=Path('/proc')/str(pid)/'stat'
if path.exists():
 raw=path.read_text();actual=int(raw[raw.rfind(')')+1:].split()[19])
 if actual!=expected: raise ValueError('trace PID identity changed')
 os.kill(pid,signal.SIGTERM)
'''
            try:
                subprocess.run(['docker', 'exec', TRACE_CONTAINER, 'python3', '-c', program,
                                str(trace_owner['pid']), str(trace_owner['start_ticks'])],
                               check=True, timeout=15)
            except Exception as error:
                errors.append('targeted stop: ' + repr(error))
        if trace is not None and trace.poll() is None:
            try:
                trace.wait(timeout=25 if trace_owner is not None and not errors else 0)
            except subprocess.TimeoutExpired:
                try:
                    label = subprocess.check_output(
                        ['docker', 'inspect', '--format', '{{index .Config.Labels "q04-run"}}',
                         TRACE_CONTAINER], text=True, timeout=10).strip()
                    if label != runner.RUN_IDENTITY:
                        raise ValueError('trace container label changed')
                    subprocess.run(['docker', 'stop', '--time', '5', TRACE_CONTAINER],
                                   check=True, timeout=15)
                except Exception as error:
                    errors.append('fallback stop: ' + repr(error))
                try:
                    trace.wait(timeout=15)
                except Exception as error:
                    errors.append('trace wait: ' + repr(error))
        if trace is not None and trace.poll() not in (None, 0) and not errors:
            errors.append('object-stall trace exit ' + str(trace.returncode) + ': ' + trace.stderr.read())
    finally:
        if trace_log is not None:
            trace_log.close()
        try:
            inspected = subprocess.run(
                ['docker', 'inspect', '--format', '{{index .Config.Labels "q04-run"}}',
                 TRACE_CONTAINER], capture_output=True, text=True, timeout=10)
            if inspected.returncode == 0:
                if inspected.stdout.strip() != runner.RUN_IDENTITY:
                    raise ValueError('trace container label changed')
                subprocess.run(['docker', 'rm', '--force', TRACE_CONTAINER],
                               check=True, capture_output=True, text=True, timeout=15)
            elif 'no such object' not in inspected.stderr.lower():
                raise RuntimeError(inspected.stderr.strip())
            remaining = subprocess.check_output(
                ['docker', 'ps', '-a', '--filter', 'name=^/' + TRACE_CONTAINER + '$',
                 '--format', '{{.Names}}'], text=True, timeout=10).strip()
            if remaining:
                raise RuntimeError('trace container remains: ' + remaining)
        except Exception as error:
            errors.append('container removal: ' + repr(error))
        try:
            image = subprocess.check_output(
                ['docker', 'inspect', '--format', '{{.Config.Image}}', runner.topology.NODE],
                text=True, timeout=15).strip()
            cleanup = ('mount -t tracefs tracefs /sys/kernel/tracing; '
                       'd=/sys/kernel/tracing/instances/$1; '
                       'if [ -d "$d" ]; then echo 0 > "$d/tracing_on"; '
                       'echo nop > "$d/current_tracer"; rmdir "$d"; fi; test ! -e "$d"')
            subprocess.run(
                ['docker', 'run', '--rm', '--pull=never', '--network=none', '--privileged',
                 '--read-only', '--entrypoint', 'sh', image, '-c', cleanup, 'cleanup',
                 TRACE_INSTANCE], check=True, timeout=20)
        except Exception as error:
            errors.append('trace instance removal: ' + repr(error))
    if errors:
        raise RuntimeError('; '.join(errors))



try:
    runner.offline_check()
    assert runner.topology.NODE == "internal-a2a-vs6-local-worker"
    base.NODE = "internal-a2a-vs6-local-worker2"  # Reads shared VM pressure through object node; not independent capacity.
    record["worker_node"] = runner.topology.NODE
    record["outer_guard_node"] = base.NODE
    if runner.OUT.exists() or runner.OBJECT_OUT.exists():
        raise FileExistsError('fresh DH output already exists')
    rows = current()
    if any(x['spec'].get('replicas', 1) != 0 or x['status'].get('readyReplicas', 0) != 0
           for x in rows):
        raise ValueError('recorded Deployments are not all held at zero')
    runner.object_trial.deployment(kube)
    base.t09a_health(kube, OUT / 'health-before-candidate.json', require_idle=True)
    object_snapshot = retained_object(runner, kube)
    pvc_before = kube.json('get', 'pvc', 'object-data')
    record['object_pvc_before'] = {'uid': pvc_before['metadata']['uid'],
                                  'volume': pvc_before['spec']['volumeName']}
    (OUT / 'object-before.json').write_text(json.dumps(object_snapshot, indent=2) + '\n')
    replacement = object_snapshot['pod']
    record['retained_object'] = object_snapshot
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
    start_trace()
    native_trace = start_native(kube, replacement['pod_name'], OUT / 'native-traffic.jsonl', runner.PREFIX)
    identify = """from pathlib import Path
import json,sys
rows=[]
for p in Path('/proc').glob('[0-9]*'):
 try:
  if sys.argv[1] in (p/'cgroup').read_text() and (p/'comm').read_text().strip()=='minio':
   rows.append({'pid':int(p.name),'argv':(p/'cmdline').read_bytes().decode().split('\\0')[:-1]})
 except (FileNotFoundError,ProcessLookupError): pass
print(json.dumps(rows))
"""
    record['server_processes'] = json.loads(subprocess.check_output(
        ['docker', 'exec', TRACE_CONTAINER, 'python3', '-c', identify,
         replacement['container_id']], text=True, timeout=10))
    if (len(record['server_processes']) != 1
            or record['server_processes'][0]['argv'] != ['minio', 'server', '/data']):
        raise ValueError('exact MinIO server process not identified')
    command = shlex.split(runner.exact_command())
    record['runner_command'] = command
    with (OUT / 'workload-controller.log').open('x') as log:
        record['runner_started_at'] = time.time()
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        started = time.monotonic()
        interrupted_at = None
        while process.poll() is None:
            try:
                native_trace.check()
                verify_observer(observer, OUT / 'node-psi-attribution.jsonl')
                proofs = terminal_proofs(
                    runner.OUT, baseline['vm_oom_kill'],
                    base.VM_RUNTIME_FLOOR_BYTES, base.CGROUP_GUARD_BYTES)
                row = sample()
                # A4 records runtime node PSI; the shared helper still enforces floor/OOM.
                psi_telemetry = runtime_psi_is_telemetry(
                    row, baseline['vm_oom_kill'], base.VM_RUNTIME_FLOOR_BYTES, True)
                if proofs is not None:
                    record.setdefault('terminal_vm_guard_boundary', {
                        'observed_at': time.time(), 'proofs': proofs})
                    if psi_telemetry:
                        record.setdefault('post_terminal_vm_pressure', []).append(
                            record['samples'][-1])
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
    lifecycle = finish_native(native_trace, kube, runner.PREFIX)
    (OUT / 'native-trace-lifecycle.json').write_text(json.dumps(lifecycle, indent=2) + '\n')
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
    if native_trace is not None:
        try:
            native_trace.close()
        except Exception as error:
            record['restoration_errors'].append('native trace stop: ' + repr(error))
    try:
        stop_trace()
    except Exception as error:
        record['restoration_errors'].append('object trace stop: ' + repr(error))
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
    try:
        after = retained_object(runner, kube)
        if object_snapshot is not None and after != object_snapshot:
            raise ValueError('retained object identity or configuration changed')
        record['minio_after'] = after
    except Exception as error:
        record['restoration_errors'].append('object-service final read: ' + repr(error))
        record['status'] = 'qualification_failed'
    record['finished_at'] = time.time()
    (OUT / 'held-topology-controller.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({key: record.get(key) for key in
          ('status', 'run_id', 'runner_exit_code', 'restoration',
           'restoration_errors', 'minio_after')}))

raise SystemExit(0 if record.get('status') == 'runner_passed' and
                 record.get('restoration') == 'verified_zero_replicas_and_no_owned_pods' and
                 not record['restoration_errors'] else 1)
