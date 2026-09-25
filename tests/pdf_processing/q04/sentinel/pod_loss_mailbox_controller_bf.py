"""Host-owned mailbox actions for the one BF Activity Pod-loss run."""

import json
from pathlib import Path
import subprocess
import time

import pod_topology_bf as topology
from sentinel import pod_loss_transition_bf as transition
from sentinel import run_yolo_pod_cgroup_p as reviewed


RUN_ID = 'q04-pod-loss-pod-cgroup-20260925-bf'
PHASE = 'pod-loss-pod-cgroup-bf'
EVIDENCE = '/q04-evidence/' + topology.EVIDENCE_DIRECTORY_NAME
CONTROL = EVIDENCE + '/pod-loss-control'
ROOT = EVIDENCE + '/state/' + PHASE


class MailboxController:
    def __init__(self, kube, coordinator: dict, deployment: dict,
                 worker_pod: dict, output: Path, *, deadline: float,
                 check_abort=lambda: None):
        self.kube = kube
        self.coordinator = coordinator
        self.deployment = deployment
        self.worker_pod = worker_pod
        self.output = output
        self.deadline = deadline
        self.check_abort = check_abort
        self.worker_transports = []
        self.handled = set()
        self.transition_started = None
        self.transition_kind = None

    def request(self, kind: str, generation: int):
        name = f'{generation}-{kind}'
        program = ("import json;from pathlib import Path;"
                   "p=Path(" + repr(CONTROL + '/' + name + '.request.json') + ");"
                   "print(p.read_text() if p.exists() else '{}')")
        value = json.loads(self.kube.exec_python(self.coordinator['pod_name'], program,
            timeout=reviewed.remaining_timeout(self.deadline, 10, 'mailbox read')))
        if not value:
            return None
        if (value.get('run_id') != RUN_ID or value.get('kind') != kind
                or value.get('generation') != generation
                or not isinstance(value.get('requested_at'), (float, int))):
            raise ValueError('Pod-loss mailbox request identity changed')
        return value

    def reply(self, kind: str, generation: int, details: dict):
        self.check_abort()
        value = {'run_id': RUN_ID, 'kind': kind, 'generation': generation,
                 'status': 'PASS', **details}
        name = f'{generation}-{kind}.reply.json'
        program = ("import json,sys;from pathlib import Path;"
                   "sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
                   "from pod_durable_evidence import write_once;"
                   "write_once(Path(" + repr(CONTROL + '/' + name) + "),"
                   "json.loads(sys.stdin.read()),volume_root=Path(" + repr(EVIDENCE) + "))")
        self.kube.run(['exec', '-i', self.coordinator['pod_name'], '--',
            '/experiment/.venv/bin/python', '-c', program],
            input=json.dumps(value),
            timeout=reviewed.remaining_timeout(self.deadline, 15, 'mailbox reply'))
        self.handled.add((kind, generation))

    def _verify_worker_pod(self, pod: dict):
        live = reviewed.validate_pod(
            self.kube.json('get', 'pod', pod['pod_name']),
            run_label=topology.RUN_LABEL, node_name=topology.NODE,
            image=topology.IMAGE)
        if (live['pod_uid'] != pod['pod_uid']
                or live['container_id'] != pod['container_id']):
            raise ValueError('Activity Pod UID/container changed')

    def _worker_proof(self, pod: dict, generation: int) -> dict:
        directory = ROOT + f'/worker-{generation}'
        program = """import hashlib,json,psutil,sys,time
from pathlib import Path
directory=Path(sys.argv[1]);ready_raw=(directory/'ready.json').read_bytes();ready=json.loads(ready_raw)
with (directory/'samples.jsonl').open('rb') as stream:first=stream.readline()
assert first.endswith(b'\\n')
sample=json.loads(first)
assert ready['generation']==sample['generation']==int(sys.argv[2])
assert sample['time']<=ready['time'] and 0<=time.time()-ready['time']<=1
assert ready['config_sha256']==hashlib.sha256((directory.parent/'config.json').read_bytes()).hexdigest()
worker=psutil.Process(ready['pid'])
assert worker.create_time()==ready['created'] and any('q04/worker_bc.py' in arg for arg in worker.cmdline())
print(json.dumps({'worker_pid':ready['pid'],'worker_created':ready['created'],
 'ready_sha256':hashlib.sha256(ready_raw).hexdigest(),
 'first_sample_sha256':hashlib.sha256(first).hexdigest()}))
"""
        return json.loads(self.kube.run(['exec', pod['pod_name'], '--',
            '/experiment/.venv/bin/python', '-c', program,
            directory, str(generation)],
            timeout=reviewed.remaining_timeout(self.deadline, 15, 'worker proof')))

    def start_worker(self, generation: int, pod: dict) -> dict:
        self.check_abort()
        self._verify_worker_pod(pod)
        command = self.kube.base + ['exec', pod['pod_name'], '--',
            '/experiment/.venv/bin/python', '-m', 'pod_activity_supervisor_bf',
            '--config', ROOT + '/config.json', '--root', ROOT,
            '--generation', str(generation)]
        log = (self.output / f'worker-{generation}-transport.log').open('x')
        transport = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        self.worker_transports.append((transport, log))
        deadline = min(self.deadline, time.time() + 90)
        ready_path = ROOT + f'/worker-{generation}/ready.json'
        ready_program = ("from pathlib import Path;print('yes' if Path("
                         + repr(ready_path) + ").exists() else 'no')")
        while time.time() < deadline:
            self.check_abort()
            if transport.poll() is not None:
                raise RuntimeError('Activity worker exited before readiness')
            if self.kube.exec_python(self.coordinator['pod_name'], ready_program,
                    timeout=reviewed.remaining_timeout(deadline, 10, 'worker readiness')).strip() != 'yes':
                time.sleep(.2)
                continue
            proof = self._worker_proof(pod, generation)
            self._verify_worker_pod(pod)
            return {'pod_uid': pod['pod_uid'], **proof}
        raise TimeoutError('Activity worker readiness deadline')

    def _stop_current_worker(self, generation: int):
        self.check_abort()
        measurement = ROOT + f'-measurement/worker-{generation}'
        program = ("import json,sys;from pathlib import Path;"
                   "sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
                   "from pod_durable_evidence import write_once;"
                   "write_once(Path(" + repr(measurement + '/stop-request.json') + "),"
                   "{'run_id':" + repr(RUN_ID) + ",'generation':" + str(generation)
                   + "},volume_root=Path(" + repr(EVIDENCE) + "))")
        self.kube.exec_python(self.coordinator['pod_name'], program,
            timeout=reviewed.remaining_timeout(self.deadline, 15, 'worker stop request'))
        expected = ROOT + f'/worker-{generation}/stopped.json'
        summary = measurement + '/resource-attribution-summary.json'
        gate = measurement + '/all-sample-resource-gate.json'
        check = ("import json;from pathlib import Path;"
            "a=Path(" + repr(expected) + ");b=Path(" + repr(summary)
            + ");c=Path(" + repr(gate) + ");"
            "print('yes' if a.exists() and b.exists() and c.exists()"
            " and json.loads(a.read_text())['parser_absent']"
            " and json.loads(a.read_text())['scratch_absent']"
            " and json.loads(b.read_text())['attribution_complete']"
            " and json.loads(c.read_text())['status']=='PASS' else 'no')")
        stop_deadline = min(self.deadline, time.time() + 75)
        while time.time() < stop_deadline:
            self.check_abort()
            if self.kube.exec_python(self.coordinator['pod_name'], check).strip() == 'yes':
                return
            time.sleep(.2)
        raise TimeoutError('Activity worker did not stop')

    def process_once(self):
        self.check_abort()
        for kind, generation in (('stop', 0), ('drain', 2), ('start', 1)):
            if (kind, generation) in self.handled:
                continue
            request = self.request(kind, generation)
            if request is None:
                continue
            if kind == 'start':
                self.transition_started = time.time()
                self.transition_kind = kind
                try:
                    self.reply(kind, generation,
                               self.start_worker(1, self.worker_pod))
                finally:
                    self.transition_started = None
                    self.transition_kind = None
            elif kind == 'drain':
                self.transition_started = time.time()
                self.transition_kind = kind
                try:
                    replacement, proof = transition.drain_worker(
                        self.kube, self.deployment, self.worker_pod,
                        self.coordinator['pod_name'], request,
                        self.output / 'replacement', deadline=self.deadline,
                        check_abort=self.check_abort)
                    self.worker_pod = replacement
                    self.reply(kind, generation, {**proof,
                        **self.start_worker(2, replacement)})
                finally:
                    self.transition_started = None
                    self.transition_kind = None
            else:
                self.transition_started = time.time()
                self.transition_kind = kind
                try:
                    if self.worker_pod is not None:
                        worker_generation = 2 if ('drain', 2) in self.handled else 1
                        try:
                            self._stop_current_worker(worker_generation)
                        except (FileNotFoundError, subprocess.CalledProcessError):
                            pass
                        self.check_abort()
                        reviewed.cleanup_deployment_and_pod(
                            self.kube, self.deployment, self.worker_pod,
                            deadline=self.deadline,
                            deployment_name=topology.DEPLOYMENT,
                            namespace=topology.NAMESPACE, node_name=topology.NODE)
                    self.reply(kind, generation,
                        {'worker_absent': True, 'activity_pods_absent': True,
                         'emptydirs_absent': True})
                    self.worker_pod = None
                finally:
                    self.transition_started = None
                    self.transition_kind = None
            return kind
        return None
