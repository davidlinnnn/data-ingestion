"""Read exact object-container cgroup and node pressure from the existing kind node."""

import argparse
import json
import os
from pathlib import Path
import signal
import time


CGROUPS = Path('/sys/fs/cgroup')
NODE_PRESSURE = Path('/proc/pressure/memory')


def fields(path: Path) -> dict[str, int]:
    return {parts[0]: int(parts[1]) for line in path.read_text().splitlines()
            if len(parts := line.split()) == 2}


def full_pressure(path: Path) -> tuple[float, int]:
    line = next(line for line in path.read_text().splitlines()
                if line.startswith('full '))
    values = dict(part.split('=') for part in line.split()[1:])
    return float(values['avg10']), int(values['total'])


def exact_cgroup(root: Path, pod_uid: str, container_id: str,
                 expected_max: int) -> Path:
    pod_marker = 'pod' + pod_uid.replace('-', '_')
    container_marker = 'cri-containerd-' + container_id + '.scope'
    matches = [path.parent for path in root.rglob('memory.max')
               if pod_marker in str(path.parent)
               and path.parent.name == container_marker]
    if len(matches) != 1 or matches[0].joinpath('memory.max').read_text().strip() != str(expected_max):
        raise ValueError('exact object cgroup or memory limit changed')
    return matches[0]


def sample(cgroup: Path, pod_uid: str, container_id: str,
           expected_max: int) -> dict:
    if (cgroup / 'memory.max').read_text().strip() != str(expected_max):
        raise ValueError('object cgroup memory limit changed during observation')
    node_avg, node_total = full_pressure(NODE_PRESSURE)
    object_avg, object_total = full_pressure(cgroup / 'memory.pressure')
    events = fields(cgroup / 'memory.events')
    return {'kind': 'sample', 'time': time.time(),
        'pod_uid': pod_uid, 'container_id': container_id,
        'cgroup': str(cgroup), 'memory_max': expected_max,
        'memory_current': int((cgroup / 'memory.current').read_text()),
        'memory_events': events,
        'object_full_avg10': object_avg,
        'object_full_total_us': object_total,
        'node_full_avg10': node_avg,
        'node_full_total_us': node_total}


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--pod-uid', required=True)
    cli.add_argument('--container-id', required=True)
    cli.add_argument('--run-id', required=True)
    cli.add_argument('--memory-max', required=True, type=int)
    cli.add_argument('--seconds', required=True, type=float)
    cli.add_argument('--interval', type=float, default=.25)
    args = cli.parse_args(argv)
    if min(args.seconds, args.interval, args.memory_max) <= 0:
        raise ValueError('positive object probe scope required')
    cgroup = exact_cgroup(CGROUPS, args.pod_uid,
                          args.container_id, args.memory_max)
    stopped = False
    def request_stop(_signal, _frame):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, request_stop)
    pid = os.getpid()
    start_ticks = int(Path('/proc/self/stat').read_text().rsplit(') ', 1)[1].split()[19])
    print(json.dumps({'kind': 'start', 'time': time.time(),
        'run_id': args.run_id, 'pid': pid, 'start_ticks': start_ticks,
        'pod_uid': args.pod_uid, 'container_id': args.container_id,
        'cgroup': str(cgroup), 'memory_max': args.memory_max}), flush=True)
    deadline = time.monotonic() + args.seconds
    while not stopped and time.monotonic() < deadline:
        row = sample(cgroup, args.pod_uid, args.container_id, args.memory_max)
        print(json.dumps(row, sort_keys=True), flush=True)
        time.sleep(min(args.interval, max(0, deadline - time.monotonic())))
    print(json.dumps({'kind': 'end', 'time': time.time(),
        'run_id': args.run_id, 'stopped_by_signal': stopped}), flush=True)


if __name__ == '__main__':
    main()
