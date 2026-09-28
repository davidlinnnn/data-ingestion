"""One diagnostic window; never a production resource configuration change."""
import json
import subprocess
from pathlib import Path

out = Path('/private/tmp/q44-object-restored-cn')
out.mkdir(exist_ok=False)
base = json.loads(Path('/private/tmp/q44-object-reclaim-ci/summary.json').read_text())
program = "\nimport json, sys, time\nfrom pathlib import Path\np = Path(sys.argv[1]); parent = p.parent\nassert p.name == 'cri-containerd-' + sys.argv[2] + '.scope'\nassert sys.argv[3].replace('-', '_') in parent.name\nsmall, large = 536870912, 1073741824\ndef sample():\n    levels = []\n    for q in [p, *p.parents]:\n        if not (q/'memory.max').exists(): break\n        stat = dict(line.split() for line in (q/'memory.stat').read_text().splitlines())\n        levels.append({'path': str(q), 'max': (q/'memory.max').read_text().strip(),\n            'current': int((q/'memory.current').read_text()),\n            'events_local': {k: int(v) for k,v in (line.split() for line in (q/'memory.events.local').read_text().splitlines())},\n            'pressure': (q/'memory.pressure').read_text(),\n            'stat': {k: int(stat[k]) for k in ['anon','file','pgscan_direct','pgscan_kswapd','workingset_refault_file']}})\n    return {'time': time.time(), 'levels': levels, 'processes': (p/'cgroup.procs').read_text()}\ndef full(row):\n    line = next(l for l in row['levels'][0]['pressure'].splitlines() if l.startswith('full '))\n    return int(next(w[6:] for w in line.split() if w.startswith('total=')))\n\nr={'run_id':'object-restored-cn','mode':'read-only after restoration; no object exec, requests or reclaim','before':sample(),'samples':[]}\nend=time.monotonic()+10\nwhile time.monotonic()<end:\n    row=sample();r['samples'].append(row)\n    assert all(x['max']==str(small) for x in row['levels'][:2])\n    if full(row)>full(r['before']):break\n    time.sleep(.5)\nr['after']=sample();r['full_delta']=full(r['after'])-full(r['before'])\nprint(json.dumps(r))\n"
result = subprocess.run(['docker','exec','internal-a2a-vs6-local-worker2','python3','-c',program,
    base['before']['cgroup'],base['container_id'],base['pod_uid']], capture_output=True, text=True, timeout=60)
(out/'stdout.json').write_text(result.stdout)
(out/'stderr.txt').write_text(result.stderr)
result.check_returncode()
data = json.loads(result.stdout)
(out/'summary.json').write_text(json.dumps(data, indent=2)+'\n')
print(json.dumps({k:v for k,v in data.items() if k not in ['samples','before','raised','observed','restored']}))
