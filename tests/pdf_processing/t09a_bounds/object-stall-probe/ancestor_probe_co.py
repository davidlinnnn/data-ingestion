"""Read exact object ancestors and VM counters; diagnostic, no writes."""
import json
from pathlib import Path
import sys
import time


def fields(path):
    return {k.rstrip(':'): int(v.split()[0]) for k, v in
            (line.split(None, 1) for line in path.read_text().splitlines())}


def snapshot(cgroup):
    levels = []
    for p in [cgroup, *cgroup.parents]:
        if not (p/'memory.max').exists():
            break
        stat = fields(p/'memory.stat')
        levels.append({'path': str(p), 'max': (p/'memory.max').read_text().strip(),
            'high': (p/'memory.high').read_text().strip(),
            'current': int((p/'memory.current').read_text()),
            'swap': int((p/'memory.swap.current').read_text()),
            'events_local': fields(p/'memory.events.local'),
            'pressure': (p/'memory.pressure').read_text(),
            'stat': {k: stat[k] for k in ['anon','file','kernel','pgscan_direct',
                'pgscan_kswapd','workingset_refault_file']}})
    vmstat = fields(Path('/proc/vmstat'))
    return {'time': time.time(), 'levels': levels,
        'processes': (cgroup/'cgroup.procs').read_text(),
        'vm': {'available': fields(Path('/proc/meminfo'))['MemAvailable']*1024,
            'pressure': Path('/proc/pressure/memory').read_text(),
            'stat': {k: vmstat[k] for k in ['oom_kill','pgscan_direct','pgscan_kswapd',
                'compact_stall','allocstall_movable','workingset_refault_file']}}}


def full(pressure):
    line = next(x for x in pressure.splitlines() if x.startswith('full '))
    return {k: float(v) for k,v in (x.split('=') for x in line.split()[1:])}


def violation(row, baseline, floor):
    # Existing object PSI/max/OOM and VM avg10/floor guards remain intact.
    # Ancestor events are additional diagnostic evidence, not a new acceptance rule.
    if any(x['max'] != '1073741824' for x in row['levels'][:2]):
        return 'effective object budget changed'
    if any(x['max'] != 'max' and int(x['max']) < 1073741824 for x in row['levels'][2:]):
        return 'upper ancestor limits effective budget'
    if row['processes'] != baseline['processes']:
        return 'object process changed'
    leaf, first = row['levels'][0], baseline['levels'][0]
    if full(leaf['pressure'])['total'] > full(first['pressure'])['total']:
        return 'object full PSI increased'
    if any(leaf['events_local'][k] > first['events_local'][k] for k in ['max','oom','oom_kill']):
        return 'object max/OOM increased'
    vm = row['vm']
    if (vm['available'] < floor or full(vm['pressure'])['avg10'] != 0 or
            vm['stat']['oom_kill'] != baseline['vm']['stat']['oom_kill']):
        return 'VM floor/PSI/OOM guard'
    return None


if __name__ == '__main__':
    root = Path('/sys/fs/cgroup')
    uid, cid = sys.argv[1:]
    matches = [p for p in root.rglob('cri-containerd-'+cid+'.scope')
               if uid.replace('-', '_') in p.parent.name]
    assert len(matches) == 1
    print(json.dumps(snapshot(matches[0])))
