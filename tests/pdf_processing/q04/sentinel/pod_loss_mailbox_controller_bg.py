"""Host-owned mailbox actions for the one BG Activity Pod-loss run."""

import json
from pathlib import Path
import subprocess
import time

import pod_topology_bg as topology
from sentinel import pod_loss_transition_bg as transition
from sentinel import run_yolo_pod_cgroup_p as reviewed


RUN_ID = 'q04-pod-loss-pod-cgroup-20260925-bg'
PHASE = 'pod-loss-pod-cgroup-bg'
EVIDENCE = '/q04-evidence/' + topology.EVIDENCE_DIRECTORY_NAME
CONTROL = EVIDENCE + '/pod-loss-control'
ROOT = EVIDENCE + '/state/' + PHASE


class MailboxController:
    def __init__(self, kube, coordinator: dict, deployment: dict,
                 worker_pod: dict, output: Path, *, deadline: float,
                 check_abort=lambda: None, bundle: Path | None = None,
                 capacity_path: Path | None = None):
        self.kube = kube
        self.coordinator = coordinator
        self.deployment = deployment
        self.worker_pod = worker_pod
        self.output = output
        self.deadline = deadline
        self.check_abort = check_abort
        self.bundle, self.capacity_path = bundle, capacity_path
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
        path = ROOT + f'-measurement/worker-{generation}/worker-proof.json'
        program = ("from pathlib import Path;print(Path(" + repr(path)
                   + ").read_text())")
        proof = json.loads(self.kube.exec_python(self.coordinator['pod_name'],
            program, timeout=reviewed.remaining_timeout(self.deadline, 15,
                'worker proof')))
        if (proof.get('generation') != generation
                or not 0 <= time.time() - proof['published_at'] <= 1):
            raise ValueError('Activity worker proof stale or wrong generation')
        return proof

    def start_worker(self, generation: int, pod: dict) -> dict:
        self.check_abort()
        self._verify_worker_pod(pod)
        command = self.kube.base + ['exec', pod['pod_name'], '--',
            '/experiment/.venv/bin/python', '-m', 'pod_activity_supervisor_bg',
            '--config', ROOT + '/config.json', '--root', ROOT,
            '--generation', str(generation)]
        log = (self.output / f'worker-{generation}-transport.log').open('x')
        transport = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        self.worker_transports.append((transport, log))
        deadline = min(self.deadline, time.time() + 90)
        ready_path = ROOT + f'-measurement/worker-{generation}/worker-proof.json'
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
            "ready=a.exists() and b.exists() and c.exists();"
            "status=json.loads(c.read_text())['status'] if ready else None;"
            "print('gate_failed' if ready and status!='PASS' else 'yes' if ready"
            " and json.loads(a.read_text())['parser_absent']"
            " and json.loads(a.read_text())['scratch_absent']"
            " and json.loads(b.read_text())['attribution_complete']"
            " else 'no')")
        stop_deadline = min(self.deadline, time.time() + 75)
        while time.time() < stop_deadline:
            self.check_abort()
            state = self.kube.exec_python(self.coordinator['pod_name'], check).strip()
            if state == 'gate_failed':
                raise ValueError('Activity Pod resource gate failed')
            if state == 'yes':
                return
            time.sleep(.2)
        raise TimeoutError('Activity worker did not stop')

    def prepare_replacement(self, pod: dict):
        """Populate the new Pod's emptyDir before its measured worker starts."""
        self.check_abort()
        self._verify_worker_pod(pod)
        if self.bundle is None or self.capacity_path is None:
            raise ValueError('replacement inputs unavailable')
        with (self.output / 'replacement-bundle-copy.log').open('x') as log:
            subprocess.run(self.kube.base + ['cp', str(self.bundle),
                pod['pod_name'] + ':/q04-control/inputs'],
                check=True, timeout=180, stdout=log, stderr=subprocess.STDOUT)
        for name, raw in (('capacity.json', self.capacity_path.read_bytes()),
                          ('pod-identity.json', json.dumps(pod).encode())):
            program = ("import sys;from pathlib import Path;"
                       "Path('/q04-control/" + name
                       + "').open('xb').write(sys.stdin.buffer.read())")
            self.kube.run(['exec', '-i', pod['pod_name'], '--',
                '/experiment/.venv/bin/python', '-c', program],
                input=raw.decode(),
                timeout=reviewed.remaining_timeout(self.deadline, 30,
                    'replacement input staging'))
        self._verify_worker_pod(pod)
        self.check_abort()

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
                    self.prepare_replacement(replacement)
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
