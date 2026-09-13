"""External Kubernetes fault controller; never changes processing code or inputs."""
import json,subprocess,sys,time
ns='pdf-t05-validation'
def k(*args): return subprocess.check_output(['kubectl','-n',ns,*args],text=True)
case=sys.argv[1]
run=subprocess.Popen(['kubectl','-n',ns,'exec','coordinator','--','/experiment/.venv/bin/python','/tmp/case.py',case])
start=time.monotonic()
injected=set()
while time.monotonic()-start<60:
    pod=next(p['metadata']['name'] for p in json.loads(k('get','pods','-l','app=t05-activities','-o','json'))['items'] if not p['metadata'].get('deletionTimestamp') and p['status'].get('phase')=='Running')
    probe=k('exec',pod,'--','/experiment/.venv/bin/python','-c', '''from pathlib import Path
import json
for p in Path('/scratch').glob('activity-*/pdf-*/process.log'):
 rows=[]
 for line in p.read_text(errors='replace').splitlines():
  try: rows.append(json.loads(line))
  except ValueError: pass
 for r in rows:
  if r.get('stage')=='stage_enter' and 'pid' in r:
   print(json.dumps({'pid':r['pid'],'path':str(p),'stage':r.get('native_stage'),'pages':r.get('pages',[])}));raise SystemExit
''')
    if probe.strip():
        event=json.loads(probe)
        if case.startswith('pod') and max(event.get('pages', [0])) <= 5:
            time.sleep(.1);continue
        if (pod,event['pid']) in injected:
            time.sleep(.1);continue
        injected.add((pod,event['pid']))
        if case.startswith('pod'):
            k('delete','pod',pod,'--grace-period=0','--force','--wait=false')
        elif case.startswith('drain'):
            k('delete','pod',pod,'--wait=false')
        else:
            sig='STOP' if case.startswith('hang') else 'KILL'
            k('exec',pod,'--','sh','-c',f'kill -{sig} {event["pid"]}')
        event.update(case=case,pod=pod,elapsed=time.monotonic()-start)
        print(json.dumps(event),flush=True)
        if not case.startswith('exhaust') or len(injected)==3:
            break
    time.sleep(.1)
else:
    raise RuntimeError('No native stage found for injection')
raise SystemExit(run.wait(timeout=180))
