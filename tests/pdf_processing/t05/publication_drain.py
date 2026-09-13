"""Delete a worker gracefully while its real publication is deliberately delayed."""
import json,subprocess,time
ns='pdf-t05-validation'
def k(*args): return subprocess.check_output(['kubectl','-n',ns,*args],text=True)
pod=next(p['metadata']['name'] for p in json.loads(k('get','pods','-l','app=t05-activities','-o','json'))['items'] if not p['metadata'].get('deletionTimestamp') and p['status'].get('phase')=='Running')
run=subprocess.Popen(['kubectl','-n',ns,'exec','coordinator','--','/experiment/.venv/bin/python','/tmp/case.py','pubdrain-2'])
started=time.monotonic()
while time.monotonic()-started<60:
    if 'T05_PUBLICATION_PAUSED' in k('logs',pod):
        print(json.dumps({'case':'pubdrain-2','pod':pod,'publication_pause_observed':True}),flush=True)
        k('delete','pod',pod,'--wait=false')
        break
    time.sleep(.2)
else:
    raise RuntimeError('Publication pause was not observed')
raise SystemExit(run.wait(timeout=180))
