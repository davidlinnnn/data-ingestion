"""Run-owned file control for a coordinator outside the replaceable Activity Pod."""

import asyncio
import hashlib
import json
from pathlib import Path
import time

from pod_durable_evidence import write_once
from telemetry import read_rows


class WorkerLease:
    def __init__(self, directory: Path):
        self.directory = directory

    def poll(self):
        return 0 if (self.directory / 'stopped.json').exists() else None


class Host:
    """Coordinate one exact old-Pod deletion through a host-owned controller."""

    def __init__(self, config_path: Path, root: Path, config: dict):
        self.config_path, self.root, self.config = config_path, root, config
        self.control = root.parents[1] / 'pod-loss-control'
        self.control.mkdir(mode=0o700, exist_ok=False)
        self.run_id = config['run_id']
        self.generation = 0
        self.current = root
        self.process = None
        self.pod = None
        self.pod_uid = None
        self.stopped = False

    async def exchange(self, kind: str, generation: int, details: dict,
                       seconds: float, *, repeat: bool = False) -> dict:
        request = {'run_id': self.run_id, 'kind': kind,
                   'generation': generation, **details}
        name = f'{generation}-{kind}'
        request_path = self.control / f'{name}.request.json'
        if repeat and request_path.exists():
            if json.loads(request_path.read_text()) != request:
                raise ValueError('repeated controller request changed')
        else:
            write_once(request_path, request, volume_root=self.root.parents[1])
        reply_path = self.control / f'{name}.reply.json'
        deadline = time.monotonic() + seconds
        while not reply_path.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError(f'{kind} controller reply deadline')
            await asyncio.sleep(.05)
        reply = json.loads(reply_path.read_text())
        if (reply.get('run_id') != self.run_id or reply.get('kind') != kind
                or reply.get('generation') != generation or reply.get('status') != 'PASS'):
            raise ValueError(f'{kind} controller reply identity or status invalid')
        return reply

    def adopt(self, reply: dict) -> None:
        uid = reply.get('pod_uid')
        if not isinstance(uid, str) or not uid or uid == self.pod_uid:
            raise ValueError('replacement Pod UID missing or reused')
        generation = reply['generation']
        current = self.root / f'worker-{generation}'
        ready_raw = (current / 'ready.json').read_bytes()
        ready = json.loads(ready_raw)
        sample_path = current / 'samples.jsonl'
        with sample_path.open('rb') as stream:
            first_raw = stream.readline()
        samples = read_rows(sample_path)
        if (ready['generation'] != generation or not samples
                or samples[0]['time'] > ready['time']):
            raise ValueError('replacement worker readiness lacks prior sample')
        if (not first_raw.endswith(b'\n')
                or reply.get('ready_sha256') != hashlib.sha256(ready_raw).hexdigest()
                or reply.get('first_sample_sha256') != hashlib.sha256(first_raw).hexdigest()
                or reply.get('worker_pid') != ready.get('pid')
                or reply.get('worker_created') != ready.get('created')):
            raise ValueError('replacement Pod worker evidence binding invalid')
        last = samples[-1]
        if (last.get('generation') != generation
                or not 0 <= time.time() - last['time']
                <= self.config['window']['max_sample_gap_seconds']):
            raise ValueError('replacement worker sample stale or mismatched')
        write_once(current / 'host.json', {'pod': {'uid': uid}, 'ready': ready},
                   volume_root=self.root.parents[1])
        self.generation = generation
        self.current = current
        self.pod_uid = uid
        self.process = WorkerLease(current)

    async def start(self):
        if self.generation != 0:
            raise ValueError('initial Pod already adopted')
        reply = await self.exchange('start', 1, {}, 90)
        self.adopt(reply)

    async def drain(self, child_pid):
        if self.generation != 1 or not isinstance(child_pid, int) or child_pid < 1:
            raise ValueError('drain requires initial owned parser')
        old_uid = self.pod_uid
        reply = await self.exchange('drain', 2, {'old_pod_uid': old_uid,
                                                  'child_pid': child_pid},
                                    self.config['window']['max_replacement_seconds'])
        if (reply.get('old_pod_uid') != old_uid
                or reply.get('old_runtime_absent') is not True
                or reply.get('old_scratch_absent') is not True):
            raise ValueError('old Pod runtime or scratch absence unproven')
        self.adopt(reply)
        return {'scope': 'owned_pod', 'old_generation': 1, 'new_generation': 2,
                'old_pod_uid': old_uid, 'new_pod_uid': self.pod_uid}

    async def stop(self):
        if self.stopped:
            return
        reply = await self.exchange('stop', 0,
                                    {'known_pod_uid': self.pod_uid},
                                    self.config['drain_seconds'] + 45,
                                    repeat=True)
        if (reply.get('worker_absent') is not True
                or reply.get('activity_pods_absent') is not True):
            raise ValueError('run-owned Activity Pod stop unproven')
        self.process = None
        self.stopped = True
