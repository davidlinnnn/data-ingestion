"""One controlled, in-flight Q04 Activity Pod-loss qualification window."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import threading
import time

Q04 = Path(__file__).resolve().parent.parent
if str(Q04) not in sys.path:
    sys.path.insert(0, str(Q04))

import pod_topology_bf as topology
from candidate.yolo_reviewed_window import evaluate_resource_gate
from sentinel import run_yolo_pod_cgroup_p as reviewed
from sentinel.object_monitor_bf import ObjectMonitor
from sentinel import object_limit_trial_bf as object_trial
from sentinel.pod_loss_mailbox_controller_bf import MailboxController
from telemetry import check_sample


PHASE = 'pod-loss-pod-cgroup-bf'
RUN_ID = 'q04-pod-loss-pod-cgroup-20260925-bf'
PREFIX = 'q04/pod-loss-pod-cgroup-20260925-bf/'
OUT = Path('/private/tmp/q04-pod-loss-pod-cgroup-20260925-bf')
EVIDENCE = '/q04-evidence/' + topology.EVIDENCE_DIRECTORY_NAME
CONTROL = '/q04-control'
BUNDLE = Path('/private/tmp/q04-inputs-warm-continuation-v3-ah')
V57 = Q04 / 'pod-topology-v57'
RUNNER_MANIFEST = V57 / 'RUNNER-MANIFEST.json'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def authorization_scope() -> dict:
    return {'phase': PHASE, 'run_identity': RUN_ID, 'prefix': PREFIX,
        'fixture': 'native', 'mode': 'in-flight Activity Pod loss',
        'automatic_retry': False, 'window_seconds': 1500,
        'outer_observation_seconds': 180, 'outer_continuous_seconds': 60,
        'outer_available_bytes': 4_831_838_208,
        'per_case_available_bytes': 3_221_225_472,
        'workload_seconds': 825, 'cleanup_seconds': 300,
        'sample_interval_seconds': .25, 'cgroup_guard_bytes': 4_294_967_296,
        'container_hard_limit_bytes': 5_368_709_120,
        'object_limit_bytes': object_trial.TRIAL_BYTES,
        'vm_runtime_floor_bytes': 1_610_612_736,
        'activity_deployment': topology.DEPLOYMENT,
        'coordinator_deployment': topology.COORDINATOR_DEPLOYMENT,
        'evidence_pvc': topology.EVIDENCE_PVC,
        'evidence_pvc_automatic_delete': False,
        'held_deployments_restored': False}


def authorization_scope_sha256() -> str:
    return sha(canonical(authorization_scope()))


def build_runner_manifest() -> dict:
    paths = {
        'runner': Path(__file__),
        'mailbox_controller': Path(__file__).with_name('pod_loss_mailbox_controller_bf.py'),
        'pod_transition': Path(__file__).with_name('pod_loss_transition_bf.py'),
        'object_monitor': Path(__file__).with_name('object_monitor_bf.py'),
        'object_probe': Path(__file__).with_name('object_cgroup_probe_bf.py'),
        'object_limit_trial': Path(__file__).with_name('object_limit_trial_bf.py'),
        'activity_supervisor': Q04 / 'pod_activity_supervisor_bf.py',
        'coordinator_supervisor': Q04 / 'pod_workload_bf.py',
        'coordinator_bridge': Q04 / 'pod_loss_bridge_bf.py',
        'candidate': Q04 / 'candidate/pod_loss_window_bf.py',
        'preflight': Q04 / 'pod_preflight_bf.py',
        'topology_builder': Q04 / 'pod_topology_bf.py',
        'topology': V57 / 'WORKER.yaml',
        'source_manifest': V57 / 'SOURCE-MANIFEST.json',
        'runtime_integration': V57 / 'RUNTIME-INTEGRATION-MANIFEST.json',
    }
    return {'phase': PHASE, 'run_identity': RUN_ID, 'prefix': PREFIX,
        'authorization_scope': authorization_scope(),
        'authorization_scope_sha256': authorization_scope_sha256(),
        'sources': {name: sha(path.read_bytes()) for name, path in paths.items()},
        'bundle_inputs_sha256': sha((BUNDLE / 'inputs.json').read_bytes()),
        'runtime_authorized': False, 'automatic_retry': False}


def offline_check() -> dict:
    topology.validate(json.loads((V57 / 'WORKER.yaml').read_text()))
    if json.loads((V57 / 'SOURCE-MANIFEST.json').read_text()) != topology.source_manifest():
        raise ValueError('BF source projection changed')
    manifest = json.loads((V57 / 'RUNTIME-INTEGRATION-MANIFEST.json').read_text())
    from candidate.pod_loss_window_bf import SCOPE
    if (manifest['authorization_scope'] != SCOPE
            or manifest['authorization_scope_sha256'] != sha(canonical(SCOPE))
            or manifest['identity'] != {'phase': PHASE, 'run_id': RUN_ID,
                                        'prefix': PREFIX}):
        raise ValueError('BF runtime integration identity changed')
    if json.loads(RUNNER_MANIFEST.read_text()) != build_runner_manifest():
        raise ValueError('BF host runner or projection source changed')
    return {'status': 'PASS_OFFLINE_ONLY',
        'authorization_scope_sha256': authorization_scope_sha256(),
        'source_manifest_sha256': sha((V57 / 'SOURCE-MANIFEST.json').read_bytes()),
        'topology_sha256': sha((V57 / 'WORKER.yaml').read_bytes())}


def stage_text(kube, pod: str, path: str, raw: bytes, *, evidence=False):
    if evidence:
        program = ("import json,sys;from pathlib import Path;"
                   "sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
                   "from pod_durable_evidence import write_once;"
                   "write_once(Path(" + repr(path) + "),json.loads(sys.stdin.read()),"
                   "volume_root=Path(" + repr(EVIDENCE) + "))")
        payload = raw.decode()
    else:
        program = ("import sys;from pathlib import Path;"
                   "Path(" + repr(path) + ").open('xb').write(sys.stdin.buffer.read())")
        payload = raw.decode()
    kube.run(['exec', '-i', pod, '--', '/experiment/.venv/bin/python', '-c', program],
             input=payload, timeout=30)


def scale(kube, deployment: dict, before: int, after: int):
    name = deployment['metadata']['name']
    current = kube.json('get', 'deployment', name)
    if current['metadata']['uid'] != deployment['metadata']['uid']:
        raise ValueError('run-owned Deployment UID changed')
    patch = reviewed.scale_patch(current['metadata']['uid'],
        current['metadata']['resourceVersion'], before, after)
    kube.run(['patch', 'deployment', name, '--type=json', '-p', json.dumps(patch)])


def await_coordinator(kube, deployment: dict, *, deadline: float) -> dict:
    observed_uid = None
    while time.time() < deadline:
        pods = kube.json('get', 'pods', '-l',
            'q04-run=' + topology.RUN_LABEL + '-coordinator')['items']
        if len(pods) > 1:
            raise ValueError('multiple run-owned coordinator Pods')
        if pods:
            pod = pods[0]
            metadata, spec, status = pod['metadata'], pod['spec'], pod['status']
            if observed_uid is not None and metadata['uid'] != observed_uid:
                raise ValueError('coordinator Pod UID changed during readiness')
            observed_uid = metadata['uid']
            reviewed.capture_cleanup_identity(kube, pod, deployment,
                run_label=topology.RUN_LABEL + '-coordinator', timeout=15)
            container = status.get('containerStatuses', [{}])[0]
            if (spec.get('nodeName') == topology.NODE
                    and status.get('phase') == 'Running'
                    and container.get('ready') is True):
                if (container.get('restartCount') != 0
                        or spec['containers'][0]['image'] != topology.IMAGE
                        or spec['containers'][0]['resources']
                        != topology.kubernetes_list()['items'][4]['spec']['template']['spec']['containers'][0]['resources']):
                    raise ValueError('coordinator Pod runtime contract changed')
                return {'pod_name': metadata['name'], 'pod_uid': metadata['uid'],
                        'container_id': container['containerID'],
                        'node': spec['nodeName']}
        time.sleep(.5)
    raise TimeoutError('run-owned coordinator Pod readiness deadline')


def preflight_argv(capacity: dict) -> list[str]:
    return ['/experiment/.venv/bin/python',
        '/workspace/tests/pdf_processing/q04/pod_preflight_bf.py',
        '--workspace', '/workspace', '--mount-root', '/q04-evidence',
        '--evidence-directory-name', topology.EVIDENCE_DIRECTORY_NAME,
        '--model-cache', '/experiment/PROTOTYPE-wipe-me/hf',
        '--provenance', '/workspace/tests/pdf_processing/q04/candidate/yolo-reviewed-b-fail/RETAINED-REPLAY.json',
        '--python', '/experiment/.venv/bin/python',
        '--pod-identity', CONTROL + '/pod-identity.json',
        '--capacity', CONTROL + '/capacity.json',
        '--source-manifest', CONTROL + '/source-manifest.json',
        '--bundle', CONTROL + '/inputs',
        '--authorization-scope-sha256', authorization_scope_sha256(),
        '--expected-bundle-sha256', sha((BUNDLE / 'inputs.json').read_bytes()),
        '--temporal', 'temporal:7233', '--endpoint', 'http://objects:9000',
        '--bucket', 't09a', '--prefix', PREFIX]


def workload_argv() -> list[str]:
    return ['/experiment/.venv/bin/python',
        '/workspace/tests/pdf_processing/q04/pod_workload_bf.py',
        '--prefix', PREFIX,
        '--authorization-scope-sha256', authorization_scope_sha256(),
        '--workload-seconds', '825', '--control', EVIDENCE,
        '--state', EVIDENCE + '/state', '--bundle', CONTROL + '/inputs',
        '--capacity', CONTROL + '/capacity.json',
        '--pod-temporal', 'temporal:7233',
        '--pod-objects', 'http://objects:9000', '--run-id', RUN_ID,
        '--workflow-queue', topology.WORKFLOW_QUEUE,
        '--activity-queue', topology.ACTIVITY_QUEUE]


def setup(kube, capacity: dict, owned: list[dict]):
    reviewed.run_outer_admission(kube, capacity)
    created = reviewed.create_owned_objects(
        kube, topology.kubernetes_list()['items'], owned)
    (OUT / 'created-object-specs.json').write_text(json.dumps(created, indent=2) + '\n')
    worker_deployment = reviewed.validate_created_deployment(
        kube.json('get', 'deployment', topology.DEPLOYMENT), owned,
        deployment_name=topology.DEPLOYMENT)
    coordinator_deployment = reviewed.validate_created_deployment(
        kube.json('get', 'deployment', topology.COORDINATOR_DEPLOYMENT), owned,
        deployment_name=topology.COORDINATOR_DEPLOYMENT)
    if (worker_deployment['spec']['replicas'] != 0
            or coordinator_deployment['spec']['replicas'] != 0):
        raise ValueError('new BF Deployments were not inactive')
    scale(kube, coordinator_deployment, 0, 1)
    coordinator = await_coordinator(kube, coordinator_deployment,
        deadline=time.time() + 120)
    scale(kube, worker_deployment, 0, 1)
    initial = OUT / 'initial-worker'
    initial.mkdir()
    worker, _ = reviewed.await_worker_pod(kube, worker_deployment, initial,
        run_label=topology.RUN_LABEL, node_name=topology.NODE,
        image=topology.IMAGE)
    pvc = kube.json('get', 'pvc', topology.EVIDENCE_PVC)
    pv = kube.json('get', 'pv', pvc['spec']['volumeName'])
    storage_class = kube.json('get', 'storageclass', 'standard')
    volume = reviewed.validate_evidence_volume(pvc, pv, storage_class)
    owned_pvc = next(row for row in owned if row['kind'] == 'PersistentVolumeClaim')
    if owned_pvc['uid'] != volume['pvc_uid']:
        raise ValueError('created evidence PVC UID changed')
    prepare = ("from pathlib import Path;import json,sys;"
        "sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
        "from pod_evidence_directory_d import prepare_run_directory;"
        "print(json.dumps(prepare_run_directory(Path('/q04-evidence'),"
        + repr(topology.EVIDENCE_DIRECTORY_NAME) + "),sort_keys=True))")
    volume['directory_contract'] = json.loads(
        kube.exec_python(coordinator['pod_name'], prepare))
    stage_text(kube, coordinator['pod_name'], EVIDENCE + '/evidence-volume-identity.json',
               json.dumps(volume).encode(), evidence=True)
    (OUT / 'evidence-volume-identity.json').write_text(json.dumps(volume, indent=2) + '\n')
    for pod in (coordinator['pod_name'], worker['pod_name']):
        with (OUT / f'{pod}-bundle-copy.log').open('x') as log:
            subprocess.run(kube.base + ['cp', str(BUNDLE),
                pod + ':' + CONTROL + '/inputs'],
                check=True, timeout=180, stdout=log, stderr=subprocess.STDOUT)
        stage_text(kube, pod, CONTROL + '/capacity.json',
                   (OUT / 'capacity.json').read_bytes())
    stage_text(kube, worker['pod_name'], CONTROL + '/source-manifest.json',
               (json.dumps(topology.source_manifest(), sort_keys=True) + '\n').encode())
    stage_text(kube, worker['pod_name'], CONTROL + '/pod-identity.json',
               (json.dumps(worker, sort_keys=True) + '\n').encode())
    preflight = json.loads(kube.run(['exec', worker['pod_name'], '--',
        *preflight_argv(capacity)], timeout=180))
    (OUT / 'pod-pre-inference-gates.json').write_text(
        json.dumps(preflight, indent=2) + '\n')
    stage_text(kube, worker['pod_name'], EVIDENCE + '/pre-inference-gates.json',
               json.dumps(preflight).encode(), evidence=True)
    if preflight.get('status') != 'PASS_PRE_INFERENCE':
        raise ValueError('BF pre-inference gate set did not pass')
    if time.time() + 825 + 300 > capacity['ends_at']:
        raise ValueError('insufficient fixed lease after BF preflight')
    return worker_deployment, coordinator_deployment, worker, coordinator, volume


class RuntimeMonitor:
    def __init__(self, kube, coordinator: dict, controller: MailboxController,
                 capacity: dict):
        self.kube, self.coordinator = kube, coordinator
        self.controller, self.capacity = controller, capacity
        self.stopping = threading.Event()
        self.error = None
        self.rows = []
        self.worker_initial = {}
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        channel = None
        try:
            command = self.kube.base + ['exec', '-i', self.coordinator['pod_name'],
                '--', '/experiment/.venv/bin/python']
            channel = reviewed.PersistentPython(command)
            node_program = reviewed.sample_program().replace(
                '/q04-evidence/q04-aima-pod-cgroup-20260920-p', EVIDENCE)
            if node_program == reviewed.sample_program():
                raise ValueError('node sampler evidence path not rebound')
            with (OUT / 'vm-controller.jsonl').open('x', buffering=1) as vm, \
                 (OUT / 'worker-observer.jsonl').open('x', buffering=1) as worker_stream:
                while not self.stopping.is_set():
                    row = json.loads(channel.run(node_program, timeout=10))
                    vm.write(json.dumps(row, sort_keys=True) + '\n')
                    self.rows.append(row)
                    reviewed.verify_runtime_sample(row,
                        self.capacity['expected_vm_oom_kill'])
                    if len(self.rows) > 1 and not 0 < row['time'] - self.rows[-2]['time'] <= 1:
                        raise ValueError('BF node VM telemetry gap')
                    if self.controller.transition_started is not None:
                        limit = 195 if self.controller.transition_kind == 'stop' else 120
                        if time.time() - self.controller.transition_started > limit:
                            raise TimeoutError('BF Pod transition exceeded approved bound')
                    elif ('start', 1) in self.controller.handled and ('stop', 0) not in self.controller.handled:
                        generation = 2 if ('drain', 2) in self.controller.handled else 1
                        path = EVIDENCE + f'/state/{PHASE}/worker-{generation}/samples.jsonl'
                        program = ("import json,sys;from pathlib import Path;"
                            "sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
                            "from telemetry import read_rows;"
                            "rows=read_rows(Path(" + repr(path) + "));"
                            "print(json.dumps(rows[-1] if rows else {}))")
                        observed = json.loads(channel.run(program, timeout=10))
                        if (observed.get('generation') != generation
                                or not 0 <= time.time() - observed['time'] <= 1):
                            raise ValueError('BF worker resource telemetry stale')
                        initial = self.worker_initial.setdefault(generation, observed)
                        check_sample(observed, initial, self.capacity)
                        worker_stream.write(json.dumps(observed, sort_keys=True) + '\n')
                        attribution_path = (EVIDENCE + f'/state/{PHASE}-measurement/'
                                            f'worker-{generation}/resource-attribution.jsonl.inflight')
                        attribution_program = ("import json,sys;from pathlib import Path;"
                            "sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
                            "from telemetry import read_rows;"
                            "rows=read_rows(Path(" + repr(attribution_path) + "));"
                            "print(json.dumps(rows[-1] if rows else {}))")
                        attribution = json.loads(channel.run(attribution_program, timeout=10))
                        if (attribution.get('attribution_complete') is not True
                                or not 0 <= time.time() - attribution['time'] <= 1):
                            raise ValueError('BF Activity Pod process attribution stale/incomplete')
                    self.stopping.wait(.25)
        except BaseException as error:
            self.error = error
            self.stopping.set()
        finally:
            if channel is not None:
                try:
                    channel.close()
                except BaseException as error:
                    self.error = self.error or error
                    self.stopping.set()

    def stop(self):
        self.stopping.set()
        self.thread.join(timeout=15)
        if self.thread.is_alive():
            raise TimeoutError('BF runtime monitor did not stop')
        if self.error is not None:
            raise self.error
        if not self.rows:
            raise ValueError('BF node telemetry never started')


def export_evidence(kube, coordinator: dict, volume: dict, *, success: bool):
    pod = coordinator['pod_name']
    fingerprint = reviewed.archive_fingerprint_program().replace(
        '/q04-evidence/q04-aima-pod-cgroup-20260920-p', EVIDENCE)
    before = json.loads(kube.exec_python(pod, fingerprint, timeout=30))
    archive = OUT / ('pod-control-evidence.tar' if success else 'failure-evidence.tar')
    with archive.open('xb') as stream, (OUT / 'evidence-tar.log').open('x') as errors:
        subprocess.run(kube.base + ['exec', pod, '--', 'tar', 'cf', '-',
            '-C', EVIDENCE, '.'], check=True, timeout=120,
            stdout=stream, stderr=errors)
    after = json.loads(kube.exec_python(pod, fingerprint, timeout=30))
    if before != after:
        raise ValueError('BF evidence changed during export')
    reviewed.verify_local_archive(archive, before)
    with tarfile.open(archive) as tar:
        terminal = tar.extractfile('./durable-terminal-manifest.json')
        if success and terminal is None:
            raise ValueError('BF durable terminal evidence missing')
        if terminal is not None:
            value = json.load(terminal)
            if value['volume_identity'] != volume:
                raise ValueError('BF terminal PVC identity changed')
            if success and not (value['workload_succeeded']
                                and value['cleanup_complete']):
                raise ValueError('BF terminal workload or cleanup not complete')
    (OUT / 'archive-fingerprint.json').write_text(json.dumps(before, indent=2) + '\n')
    return archive


def readback_objects(kube, coordinator: dict) -> dict:
    program = """import boto3,hashlib,json
