"""Read an active native stage from owned scratch; optionally stop that exact child."""
import json
import os
from pathlib import Path
import signal
import sys
import time

for path in Path('/scratch').glob('activity-*/pdf-*/process.log'):
    events = []
    for line in path.read_text(errors='replace').splitlines():
        try: row=json.loads(line)
        except ValueError:continue
        if isinstance(row,dict) and 'stage' in row and 'pid' in row:events.append(row)
    if not events:continue
    event=events[-1]
    if event.get('stage')!='stage_enter' or max(event.get('pages',[0]))<=5:continue
    if '--stop' in sys.argv:os.kill(event['pid'],signal.SIGSTOP)
    print(json.dumps({'observed':time.time(),'event':event,'scratch':str(path),'stopped':'--stop' in sys.argv}))
    break
