"""Observe exact T10 worker cgroups through replacements in the kind node."""
import json
import os
from pathlib import Path
import signal
import sys
import time

namespace = sys.argv[1]
stopped = False
def stop(_sig, _frame):
    global stopped
    stopped = True
signal.signal(signal.SIGTERM, stop)

def fields(path):
    return {line.split()[0].rstrip(':'): int(line.split()[1]) for line in path.read_text().splitlines()}

def pressure(path):
    full = next(line for line in path.read_text().splitlines() if line.startswith('full '))
    return float(dict(v.split('=') for v in full.split()[1:])['avg10'])

ticks=int(Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19])
print(json.dumps({'event':'start', 'pid':os.getpid(), 'start_ticks':ticks,'time':time.time()}),flush=True)
while not stopped:
    workers, parsers = [], []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            argv = proc.joinpath('cmdline').read_bytes().split(b'\0')
            if not any(x in argv for x in (b'/app/worker.py', b'/fault/fault_worker.py', b'pdf_processing.warm_child')):
                continue
            env = proc.joinpath('environ').read_bytes().split(b'\0')
            if ('T10_QUALIFICATION_NAMESPACE='+namespace).encode() not in env:
                continue
            if b'pdf_processing.warm_child' in argv:
                parsers.append(int(proc.name)); continue
            if b'WORKER_ROLE=activity' not in env:
                continue
            relative = proc.joinpath('cgroup').read_text().strip().split('::')[1]
            group = Path('/sys/fs/cgroup')/relative.lstrip('/')
            workers.append({'pid':int(proc.name), 'cgroup':relative,
                'memory_max':int(group.joinpath('memory.max').read_text()),
                'memory_current':int(group.joinpath('memory.current').read_text()),
                'memory_events':fields(group/'memory.events'), 'full_avg10':pressure(group/'memory.pressure')})
        except (FileNotFoundError, ProcessLookupError):
            continue
    print(json.dumps({'time':time.time(), 'available':fields(Path('/proc/meminfo'))['MemAvailable']*1024,
        'vm_oom_kill':fields(Path('/proc/vmstat'))['oom_kill'],
        'node_full_avg10':pressure(Path('/proc/pressure/memory')),
        'workers':workers, 'parser_pids':parsers}),flush=True)
    time.sleep(.25)
print(json.dumps({'event':'end', 'time':time.time()}),flush=True)
