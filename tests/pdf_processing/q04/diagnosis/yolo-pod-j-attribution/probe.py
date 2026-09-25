"""Bounded no-inference Linux process-read diagnostic; no acceptance changes."""
import hashlib,json,os,time
from pathlib import Path
out=[];start=time.monotonic();deadline=start+35
while time.monotonic()<deadline:
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  row={"time":time.time(),"elapsed":time.monotonic()-start,"pid":int(p.name)}
  try:
   row["comm"]=(p/'comm').read_text().strip()
   raw=(p/'stat').read_text();row["start_ticks"]=int(raw[raw.rfind(')')+1:].split()[19])
   command=(p/'cmdline').read_bytes();row["command_sha256"]=hashlib.sha256(command).hexdigest()
   row["uid_line"]=next(x for x in (p/'status').read_text().splitlines() if x.startswith('Uid:'))
   row["gid_line"]=next(x for x in (p/'status').read_text().splitlines() if x.startswith('Gid:'))
   (p/'smaps_rollup').read_text()
  except OSError as e:
   row.update(error=type(e).__name__,errno=e.errno,filename=e.filename)
   out.append(row)
 time.sleep(.02)
print(json.dumps({"uid":os.getuid(),"duration":time.monotonic()-start,"errors":out}))
