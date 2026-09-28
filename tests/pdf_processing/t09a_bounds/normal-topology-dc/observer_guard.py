"""Fail the window if auxiliary attribution exits or stops publishing samples."""
import json
from pathlib import Path
import time


def verify_observer(process, output: Path, *, now=None):
    if process.poll() is not None:
        raise RuntimeError('node attribution exited during qualification')
    with output.open('rb') as stream:
        stream.seek(max(0, output.stat().st_size - 131072))
        lines = stream.read().splitlines()
    # An in-progress last write is not a complete heartbeat.
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        stamp = row.get('ended_at', row.get('time'))
        if stamp is not None:
            if (time.time() if now is None else now) - stamp > 5:
                raise TimeoutError('node attribution telemetry stalled')
            return
    raise ValueError('node attribution heartbeat missing')


def stop_program(run_id, owner):
    """Stop only the stdin observer with this run identity, even before its start row."""
    return '''import json,os,signal,time
from pathlib import Path
scope=json.loads(%r)
def matches():
 result=[]
 for path in Path('/proc').glob('[0-9]*/cmdline'):
  try: args=path.read_bytes().split(b'\\0')
  except (FileNotFoundError,ProcessLookupError): continue
  if b'-u' in args and b'-' in args and b'--run-id' in args:
   index=args.index(b'--run-id')
   if args[index+1:index+2]==[scope['run_id'].encode()]:
    result.append(int(path.parent.name))
 return result
pids=matches()
assert len(pids)<=1, 'ambiguous node attribution process'
for pid in pids:
 owner=scope['owner']
 if owner is not None:
  raw=(Path('/proc')/str(pid)/'stat').read_text()
  assert pid==owner['pid'] and int(raw.rsplit(') ',1)[1].split()[19])==owner['start_ticks']
 os.kill(pid,signal.SIGTERM)
deadline=time.monotonic()+5
while matches() and time.monotonic()<deadline: time.sleep(.1)
assert not matches(), 'node attribution process remains'
print('node-attribution-absent')
''' % json.dumps({'run_id': run_id, 'owner': owner})
