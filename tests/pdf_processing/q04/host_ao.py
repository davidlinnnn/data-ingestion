"""AO host starts the test-only interruption worker in its owned Pod."""

import json
from pathlib import Path
import subprocess

from consumer import require
from host_an import Host as BaseHost


class Host(BaseHost):
    async def launch_start(self):
        self.generation += 1
        self.current = self.root / f"worker-{self.generation}"
        command = [self.config["python"], str(Path(__file__).with_name("worker_ao.py")),
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

    def signal(self, pid, sig, child=False):
        require(not child, "AO host only signals its exact worker parent")
        identity = self.current / "ready.json"
        if not identity.exists():
            identity = self.current / "ownership.json"
        owner = json.loads(identity.read_text())
        require(pid == owner["pid"], "worker PID changed")
        script = """import json,os,psutil,signal,sys
pid,created,sig,command=int(sys.argv[1]),float(sys.argv[2]),int(sys.argv[3]),json.loads(sys.argv[4])
p=psutil.Process(pid)
assert p.create_time()==created and p.cmdline()==command
assert command[1].endswith('/q04/worker_ao.py')
os.kill(pid,sig)
"""
        subprocess.run([self.config["python"], "-c", script, str(pid),
                        str(owner["created"]), str(sig), json.dumps(self.worker_command)],
                       check=True, timeout=20, capture_output=True)

    def force_stop(self):
        owner = json.loads((self.current / "ownership.json").read_text())
        script = """import json,psutil,sys
pid,created,command=int(sys.argv[1]),float(sys.argv[2]),json.loads(sys.argv[3])
try: p=psutil.Process(pid)
except psutil.NoSuchProcess: print(json.dumps({'already_absent':True}));sys.exit(0)
assert p.create_time()==created and p.cmdline()==command
assert command[1].endswith('/q04/worker_ao.py')
children=p.children(recursive=True)
for child in reversed(children):
 try: child.kill()
 except psutil.NoSuchProcess: pass
p.kill()
_,alive=psutil.wait_procs(children+[p],timeout=5)
assert not [x for x in alive if x.status()!=psutil.STATUS_ZOMBIE]
print(json.dumps({'forced':True,'owned_pids':[x.pid for x in children]+[pid]}))
"""
        output = subprocess.check_output([self.config["python"], "-c", script,
            str(owner["pid"]), str(owner["created"]), json.dumps(self.worker_command)],
            text=True, timeout=15)
        (self.current / "forced-cleanup.json").write_text(output)
