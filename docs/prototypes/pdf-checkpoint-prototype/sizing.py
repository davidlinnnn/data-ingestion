"""Bounded sizing trial on original pages 1-10 (includes multicolumn text, figures, tables)."""
import json
import os
from pathlib import Path
import subprocess
import time
ROOT=Path(__file__).resolve().parent
scratch=ROOT/'PROTOTYPE-wipe-me'
summary=[]
for size in (1,5,10):
    start_time=time.perf_counter()
    reports=[]
    for start in range(1,11,size):
        out=scratch/f'sizing-{size}'/f'{start}-{start+size-1}'
        out.mkdir(parents=True,exist_ok=True)
        with (out/'process.log').open('w') as log:
            subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'experiment.py'),'capture',str(ROOT/'fixtures/llm-survey-2303.18223v1.pdf'),'--out',str(out),'--start',str(start),'--end',str(start+size-1),'--checkpoint-only'],stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'HF_HUB_OFFLINE':'1'},check=True)
        reports.append(json.loads((out/'metrics.json').read_text()))
    result={'group_size':size,'source_pages':[1,10],'processes':len(reports),
      'wall_seconds':time.perf_counter()-start_time,
      'peak_child_rss_bytes':max(r['peak_rss_bytes'] for r in reports),
      'convert_seconds_sum':sum(r['convert_seconds'] for r in reports),
      'checkpoint_bytes':sum(p.stat().st_size for p in (scratch/f'sizing-{size}').glob('*/checkpoints/*')),
      'metrics':reports}
    summary.append(result)
    (ROOT/'evidence/sizing.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='metrics'}),flush=True)
