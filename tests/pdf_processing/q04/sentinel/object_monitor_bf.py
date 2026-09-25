"""Own one read-only exact MinIO cgroup observer in the existing kind node."""

import json
from pathlib import Path
import subprocess
import threading
import time

from sentinel import object_cgroup_probe_bf as probe


NODE = 'internal-a2a-vs6-local-worker2'
RUN_ID = 'q04-pod-loss-pod-cgroup-20260925-bf'


def object_identity(kube, expected_max: int) -> dict:
    pods = kube.json('get', 'pods', '-l', 'app=pdf-objects')['items']
    if len(pods) != 1:
        raise ValueError('exact object-service Pod count changed')
    pod = pods[0]
    container = pod['status']['containerStatuses'][0]
    if (pod['spec']['nodeName'] != NODE
            or pod['status']['phase'] != 'Running'
            or container.get('ready') is not True
            or container.get('restartCount') != 0
            or len(pod['spec']['containers']) != 1
            or pod['spec']['containers'][0]['resources']['limits']['memory']
            != str(expected_max // 1048576) + 'Mi'
            or expected_max % 1048576
            or not container['containerID'].startswith('containerd://')):
        raise ValueError('object-service Pod placement or memory contract changed')
    return {'pod_name': pod['metadata']['name'],
        'pod_uid': pod['metadata']['uid'],
        'container_id': container['containerID'].removeprefix('containerd://'),
        'memory_max': expected_max, 'node': NODE}


def stop_program(identity: dict, start: dict) -> str:
    return """import os,signal,sys
from pathlib import Path
pid,ticks,run_id,pod_uid,container_id=sys.argv[1:]
pid=int(pid);ticks=int(ticks)
raw=(Path('/proc')/str(pid)/'stat').read_text()
assert int(raw.rsplit(') ',1)[1].split()[19])==ticks
command=(Path('/proc')/str(pid)/'cmdline').read_bytes().replace(b'\\0',b' ')
assert b'Read exact object-container cgroup' in command
assert all(value.encode() in command for value in (run_id,pod_uid,container_id))
os.kill(pid,signal.SIGTERM)
print('stop-sent')
"""


FIND_AND_STOP = """import os,signal,sys
from pathlib import Path
run_id,pod_uid,container_id=sys.argv[1:]
matches=[]
for path in Path('/proc').glob('[0-9]*/cmdline'):
 try: args=path.read_bytes().split(b'\\0')
 except (FileNotFoundError,PermissionError): continue
 if len(args)>4 and b'-u' in args and b'-c' in args and all(
   value.encode() in b' '.join(args) for value in (run_id,pod_uid,container_id)) and any(
   b'Read exact object-container cgroup' in arg for arg in args):
  matches.append(int(path.parent.name))
assert len(matches)==1, f'exact observer process count {len(matches)}'
assert matches[0]!=os.getpid()
os.kill(matches[0],signal.SIGTERM)
print('stop-sent')
"""


VERIFY_ABSENT = """import sys
from pathlib import Path
run_id,pod_uid,container_id=sys.argv[1:]
matches=[]
for path in Path('/proc').glob('[0-9]*/cmdline'):
 try: args=path.read_bytes().split(b'\\0')
 except (FileNotFoundError,PermissionError): continue
 if len(args)>4 and b'-u' in args and b'-c' in args and all(
   value.encode() in b' '.join(args) for value in (run_id,pod_uid,container_id)) and any(
   b'Read exact object-container cgroup' in arg for arg in args):
  matches.append(int(path.parent.name))
assert not matches, f'exact observer remains: {matches}'
print('absent')
"""


def verify_remote_absence(scope: list[str]):
    command = ['docker', 'exec', NODE, 'python3', '-c', VERIFY_ABSENT, *scope]
    deadline = time.monotonic() + 5
    while True:
        result = subprocess.run(command, capture_output=True,
                                text=True, timeout=20)
        if result.returncode == 0:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('exact observer remote absence unproven: '
                               + result.stderr.strip())
        time.sleep(.1)


class ObjectMonitor:
    def __init__(self, kube, output: Path, expected_max: int):
        self.kube, self.output, self.expected_max = kube, output, expected_max
        self.identity = None
        self.process = None
        self.thread = None
        self.started = threading.Event()
        self.error = None
        self.start_row = None
        self.end_row = None
        self.samples = []
        self.stderr = None
        self.cleaned = False
        self.last_received = None
        self.watchdog_stop = threading.Event()
        self.watchdog = None

    def start(self, *, seconds: int):
        self.identity = object_identity(self.kube, self.expected_max)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.stderr = self.output.with_name(self.output.stem + '.stderr.log').open('x')
        self.process = subprocess.Popen([
            'docker', 'exec', NODE, 'python3', '-u', '-c',
            Path(probe.__file__).read_text(), '--run-id', RUN_ID,
            '--pod-uid', self.identity['pod_uid'],
            '--container-id', self.identity['container_id'],
            '--memory-max', str(self.expected_max),
            '--seconds', str(seconds), '--interval', '0.25'],
            stdout=subprocess.PIPE, stderr=self.stderr, text=True,
            bufsize=1)
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()
        self.watchdog = threading.Thread(target=self._watch, daemon=True)
        self.watchdog.start()
        if not self.started.wait(20):
            raise TimeoutError('exact object observer start deadline')
        if self.error is not None:
            raise self.error
        return self.start_row

    def _read(self):
        try:
            with self.output.open('x', buffering=1) as stream:
                for line in self.process.stdout:
                    stream.write(line)  # Persist the rejected row before checking it.
                    self.last_received = time.monotonic()
                    if self.error is not None:
                        continue  # Drain the pipe so an early guard failure cannot strand the node process.
                    try:
                        row = json.loads(line)
                        if row['kind'] == 'start':
                            if (self.start_row is not None or row['run_id'] != RUN_ID
                                    or any(row[key] != self.identity[key]
                                           for key in ('pod_uid', 'container_id', 'memory_max'))
                                    or row.get('pid', 0) < 1 or row.get('start_ticks', 0) < 1):
                                raise ValueError('exact object observer start identity changed')
                            self.start_row = row
                            self.started.set()
                        elif row['kind'] == 'sample':
                            if (self.start_row is None
                                    or any(row[key] != self.identity[key]
                                           for key in ('pod_uid', 'container_id', 'memory_max'))
                                    or row['cgroup'] != self.start_row['cgroup']
                                    or row['memory_current'] > self.expected_max
                                    or (self.samples and not 0 < row['time'] - self.samples[-1]['time'] <= 1)):
                                raise ValueError('exact object observer sample identity/gap changed')
                            if self.samples and any(row[key] < self.samples[-1][key]
                                    for key in ('object_full_total_us', 'node_full_total_us')):
                                raise ValueError('object/node PSI counter moved backwards')
                            self.samples.append(row)
                            events = row['memory_events']
                            if any(events.get(key, -1) != 0 for key in
                                   ('oom', 'oom_kill', 'oom_group_kill')):
                                raise ValueError('object-service cgroup OOM event')
                        elif row['kind'] == 'end':
                            self.end_row = row
                        else:
                            raise ValueError('unknown object observer row')
                    except BaseException as error:
                        self.error = error
                        self.started.set()
            if self.end_row is None and self.error is None:
                raise ValueError('object observer terminal marker missing')
        except BaseException as error:
            self.error = error
            self.started.set()

    def _watch(self):
        while not self.watchdog_stop.wait(.2):
            if self.error is not None:
                return
            if self.started.is_set() and self.last_received is not None:
                if time.monotonic() - self.last_received > 1:
                    self.error = TimeoutError('exact object observer telemetry stalled')
                    return

    def stop(self):
        if self.process is None:
            return
        self.watchdog_stop.set()
        outcomes = {}
        if self.process.poll() is None:
            scope = [RUN_ID, self.identity['pod_uid'], self.identity['container_id']]
            command = (['docker', 'exec', NODE, 'python3', '-c',
                stop_program(self.identity, self.start_row),
                str(self.start_row['pid']), str(self.start_row['start_ticks']),
                *scope] if self.start_row is not None else
                ['docker', 'exec', NODE, 'python3', '-c', FIND_AND_STOP, *scope])
            try:
                subprocess.run(command, check=True, capture_output=True,
                               text=True, timeout=20)
                outcomes['remote_stop'] = {'ok': True}
            except BaseException as error:
                outcomes['remote_stop'] = {'ok': False, 'error': repr(error)}
                try:
                    subprocess.run(['docker', 'exec', NODE, 'python3', '-c',
                        FIND_AND_STOP, *scope], check=True, capture_output=True,
                        text=True, timeout=20)
                    outcomes['exact_fallback_stop'] = {'ok': True}
                except BaseException as fallback:
                    outcomes['exact_fallback_stop'] = {
                        'ok': False, 'error': repr(fallback)}
        try:
            self.process.wait(timeout=20)
            outcomes['transport'] = {'ok': self.process.returncode == 0,
                                     'returncode': self.process.returncode}
        except BaseException as error:
            outcomes['transport'] = {'ok': False, 'error': repr(error)}
            self.process.terminate()  # Only the local docker-exec transport.
            try:
                self.process.wait(timeout=5)
            except BaseException as settle:
                outcomes['transport_settle'] = {'ok': False,
                                                'error': repr(settle)}
        scope = [RUN_ID, self.identity['pod_uid'], self.identity['container_id']]
        try:
            verify_remote_absence(scope)
            outcomes['remote_absence'] = {'ok': True}
        except BaseException:
            try:
                subprocess.run(['docker', 'exec', NODE, 'python3', '-c',
                    FIND_AND_STOP, *scope], check=True, capture_output=True,
                    text=True, timeout=20)
                verify_remote_absence(scope)
                outcomes['remote_absence'] = {'ok': True,
                                               'late_exact_stop': True}
            except BaseException as error:
                outcomes['remote_absence'] = {'ok': False,
                                               'error': repr(error)}
        if self.thread is not None:
            self.thread.join(timeout=5)
        if self.watchdog is not None:
            self.watchdog.join(timeout=5)
        outcomes['reader'] = {'ok': self.thread is not None
                             and not self.thread.is_alive(),
                             'error': repr(self.error) if self.error else None}
        if self.stderr is not None:
            self.stderr.close()
        self.cleaned = (self.process.poll() is not None
                        and outcomes['reader']['ok']
                        and outcomes['remote_absence']['ok']
                        and (self.watchdog is None or not self.watchdog.is_alive()))
        outcomes['complete'] = self.cleaned and self.error is None and all(
            item['ok'] for item in outcomes.values() if isinstance(item, dict))
        self.output.with_name(self.output.stem + '.cleanup.json').write_text(
            json.dumps(outcomes, indent=2) + '\n')
        if not outcomes['complete']:
            raise RuntimeError('object observer cleanup incomplete: ' + repr(outcomes))
        if (not self.samples or self.end_row is None
                or self.end_row.get('run_id') != RUN_ID
                or self.end_row['time'] < self.samples[-1]['time']
                or self.samples[0]['time'] - self.start_row['time'] > 1
                or self.end_row['time'] - self.samples[-1]['time'] > 1):
            raise ValueError('object observer sample/end coverage incomplete')
        if object_identity(self.kube, self.expected_max) != self.identity:
            raise ValueError('object-service Pod/container changed during observation')
        return {'samples': len(self.samples),
            'max_memory_current': max(row['memory_current'] for row in self.samples),
            'max_events_delta': self.samples[-1]['memory_events']['max']
                - self.samples[0]['memory_events']['max'],
            'full_psi_delta_us': self.samples[-1]['object_full_total_us']
                - self.samples[0]['object_full_total_us'],
            'identity': self.identity}
