"""Drain only the owned worker process while preserving its Pod identity."""

import asyncio
import signal

from consumer import require
from host_an import Host as BaseHost


class Host(BaseHost):
    async def drain(self, child_pid):
        require(self.pod is not None and self.collector.started,
                'owned Pod and active collector required for process drain')
        uid = self.pod['metadata']['uid']
        generation = self.generation
        await asyncio.to_thread(self.signal, child_pid, signal.SIGSTOP, True)
        await asyncio.sleep(.6)
        await self.stop()
        require(self.process is None and self.generation == generation,
                'old worker process did not stop')
        await self.prepare_start()
        require(self.pod['metadata']['uid'] == uid, 'process drain replaced Pod')
        await self.collector.process_transition('replacement_worker_birth', self.launch_start)
        await self.await_ready()
        require(self.generation == generation + 1
                and self.pod['metadata']['uid'] == uid,
                'replacement worker or Pod identity changed')
        return {'scope': 'owned_worker_process', 'pod_uid': uid,
                'old_generation': generation, 'new_generation': self.generation}
