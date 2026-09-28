"""Check retained direct-call attribution and the CK/CM/CN limit reversal offline."""
import gzip
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def load(name):
    path = ROOT / name
    return json.loads(path.read_text() if path.exists()
                      else gzip.decompress(Path(str(path) + '.gz').read_bytes()))


def full(level):
    line = next(x for x in level['pressure'].splitlines() if x.startswith('full '))
    return int(next(x[6:] for x in line.split() if x.startswith('total=')))


ck = load('ck-idle/summary.json')
assert ck['after']['full'] > ck['before']['full']
assert ck['trace_exit'] == 0 and ck['trace_stderr'] == ''
assert ck['server_processes'] == [{'pid': 778767, 'argv': ['minio', 'server', '/data']}]
trace = [json.loads(x) for x in (ROOT/'ck-idle/trace.jsonl').read_text().splitlines()]
assert trace[0]['kind'] == 'start' and trace[-1]['kind'] == 'end'
identities, stacks, current = {}, [], None
for row in trace:
    if 'identity' in row:
        identities[row['identity']['tid']] = row['identity']
    line = row.get('line', '')
    if '<stack trace>' in line:
        tid = int(re.search(r'-(\d+)\s+\[', line)[1])
        current = {'identity': identities[tid], 'calls': []}
        stacks.append(current)
    elif line.startswith(' => ') and current is not None:
        current['calls'].append(line[4:])
    elif line and not line.startswith(' => '):
        current = None
target = [s for s in stacks if ck['container_id'] in s['identity']['cgroup']]
assert len(target) == 3
for stack in target:
    assert stack['identity']['tgid'] == 778767
    assert stack['calls'][:2] == ['psi_memstall_enter', 'try_charge_memcg']
    assert 'ext4_readdir' in stack['calls'] and '__arm64_sys_getdents64' in stack['calls']
for stats in trace[-1]['buffer_stats'].values():
    fields = dict(line.split(':', 1) for line in stats.splitlines())
    assert all(int(fields[k]) == 0 for k in ['overrun', 'commit overrun', 'dropped events'])

cm = load('cm-effective-limit/summary.json')
assert cm['status'] == 'NO_PSI_IN_WINDOW' and 'error' not in cm
assert cm['observed']['time'] - cm['raised']['time'] >= 30
for row in [cm['raised'], *cm['samples'], cm['observed']]:
    assert row['processes'] == cm['before']['processes']
    assert all(level['max'] == '1073741824' for level in row['levels'][:2])
    for i in [0, 1]:
        assert full(row['levels'][i]) == full(cm['raised']['levels'][i])
        assert row['levels'][i]['events_local'] == cm['raised']['levels'][i]['events_local']
        assert row['levels'][i]['stat']['pgscan_direct'] == cm['raised']['levels'][i]['stat']['pgscan_direct']
assert cm['observed']['levels'][0]['stat']['file'] > cm['raised']['levels'][0]['stat']['file']
assert cm['restoration_pass']
assert all(level['max'] == '536870912' for level in cm['restored']['levels'][:2])
cn = load('cn-restored/summary.json')
assert cn['before']['processes'] == cn['after']['processes'] == cm['before']['processes']
assert cn['full_delta'] > 0
for row in [cn['before'], *cn['samples'], cn['after']]:
    assert all(level['max'] == '536870912' for level in row['levels'][:2])
    assert all(level['events_local']['oom'] == level['events_local']['oom_kill'] == 0 for level in row['levels'][:2])
assert cn['after']['levels'][0]['events_local']['max'] == cn['before']['levels'][0]['events_local']['max']
assert cn['after']['levels'][1]['events_local']['max'] > cn['before']['levels'][1]['events_local']['max']
assert load('cm-effective-limit/independent-cleanup.json')['status'] == 'PASS'
print('PASS: server directory reads -> cgroup charge PSI; effective-limit reversal; ancestor-only max events; restoration')
