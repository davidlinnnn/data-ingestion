"""T09b host: launch and cleanup identify the same measured worker."""

import asyncio
import json
from pathlib import Path
import signal
import subprocess
import time

from consumer import require
from host import Host as BaseHost
from host_be import lifecycle_boundary


def checked_helper(command, timeout):
    try:
        return subprocess.run(command, check=True, timeout=timeout,
                              capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "no diagnostic output").strip()
        raise RuntimeError(
            f"worker lifecycle helper failed ({error.returncode}): {detail}"
        ) from error


class Host(BaseHost):
    def signal(self, pid, sig, child=False):
        try:
            with lifecycle_boundary():
                return self._signal(pid, sig, child)
        except RuntimeError as error:
            if str(error) == "process lifecycle lock timed out":
                self.force_stop()
            raise

    def _signal(self, pid, sig, child=False):
        identity = self.current / "ready.json"
        if not identity.exists():
            identity = self.current / "ownership.json"
        ready = json.loads(identity.read_text())
        script = '''import os,psutil,signal,sys,time
pid,parent,sig,child,start_ticks=int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5])
p=psutil.Process(parent)
raw=open(f'/proc/{parent}/stat').read()
observed=int(raw[raw.rfind(')')+1:].split()[19])
assert observed==start_ticks,f'worker identity changed: expected start_ticks {start_ticks}, observed {observed}'
assert any('t09b/worker.py' in x for x in p.cmdline()),'worker command identity changed'
t=psutil.Process(pid)
assert (pid==parent and not child) or (child and parent in [a.pid for a in t.parents()] and 'pdf_processing.warm_child' in t.cmdline()),'signal target is not owned'
os.kill(pid,sig)
if sig==signal.SIGSTOP:
 deadline=time.monotonic()+3
 while t.status()!=psutil.STATUS_STOPPED:
  assert time.monotonic()<deadline
  time.sleep(.02)
'''
        command = [self.config["python"], "-c", script, str(pid), str(ready["pid"]),
                   str(sig), str(int(child)), str(ready["start_ticks"])]
        if self.pod:
            current = self.inventory()
            require(current["metadata"]["uid"] == self.pod["metadata"]["uid"],
                    "Pod identity changed")
            command = ["kubectl", "-n", self.config["pod_namespace"], "exec",
                       self.pod["metadata"]["name"], "--", *command]
        checked_helper(command, 20)

    def force_stop(self):
        ready = json.loads((self.current / "ownership.json").read_text())
        script = """import psutil,sys,json
pid,start_ticks=int(sys.argv[1]),int(sys.argv[2])
try: p=psutil.Process(pid)
except psutil.NoSuchProcess: print(json.dumps({'already_absent':True}));sys.exit(0)
raw=open(f'/proc/{pid}/stat').read();observed=int(raw[raw.rfind(')')+1:].split()[19])
assert observed==start_ticks,'worker start_ticks changed'
assert any('t09b/worker.py' in x for x in p.cmdline()),'worker command identity changed'
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
        command = [self.config["python"], "-c", script, str(ready["pid"]),
                   str(ready["start_ticks"])]
        if self.pod:
            command = ["kubectl", "-n", self.config["pod_namespace"], "exec",
                       self.pod["metadata"]["name"], "--", *command]
        output = checked_helper(command, 15)
        (self.current / "forced-cleanup.json").write_text(output)

    async def start(self):
        await self.prepare_start()
        await self.launch_start()
        await self.await_ready()

    async def prepare_start(self):
        if self.config.get("pod_namespace"):
            self.pod = await asyncio.to_thread(self.inventory)

    async def launch_start(self):
        self.generation += 1
        self.current = self.root / f"worker-{self.generation}"
        command = [self.config["python"], str(Path(__file__).with_name("worker.py")),
                   "--config", str(self.config_path), "--out", str(self.current),
                   "--generation", str(self.generation)]
        self.worker_command = list(command)
        if self.config.get("pod_namespace"):
            require(self.pod is not None, "prepared Pod required")
            command = ["kubectl", "-n", self.config["pod_namespace"], "exec",
                       self.pod["metadata"]["name"], "--", *command]
        self.log = (self.root / f"worker-{self.generation}.log").open("x")
        self.process = subprocess.Popen(command, stdout=self.log,
                                        stderr=subprocess.STDOUT, start_new_session=True)

    async def await_ready(self):
        deadline = time.monotonic() + 90
        while not (self.current / "ready.json").exists():
            require(self.process.poll() is None and time.monotonic() < deadline,
                    "worker readiness failed")
            await asyncio.sleep(.2)
        ready = json.loads((self.current / "ready.json").read_text())
        require(ready["generation"] == self.generation, "worker generation mismatch")
        (self.current / "host.json").write_text(json.dumps({
            "pod": self.pod, "command": self.process.args, "ready": ready,
        }, indent=2))
