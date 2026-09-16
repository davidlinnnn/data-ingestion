"""Linux VM/cgroup observation and fail-closed guards; no inferred sizing limits."""
import json
from pathlib import Path
import time

from consumer import require


def sample(proc=Path('/proc'), cgroup=Path('/sys/fs/cgroup')):
    def fields(path):
        return {line.split()[0].rstrip(':'): int(line.split()[1]) for line in path.read_text().splitlines()}
    pressure = (proc/'pressure/memory').read_text()
    full = next(line for line in pressure.splitlines() if line.startswith('full '))
    return {'time': time.time(), 'available': fields(proc/'meminfo')['MemAvailable']*1024,
        'vm_oom_kill': fields(proc/'vmstat')['oom_kill'],
        'memory_current': int((cgroup/'memory.current').read_text()),
        'memory_events': fields(cgroup/'memory.events'),
        'psi_full_avg10': float(dict(v.split('=') for v in full.split()[1:])['avg10'])}


def check_sample(row, initial, limits):
    require(row['available'] >= limits['min_available_bytes'], 'VM memory pressure')
    require(row['psi_full_avg10'] <= limits['max_full_psi'], 'VM PSI pressure')
    require(row['vm_oom_kill'] == initial['vm_oom_kill'], 'new VM OOM')
    require(row['memory_events'].get('oom_kill', 0) == initial['memory_events'].get('oom_kill', 0), 'new cgroup OOM')
    require(row['memory_current'] <= limits['max_cgroup_bytes'], 'cgroup budget exceeded')


def check_coverage(rows, started, finished, maximum_gap):
    require(len(rows) >= 2 and rows[0]['time'] <= started and rows[-1]['time'] >= finished, 'incomplete resource coverage')
    gaps = [b['time']-a['time'] for a, b in zip(rows, rows[1:])]
    require(all(0 < gap <= maximum_gap for gap in gaps), 'resource telemetry gap')
    return {'samples': len(rows), 'max_gap': max(gaps),
        'min_available_bytes': min(r['available'] for r in rows),
        'max_cgroup_bytes': max(r['memory_current'] for r in rows)}


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines(keepends=True) if line.endswith('\n')]
