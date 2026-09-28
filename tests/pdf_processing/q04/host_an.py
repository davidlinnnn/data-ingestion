"""AN worker birth boundary for strict process attribution."""

import asyncio
import json
from pathlib import Path
import subprocess
import time

from consumer import require
from host import Host as BaseHost


class Host(BaseHost):
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