prefix='q04/pod-loss-pod-cgroup-20260925-bf/'
s3=boto3.client('s3',endpoint_url='http://objects:9000')
listed=[]
for page in s3.get_paginator('list_objects_v2').paginate(Bucket='t09a',Prefix=prefix):
 listed.extend(page.get('Contents',[]))
assert listed and all(item['Key'].startswith(prefix) for item in listed)
objects=[]
for item in listed:
 response=s3.get_object(Bucket='t09a',Key=item['Key'])
 digest=hashlib.sha256();size=0
 for chunk in response['Body'].iter_chunks(chunk_size=1048576):
  digest.update(chunk);size+=len(chunk)
 assert size==item['Size']==response['ContentLength']
 assert response['ETag']==item['ETag']
 objects.append({'key':item['Key'],'bytes':size,'sha256':digest.hexdigest(),
  'etag':item['ETag']})
again=[]
for page in s3.get_paginator('list_objects_v2').paginate(Bucket='t09a',Prefix=prefix):
 again.extend((item['Key'],item['Size'],item['ETag']) for item in page.get('Contents',[]))
assert sorted(again)==sorted((item['Key'],item['Size'],item['ETag']) for item in listed)
print(json.dumps({'prefix':prefix,'bucket':'t09a','objects':objects},sort_keys=True))
"""
    value = json.loads(kube.exec_python(coordinator['pod_name'], program,
        timeout=180))
    if (value.get('prefix') != PREFIX or value.get('bucket') != 't09a'
            or not value.get('objects')
            or any(not row['key'].startswith(PREFIX)
                   or row['bytes'] < 0 or len(row['sha256']) != 64
                   for row in value['objects'])):
        raise ValueError('BF independent object readback incomplete')
    (OUT / 'object-readback.json').write_text(json.dumps(value, indent=2) + '\n')
    return {'objects': len(value['objects']),
            'bytes': sum(row['bytes'] for row in value['objects']),
            'inventory_sha256': sha(canonical(value['objects']))}


def validate_old_resource_rows(rows: list[dict]):
    # The deleted Pod cannot write terminal cleanup markers or a summary. Reuse
    # the unchanged per-sample resource gate without treating those as a pass.
    gate = evaluate_resource_gate(rows, {},
                                  limit_bytes=authorization_scope()['cgroup_guard_bytes'])
    if any(gate[name] for name in (
            'incomplete_sample_indexes', 'memory_violations',
            'oom_violations', 'psi_violations')):
        raise ValueError('BF old Pod all-sample resource gate failed')


def validate_archive(archive: Path) -> dict:
    with tarfile.open(archive) as tar:
        files = {member.name.removeprefix('./'): tar.extractfile(member).read()
                 for member in tar.getmembers() if member.isfile()}
    def record(name):
        return json.loads(files[name])
    manifest = record('durable-terminal-manifest.json')
    inventory = manifest['inventory']
    for item in inventory:
        raw = files[item['path']]
        if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
            raise ValueError('BF terminal inventory member changed')
    phase = f'state/{PHASE}/'
    accepted = record(phase + 'drain-native/accepted.json')
    drain = record(phase + 'drain-native/drain.json')
    retry = record(phase + 'drain-native/drain-proof.json')
    request = record('pod-loss-control/2-drain.request.json')
    reply = record('pod-loss-control/2-drain.reply.json')
    stop = record('pod-loss-control/0-stop.reply.json')
    expected = record('state/config.json')
    fixed = record('pod-loss-control/1-start.reply.json')
    if (accepted['result']['status'] != 'complete'
            or not accepted['result']['processing_complete']
            or accepted['result']['registered_pages'] != 51
            or accepted['result']['registered_components'] != 7
            or accepted['accepted']['document_sha256']
            != '70673bdc5cb548d37c81efa91bb1c5460f71f94148bdb5d1218a319c6af9f152'
            or accepted['accepted']['checks']['full_reference_graph_sha256']
            != '9f1b0ef9ed561df0c4a5748d5c49554e8f5ad3bb38764d94a51d3433f4d94972'
            or drain['scope'] != 'owned_pod'
            or retry['retried_range'] != [6, 10] or retry['attempt'] != 2
            or len(retry['retained']) != 1
            or reply['old_pod_uid'] != fixed['pod_uid']
            or reply['pod_uid'] == fixed['pod_uid']
            or not reply['old_runtime_absent'] or not reply['old_scratch_absent']
            or not stop['activity_pods_absent'] or not stop['emptydirs_absent']
            or expected['run_id'] != RUN_ID):
        raise ValueError('BF native Pod-loss business or cleanup proof incomplete')
    old_samples = [json.loads(line) for line in
        files[phase + 'worker-1/samples.jsonl'].splitlines(keepends=True)
        if line.endswith(b'\n')]
    new_samples = [json.loads(line) for line in
        files[phase + 'worker-2/samples.jsonl'].splitlines(keepends=True)
        if line.endswith(b'\n')]
    for generation, rows in ((1, old_samples), (2, new_samples)):
        if (len(rows) < 2 or any(row['generation'] != generation for row in rows)
                or any(not 0 < later['time'] - earlier['time'] <= 1
                       for earlier, later in zip(rows, rows[1:]))):
            raise ValueError('BF worker resource sample coverage incomplete')
        for row in rows:
            check_sample(row, rows[0], expected['window'])
    if old_samples[-1]['time'] < request['requested_at']:
        raise ValueError('BF old worker resource coverage ended before Pod deletion')
    old_raw = files[f'state/{PHASE}-measurement/worker-1/'
                    'resource-attribution.jsonl.inflight']
    old_rows = [json.loads(line) for line in old_raw.splitlines(keepends=True)
                if line.endswith(b'\n')]
    if (len(old_rows) < 2
            or any(row['attribution_complete'] is not True for row in old_rows)
            or any(not 0 < later['time'] - earlier['time'] <= 1
                   for earlier, later in zip(old_rows, old_rows[1:]))
            or old_rows[-1]['time'] < request['requested_at']):
        raise ValueError('BF old Pod process attribution incomplete')
    validate_old_resource_rows(old_rows)
    measurement = f'state/{PHASE}-measurement/worker-2/'
    summary = record(measurement + 'resource-attribution-summary.json')
    gate = record(measurement + 'all-sample-resource-gate.json')
    if (not summary['process_attribution_complete']
            or not summary['qualification_complete']
            or not summary['cgroup_resource_complete']
            or gate['status'] != 'PASS'):
        raise ValueError('BF replacement Pod process/resource attribution incomplete')
    return {'status': 'PASS', 'pages': 51,
            'old_pod_uid': fixed['pod_uid'], 'new_pod_uid': reply['pod_uid'],
            'old_process_samples': len(old_rows),
            'old_uncommitted_tail_bytes': len(old_raw) -
                sum(len(line) for line in old_raw.splitlines(keepends=True)
                    if line.endswith(b'\n')),
            'new_process_samples': summary['samples']}


def cleanup_owned_deployments(kube, owned: list[dict], *, deadline: float,
                              errors: dict | None = None,
                              names: tuple[str, ...] | None = None) -> dict:
    result = {}
    errors = errors if errors is not None else {}
    for name, label in ((topology.DEPLOYMENT, topology.RUN_LABEL),
                        (topology.COORDINATOR_DEPLOYMENT,
                         topology.RUN_LABEL + '-coordinator')):
        if names is not None and name not in names:
            continue
        owner = next((row for row in owned
                      if row['kind'] == 'Deployment' and row['name'] == name), None)
        if owner is None:
            continue
        try:
            deployment = kube.json('get', 'deployment', name)
            if deployment['metadata']['uid'] != owner['uid']:
                raise ValueError('owned Deployment UID changed during cleanup')
            pods = kube.json('get', 'pods', '-l', 'q04-run=' + label)['items']
            identities = [reviewed.capture_cleanup_identity(kube, pod, deployment,
                          run_label=label) for pod in pods]
            if identities:
                for identity in identities:
                    result[name] = reviewed.cleanup_deployment_and_pod(kube,
                        deployment, identity, deadline=deadline,
                        deployment_name=name, namespace=topology.NAMESPACE,
                        node_name=topology.NODE)
            else:
                scale(kube, deployment, deployment['spec'].get('replicas', 0), 0)
                result[name] = {'deployment_scaled_zero': True, 'pods_observed': 0}
            if kube.json('get', 'pods', '-l', 'q04-run=' + label)['items']:
                raise ValueError('run-owned Pod remained after cleanup')
        except BaseException as error:
            errors['run_owned_pods:' + name] = repr(error)
    return result


def execute(args):
    offline_check()
    if json.loads(RUNNER_MANIFEST.read_text())['runtime_authorized'] is not True:
        raise RuntimeError('BF runtime awaits complete observer/cleanup review')
    if args.authorization_scope_sha256 != authorization_scope_sha256():
        raise ValueError('BF authorization scope digest changed')
    reviewed.PHASE = PHASE
    reviewed.RUN_IDENTITY = RUN_ID
    reviewed.PREFIX = PREFIX
    reviewed.OUT = OUT
    reviewed.EVIDENCE = EVIDENCE
    reviewed.EVIDENCE_DIRECTORY_NAME = topology.EVIDENCE_DIRECTORY_NAME
    reviewed.NAMESPACE = topology.NAMESPACE
    reviewed.NODE = topology.NODE
    reviewed.DEPLOYMENT = topology.DEPLOYMENT
    reviewed.RUN_LABEL = topology.RUN_LABEL
    reviewed.pod_topology = topology
    reviewed.authorization_scope_sha256 = authorization_scope_sha256
    OUT.mkdir(exist_ok=False)
    capacity = reviewed.build_capacity(
        starts_at=time.time(), owner=args.owner,
        approval_reference=args.approval_reference)
    (OUT / 'capacity.json').write_text(json.dumps(capacity, indent=2) + '\n')
    kube = reviewed.Kubectl()
    owned = []
    trial = None
    worker_deployment = coordinator_deployment = None
    worker = coordinator = volume = None
    controller = monitor = object_monitor = workload = None
    primary = None
    success = False
    try:
        reviewed.verify_held_deployments(kube)
        reviewed.t09a_health(kube, OUT / 'health-before-object-trial.json',
                            require_idle=True)
        trial = object_trial.capture(kube)
        (OUT / 'object-trial-before.json').write_text(json.dumps(trial, indent=2) + '\n')
        object_trial.enter(kube, trial, deadline=min(time.time() + 120,
                                                    capacity['ends_at'] - 300))
        (OUT / 'object-trial-entered.json').write_text(json.dumps(trial, indent=2) + '\n')
        (worker_deployment, coordinator_deployment,
         worker, coordinator, volume) = setup(kube, capacity, owned)
        deadline = min(capacity['ends_at'] - 300, time.time() + 825)
        def check_monitor():
            if monitor is not None and monitor.error is not None:
                raise monitor.error
            if object_monitor is not None and object_monitor.error is not None:
                raise object_monitor.error
        controller = MailboxController(kube, coordinator, worker_deployment,
                                       worker, OUT, deadline=deadline,
                                       check_abort=check_monitor, bundle=BUNDLE,
                                       capacity_path=OUT / 'capacity.json')
        monitor = RuntimeMonitor(kube, coordinator, controller, capacity)
        object_monitor = ObjectMonitor(kube, OUT / 'object-pressure.jsonl',
            authorization_scope()['object_limit_bytes'])
        (OUT / 'object-observer-start.json').write_text(json.dumps(
            object_monitor.start(seconds=int(capacity['ends_at'] - time.time())),
            indent=2) + '\n')
        workload = subprocess.Popen(kube.base + ['exec', coordinator['pod_name'],
            '--', *workload_argv()],
            stdout=(OUT / 'workload-transport.log').open('x'),
            stderr=subprocess.STDOUT)
        monitor.start()
        while workload.poll() is None:
            check_monitor()
            controller.process_once()
            if time.time() >= deadline:
                raise TimeoutError('BF workload deadline')
            time.sleep(.1)
        check_monitor()
        if workload.returncode != 0:
            raise RuntimeError('BF workload failed; no retry')
        if controller.handled != {('start', 1), ('drain', 2), ('stop', 0)}:
            raise ValueError('BF complete Pod transition sequence not observed')
        reviewed.verify_held_deployments(kube)
        archive = export_evidence(kube, coordinator, volume, success=True)
        (OUT / 'independent-verification.json').write_text(
            json.dumps(validate_archive(archive), indent=2) + '\n')
        (OUT / 'object-readback-summary.json').write_text(json.dumps(
            readback_objects(kube, coordinator), indent=2) + '\n')
        check_monitor()
        monitor.stop()
        (OUT / 'object-observer-summary.json').write_text(json.dumps(
            object_monitor.stop(), indent=2) + '\n')
        success = True
    except BaseException as error:
        primary = error
        (OUT / 'controller-stop.json').write_text(json.dumps({
            'time': time.time(), 'type': type(error).__name__,
            'reason': str(error), 'automatic_retry': False}, indent=2) + '\n')
    finally:
        cleanup = {'primary_error': repr(primary) if primary else None,
                   'errors': {}, 'retained': []}
        if monitor is not None:
            try:
                monitor.stop()
            except BaseException as error:
                cleanup['errors']['monitor'] = repr(error)
        if object_monitor is not None and object_monitor.process is not None:
            try:
                if not object_monitor.cleaned:
                    cleanup['object_observer'] = object_monitor.stop()
            except BaseException as error:
                cleanup['errors']['object_observer'] = repr(error)
        if workload is not None and workload.poll() is None:
            try:
                stop_program = reviewed.stop_owned_supervisor_program(120).replace(
                    '/q04-evidence/q04-aima-pod-cgroup-20260920-p', EVIDENCE)
                kube.exec_python(coordinator['pod_name'], stop_program, timeout=135)
            except BaseException as error:
                cleanup['errors']['supervisor_stop'] = repr(error)
            try:
                reviewed.stop_transport_process(workload,
                    recovery_deadline=capacity['ends_at'] - 120)
            except BaseException as error:
                cleanup['errors']['workload_transport'] = repr(error)
        cleanup['deployments'] = {}
        if not success:
            try:
                cleanup['deployments'].update(cleanup_owned_deployments(
                    kube, owned, deadline=capacity['ends_at'] - 90,
                    errors=cleanup['errors'], names=(topology.DEPLOYMENT,)))
            except BaseException as error:
                cleanup['errors']['worker_cleanup'] = repr(error)
        if coordinator is not None and volume is not None and not success:
            try:
                export_evidence(kube, coordinator, volume, success=False)
            except BaseException as error:
                cleanup['errors']['failure_evidence'] = repr(error)
        try:
            cleanup['deployments'].update(cleanup_owned_deployments(
                kube, owned, deadline=capacity['ends_at'] - 90,
                errors=cleanup['errors'], names=(topology.COORDINATOR_DEPLOYMENT,)
                if not success else None))
        except BaseException as error:
            cleanup['errors']['run_owned_pods'] = repr(error)
        if owned and not any(key.startswith('run_owned_pods') for key in cleanup['errors']):
            try:
                objects = reviewed.delete_owned_objects(kube, owned,
                    deadline=capacity['ends_at'] - 60)
                cleanup['object_cleanup'] = objects
                cleanup['retained'] = objects['retained']
                cleanup['errors'].update(objects['errors'])
            except BaseException as error:
                cleanup['errors']['object_cleanup'] = repr(error)
        if trial is not None:
            try:
                cleanup['object_trial_restoration'] = object_trial.restore(
                    kube, trial, deadline=capacity['ends_at'] - 30)
            except BaseException as error:
                cleanup['errors']['object_trial_restoration'] = repr(error)
        try:
            reviewed.verify_held_deployments(kube)
            reviewed.t09a_health(kube, OUT / 'health-after.json', require_idle=True)
        except BaseException as error:
            cleanup['errors']['cluster_health'] = repr(error)
        (OUT / 'outer-cleanup.json').write_text(json.dumps(cleanup, indent=2) + '\n')
    if primary is not None:
        raise primary
    if cleanup['errors']:
        raise RuntimeError('BF terminal cleanup incomplete: ' + repr(cleanup['errors']))
    return {'status': 'PASS', 'archive': str(OUT / 'pod-control-evidence.tar')}


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--offline-check', action='store_true')
    cli.add_argument('--execute', action='store_true')
    cli.add_argument('--owner')
    cli.add_argument('--approval-reference')
    cli.add_argument('--authorization-scope-sha256')
    args = cli.parse_args(argv)
    if args.offline_check and not args.execute:
        print(json.dumps(offline_check(), indent=2))
        return 0
    if not (args.execute and args.owner and args.approval_reference):
        cli.error('execution requires explicit owner, approval reference and scope digest')
    print(json.dumps(execute(args), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
