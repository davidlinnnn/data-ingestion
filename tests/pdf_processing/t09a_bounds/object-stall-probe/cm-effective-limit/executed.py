"""One diagnostic window; never a production resource configuration change."""
import json
import subprocess
from pathlib import Path

out = Path('/private/tmp/q44-object-effective-limit-cm')
out.mkdir(exist_ok=False)
base = json.loads(Path('/private/tmp/q44-object-reclaim-ci/summary.json').read_text())
program = r'''
import json, sys, time
from pathlib import Path
p = Path(sys.argv[1]); parent = p.parent
assert p.name == 'cri-containerd-' + sys.argv[2] + '.scope'
assert sys.argv[3].replace('-', '_') in parent.name
small, large = 536870912, 1073741824
def sample():
    levels = []
    for q in [p, *p.parents]:
        if not (q/'memory.max').exists(): break
        stat = dict(line.split() for line in (q/'memory.stat').read_text().splitlines())
        levels.append({'path': str(q), 'max': (q/'memory.max').read_text().strip(),
            'current': int((q/'memory.current').read_text()),
            'events_local': {k: int(v) for k,v in (line.split() for line in (q/'memory.events.local').read_text().splitlines())},
            'pressure': (q/'memory.pressure').read_text(),
            'stat': {k: int(stat[k]) for k in ['anon','file','pgscan_direct','pgscan_kswapd','workingset_refault_file']}})
    return {'time': time.time(), 'levels': levels, 'processes': (p/'cgroup.procs').read_text()}
def full(row):
    line = next(l for l in row['levels'][0]['pressure'].splitlines() if l.startswith('full '))
    return int(next(w[6:] for w in line.split() if w.startswith('total=')))
r = {'run_id': 'object-effective-limit-cm', 'samples': [], 'intervention': 'same container; leaf AND exact Pod ancestor 512Mi to 1Gi for at most 30s; restore both'}
changed = []
try:
    r['before'] = sample()
    assert all(x['max'] == str(small) for x in r['before']['levels'][:2])
    assert r['before']['levels'][0]['stat']['anon'] < small // 2
    assert all(x['max'] == 'max' or int(x['max']) >= large for x in r['before']['levels'][2:])
    for q in [parent, p]:
        changed.append(q)
        (q/'memory.max').write_text(str(large))
    r['raised'] = sample()
    assert all(x['max'] == str(large) for x in r['raised']['levels'][:2])
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        row = sample(); r['samples'].append(row)
        assert all(x['max'] == str(large) for x in row['levels'][:2])
        assert row['processes'] == r['before']['processes']
        if full(row) > full(r['raised']):
            r['stop'] = 'PSI increased'; break
        if any(row['levels'][i]['events_local']['oom_kill'] > r['before']['levels'][i]['events_local']['oom_kill'] for i in [0,1]):
            r['stop'] = 'OOM increased'; break
        time.sleep(.5)
    r['observed'] = sample()
    r['full_delta'] = full(r['observed']) - full(r['raised'])
    r['status'] = 'NO_PSI_IN_WINDOW' if r['full_delta'] == 0 and 'stop' not in r else 'STOPPED'
except BaseException as exc:
    r['error'] = repr(exc)
finally:
    for q in reversed(changed): (q/'memory.max').write_text(str(small))
    r['restored'] = sample()
    r['restoration_pass'] = all(x['max'] == str(small) for x in r['restored']['levels'][:2])
    print(json.dumps(r), flush=True)
    assert r['restoration_pass']
'''
result = subprocess.run(['docker','exec','internal-a2a-vs6-local-worker2','python3','-c',program,
    base['before']['cgroup'],base['container_id'],base['pod_uid']], capture_output=True, text=True, timeout=60)
(out/'stdout.json').write_text(result.stdout)
(out/'stderr.txt').write_text(result.stderr)
result.check_returncode()
data = json.loads(result.stdout)
(out/'summary.json').write_text(json.dumps(data, indent=2)+'\n')
print(json.dumps({k:v for k,v in data.items() if k not in ['samples','before','raised','observed','restored']}))
