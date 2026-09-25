"""Bounded THP mechanism probe: 64 MiB, no model or workflow."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

libc = ctypes.CDLL(None, use_errno=True)
mode = sys.argv[1]
assert mode in ('default', 'disabled')
if mode == 'disabled':
    assert libc.prctl(41, 1, 0, 0, 0) == 0, ctypes.get_errno()
disabled = libc.prctl(42, 0, 0, 0, 0)
assert disabled == (mode == 'disabled')

def snapshot():
    paths = ['/proc/vmstat', '/proc/pressure/memory', '/proc/meminfo',
             '/proc/self/smaps_rollup', '/sys/fs/cgroup/memory.stat',
             '/sys/fs/cgroup/memory.events', '/sys/fs/cgroup/memory.pressure']
    return {p: Path(p).read_text() for p in paths}

before = snapshot()
mem = dict(line.split(':', 1) for line in before['/proc/meminfo'].splitlines())
assert int(mem['MemAvailable'].split()[0]) * 1024 > 5 * 1024**3
assert 'full avg10=0.00' in before['/proc/pressure/memory']
import numpy as np
start = time.monotonic()
array = np.empty(64 * 1024**2, dtype=np.uint8)
array.fill(1)
after = snapshot()
child = subprocess.check_output([sys.executable, '-c',
    'import ctypes;print(ctypes.CDLL(None).prctl(42,0,0,0,0))'], text=True)
print(json.dumps(dict(mode=mode, pid=os.getpid(), thp_disabled=disabled,
    exec_child_thp_disabled=int(child), numpy_version=np.__version__,
    bytes=array.nbytes, seconds=time.monotonic()-start, before=before, after=after)))
assert int(child) == disabled
if disabled:
    assert 'AnonHugePages:         0 kB' in after['/proc/self/smaps_rollup']
