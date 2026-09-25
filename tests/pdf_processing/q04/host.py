"""Owned worker process / explicitly selected single-Pod adapter.

Pod provisioning and service capacity are external. This code never scales a
Deployment. Pod mode requires a shared evidence directory visible at the same
absolute path in coordinator and worker, and the exact q04-run label.
"""
import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from consumer import require


class Host:
    def __init__(self, config_path, root, config):
        self.config_path, self.root, self.config = config_path, root, config
        self.process = None
        self.generation = 0
        self.pod = None
        self.log = None
        self.current = root
        self.worker_command = None

    def kubectl(self, *args, body=None):
        return subprocess.check_output(['kubectl', '--request-timeout=10s', '-n', self.config['pod_namespace'], *args], input=body, text=True, timeout=20)

    def inventory(self):
        pods = json.loads(self.kubectl('get', 'pods', '-l', 'q04-run='+self.config['run_id'], '-o', 'json'))['items']
        pods = [p for p in pods if not p['metadata'].get('deletionTimestamp') and p['status']['phase'] == 'Running']
        require(len(pods) == 1, 'exactly one owned Q04 Pod required')
        pod = pods[0]
        require(any(v['name'] == 'scratch' and 'emptyDir' in v for v in pod['spec']['volumes']), 'Pod needs isolated scratch emptyDir')
        require(any(v['name'] == 'scratch' and v['mountPath'] == '/scratch' for v in pod['spec']['containers'][0]['volumeMounts']), 'scratch mount required')
        require(all(c['restartCount'] == 0 and c['ready'] for c in pod['status']['containerStatuses']), 'owned Pod restarted/not ready')
        require(len(pod['spec']['containers']) == 1, 'single-container qualification only')
        return pod

    async def start(self):
        self.generation += 1
        self.current = self.root/f'worker-{self.generation}'
        command = [self.config['python'], str(Path(__file__).with_name('worker.py')),
            '--config', str(self.config_path), '--out', str(self.current), '--generation', str(self.generation)]
        self.worker_command = list(command)
        if self.config.get('pod_namespace'):
            self.pod = await asyncio.to_thread(self.inventory)
            command = ['kubectl', '-n', self.config['pod_namespace'], 'exec', self.pod['metadata']['name'], '--', *command]
        self.log = (self.root/f'worker-{self.generation}.log').open('x')
        self.process = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic()+90
        while not (self.current/'ready.json').exists():
            require(self.process.poll() is None and time.monotonic() < deadline, 'worker readiness failed')
            await asyncio.sleep(.2)
        ready = json.loads((self.current/'ready.json').read_text())
        require(ready['generation'] == self.generation, 'worker generation mismatch')
        (self.current/'host.json').write_text(json.dumps({'pod': self.pod, 'command': command, 'ready': ready}, indent=2))

    def signal(self, pid, sig, child=False):
        # Verify identity and parentage immediately before signaling owned processes.
        identity = self.current/'ready.json'
        if not identity.exists():
            identity = self.current/'ownership.json'
        ready = json.loads(identity.read_text())
        script = '''import os,psutil,signal,sys,time
pid,parent,sig,child,created=int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),float(sys.argv[5])
p=psutil.Process(parent)
assert p.create_time()==created
assert any('q04/worker.py' in x for x in p.cmdline())
t=psutil.Process(pid)
assert (pid==parent and not child) or (child and parent in [a.pid for a in t.parents()] and 'pdf_processing.warm_child' in t.cmdline())
os.kill(pid,sig)
if sig==signal.SIGSTOP:
 deadline=time.monotonic()+3
 while t.status()!=psutil.STATUS_STOPPED:
  assert time.monotonic()<deadline
  time.sleep(.02)
'''
        command = [self.config['python'], '-c', script, str(pid), str(ready['pid']), str(sig), str(int(child)), str(ready['created'])]
        if self.pod:
            current = self.inventory()
            require(current['metadata']['uid'] == self.pod['metadata']['uid'], 'Pod identity changed')
            command = ['kubectl', '-n', self.config['pod_namespace'], 'exec', self.pod['metadata']['name'], '--', *command]
        subprocess.run(command, check=True, timeout=20, capture_output=True)

    def force_stop(self):
        identity = self.current/'ownership.json'
        ready = json.loads(identity.read_text())
        script = """import psutil,sys,json
pid,created=int(sys.argv[1]),float(sys.argv[2])
try: p=psutil.Process(pid)
except psutil.NoSuchProcess: print(json.dumps({'already_absent':True}));sys.exit(0)
assert p.create_time()==created and any('q04/worker.py' in x for x in p.cmdline())
children=p.children(recursive=True)
for child in reversed(children):
 try: child.kill()
 except psutil.NoSuchProcess: pass
p.kill()
gone,alive=psutil.wait_procs(children+[p],timeout=5)
alive=[x for x in alive if x.status()!=psutil.STATUS_ZOMBIE]
assert not alive
print(json.dumps({'forced':True,'owned_pids':[x.pid for x in children]+[pid]}))
"""
        command = [self.config['python'], '-c', script, str(ready['pid']), str(ready['created'])]
        if self.pod:
            command = ['kubectl', '-n', self.config['pod_namespace'], 'exec', self.pod['metadata']['name'], '--', *command]
        output = subprocess.check_output(command, text=True, timeout=15)
        (self.current/'forced-cleanup.json').write_text(output)

    def stop_remote(self):
        # A kubectl launcher is a transport, not the lifetime of its remote worker.
        # Read the original Pod directly: failed readiness must not block cleanup.
        if self.pod is None or self.worker_command is None:
            raise ValueError('missing remote ownership')
        pod = json.loads(self.kubectl('get', 'pod', self.pod['metadata']['name'], '-o', 'json'))
        require(pod['metadata']['uid'] == self.pod['metadata']['uid'], 'Pod identity changed; cleanup remains pending')
        identity = self.current/'ownership.json'
        owner = json.loads(identity.read_text()) if identity.exists() else None
        script = """import json,os,psutil,signal,sys,time
command,owner,timeout=json.loads(sys.argv[1]),json.loads(sys.argv[2]),float(sys.argv[3])
owned=[]
for p in psutil.process_iter():
 try:
  if p.uids().real==os.getuid() and p.status()!=psutil.STATUS_ZOMBIE and p.cmdline()==command: owned.append(p)
 except psutil.NoSuchProcess: pass
assert len(owned)<=1, 'ambiguous exact worker command'
if owner:
 for p in owned: assert p.pid==owner['pid'] and p.create_time()==owner['created']
tracked=[]
for p in owned:
 tracked.extend(p.children(recursive=True));tracked.append(p)
 try: p.send_signal(signal.SIGTERM)
 except psutil.NoSuchProcess: pass
def live(processes):
 result=[]
 for p in processes:
  try:
   if p.is_running() and p.status()!=psutil.STATUS_ZOMBIE: result.append(p)
  except psutil.NoSuchProcess: pass
 return result
deadline=time.monotonic()+timeout
alive=live(tracked)
while alive and time.monotonic()<deadline:
 time.sleep(.05);alive=live(alive)
forced=bool(alive)
for p in reversed(alive):
 try: p.kill()
 except psutil.NoSuchProcess: pass
_,alive=psutil.wait_procs(alive,timeout=5)
assert not [p for p in alive if p.status()!=psutil.STATUS_ZOMBIE], 'owned processes remain'
for p in psutil.process_iter():
 try:
  if p.uids().real==os.getuid() and p.status()!=psutil.STATUS_ZOMBIE: assert p.cmdline()!=command, 'worker still present'
 except psutil.NoSuchProcess: pass
print(json.dumps({'worker_absent':True,'forced':forced,'owned_pids':[p.pid for p in tracked],'identity_published':owner is not None}))
"""
        command = ['kubectl', '-n', self.config['pod_namespace'], 'exec', self.pod['metadata']['name'], '--',
            self.config['python'], '-c', script, json.dumps(self.worker_command), json.dumps(owner), str(self.config['drain_seconds']+45)]
        output = subprocess.check_output(command, text=True, timeout=self.config['drain_seconds']+65)
        outcome = json.loads(output)
        require(outcome['worker_absent'], 'remote cleanup incomplete')
        # Root exists even when startup failed before the worker created its directory.
        with (self.root/f'remote-cleanup-{self.generation}-{time.time_ns()}.json').open('x') as stream:
            json.dump(outcome, stream)
        return outcome

    async def stop(self):
        if self.process is None:
            return
        if self.pod:
            # Keep process/Pod/command ownership on every uncertain cleanup path.
            outcome = await asyncio.to_thread(self.stop_remote)
            try:
                await asyncio.to_thread(self.process.wait, 10)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                await asyncio.to_thread(self.process.wait, 10)
                raise RuntimeError('remote worker absence verified; transport did not exit; child/scratch proof pending')
            returncode = self.process.returncode
            if self.log:
                self.log.close()
            proof = self.current/'stopped.json'
            require(proof.exists(), 'worker absent but child/scratch cleanup remains pending')
            stopped = json.loads(proof.read_text())
            require(stopped['parser_absent'] and stopped['scratch_absent'], 'worker cleanup incomplete; ownership retained')
            require(stopped['generation'] == self.generation, 'cleanup generation mismatch')
            identity = self.current/'ownership.json'
            if identity.exists():
                require(stopped['pid'] == json.loads(identity.read_text())['pid'], 'cleanup owner mismatch')
            self.process = None
            require(not outcome['forced'], 'forced remote cleanup; graceful qualification failed')
            require(returncode == 0, 'worker transport failed; remote cleanup verified')
            return
        if self.process.poll() is None:
            identity = self.current/'ready.json'
            if not identity.exists():
                identity = self.current/'ownership.json'
            if not identity.exists():
                # No remote worker identity was published; readiness failed before
                # the harness could connect or poll. The local launcher is owned.
                if self.pod:
                    raise RuntimeError('Remote worker identity unavailable; explicit cleanup needed')
                self.process.terminate()
                await asyncio.to_thread(self.process.wait, 10)
                raise RuntimeError('Worker failed before ownership publication')
            ready = json.loads(identity.read_text())
            await asyncio.to_thread(self.signal, ready['pid'], signal.SIGTERM)
            try:
                await asyncio.to_thread(self.process.wait, self.config['drain_seconds']+45)
            except subprocess.TimeoutExpired:
                await asyncio.to_thread(self.force_stop)
                await asyncio.to_thread(self.process.wait, 10)
                if self.log:
                    self.log.close()
                raise RuntimeError('forced worker cleanup; scratch proof pending; graceful qualification failed')
        if self.log:
            self.log.close()
        returncode = self.process.returncode
        proof = self.current/'stopped.json'
        require(proof.exists(), 'worker absent but child/scratch cleanup remains pending')
        stopped = json.loads(proof.read_text())
        require(stopped['parser_absent'] and stopped['scratch_absent'], 'worker cleanup incomplete')
        require(stopped['generation'] == self.generation, 'cleanup generation mismatch')
        identity = self.current/'ownership.json'
        if identity.exists():
            require(stopped['pid'] == json.loads(identity.read_text())['pid'], 'cleanup owner mismatch')
        self.process = None
        require(returncode == 0, 'worker failed; retain logs and do not accept run')

    async def drain(self, child_pid):
        old = self.pod
        await asyncio.to_thread(self.signal, child_pid, signal.SIGSTOP, True)
        await asyncio.sleep(.6)  # retain a sample spanning the injection before stopping the runtime
        if not old:
            await self.stop()
            await self.start()
            return {'scope': 'owned_worker_process', 'old_generation': self.generation-1, 'new_generation': self.generation}
        uid, name, node = old['metadata']['uid'], old['metadata']['name'], old['spec']['nodeName']
        body = json.dumps({'apiVersion': 'v1', 'kind': 'DeleteOptions', 'gracePeriodSeconds': self.config['drain_seconds']+15, 'preconditions': {'uid': uid}})
        await asyncio.to_thread(self.kubectl, 'delete', '--raw', f'/api/v1/namespaces/{self.config["pod_namespace"]}/pods/{name}', '-f', '-', body=body)
        deadline = time.monotonic()+120
        while await asyncio.to_thread(self.kubectl, 'get', 'pod', name, '--ignore-not-found', '-o', 'name'):
            require(time.monotonic() < deadline, 'old Pod still exists')
            await asyncio.sleep(1)
        if self.process is None:
            raise ValueError('missing owned exec process')
        await asyncio.to_thread(self.process.wait, 20)
        if self.log:
            self.log.close()
        self.process = None
        # This adapter targets the existing kind/docker topology only. Audit all
        # running containers by old UID; a deleted API object alone is insufficient.
        raw = await asyncio.to_thread(subprocess.check_output,
            ['docker', 'exec', node, 'crictl', 'ps', '--state', 'Running', '--label', 'io.kubernetes.pod.uid='+uid, '-o', 'json'], text=True, timeout=20)
        require(not json.loads(raw)['containers'], 'old runtime still running')
        await asyncio.to_thread(subprocess.run, ['docker', 'exec', node, 'test', '!', '-e',
            f'/var/lib/kubelet/pods/{uid}/volumes/kubernetes.io~empty-dir/scratch'], check=True, timeout=20)
        while True:
            require(time.monotonic() < deadline, 'replacement Pod not ready')
            try:
                new = await asyncio.to_thread(self.inventory)
                if new['metadata']['uid'] != uid:
                    break
            except ValueError:
                pass
            await asyncio.sleep(1)
        await self.start()
        return {'scope': 'owned_pod_kind', 'old_uid': uid, 'new_uid': new['metadata']['uid'],
                'old_runtime_absent': True, 'old_emptydir_absent': True}
