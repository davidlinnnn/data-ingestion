"""Host controller: hold the shared lock throughout each measured experiment."""
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

NS = 'pdf-t09a-validation'
ROOT = Path(__file__).resolve().parents[3]
OUT = Path('/private/tmp/t09a-controller'); OUT.mkdir(exist_ok=True)
PYTHON = '/experiment/.venv/bin/python'

def k(*args, **kwargs):
    return subprocess.check_output(['kubectl','--request-timeout=15s','-n',NS,*args],text=True,timeout=45,**kwargs)

def inventory(name):
    # Observation transport failure contaminates a trial; it must not abandon work.
    snapshot: dict = {'time': time.time()}
    commands = {
        'pods': ['kubectl','--request-timeout=5s','get','pods','-A','-o','json'],
        'host': ['ps','-A','-o','pid,pcpu,rss,comm'],
        'node': ['kubectl','--request-timeout=5s','get','--raw',
                 '/api/v1/nodes/internal-a2a-vs6-local-worker2/proxy/stats/summary'],
    }
    for key, command in commands.items():
        try:
            raw = subprocess.check_output(command,text=True,timeout=10,stderr=subprocess.PIPE)
            snapshot[key] = raw if key == 'host' else json.loads(raw)
        except (subprocess.SubprocessError, ValueError) as error:
            snapshot[key+'_error'] = type(error).__name__
    with (OUT/(name+'-inventory.jsonl')).open('a') as f:
        f.write(json.dumps(snapshot)+'\n')


def quiesce():
    # Fail closed: retain the host lock until the remote worker is actually gone.
    while True:
        try:
            k('scale','deployment/activities','--replicas=0')
            rows = json.loads(k('get','pods','-l','app=t09a-activities','-o','json'))['items']
            if not rows:
                return
        except subprocess.SubprocessError:
            pass
        print('Recovery guard held: waiting for T09a Activity Pods to stop',flush=True)
        time.sleep(10)

def pod():
    data = json.loads(k('get','pods','-l','app=t09a-activities','-o','json'))
    return next(x['metadata']['name'] for x in data['items'] if not x['metadata'].get('deletionTimestamp'))

def run_trial(sid,trial,restart,driver_args=None):
    if restart:
        k('scale','deployment/activities','--replicas=1')
        k('rollout','restart','deployment/activities')
        k('rollout','status','deployment/activities','--timeout=90s')
    worker = pod()
    k('cp',str(ROOT/'tests/pdf_processing/t09a/sample.py'),worker+':/tmp/sample.py')
    k('exec',worker,'--','rm','-f','/tmp/t09a-stop-sampling','/tmp/t09a-samples.jsonl')
    sample_output = (OUT/(trial+'-live-samples.jsonl')).open('w')
    sampler = subprocess.Popen(['kubectl','-n',NS,'exec',worker,'--',PYTHON,'/tmp/sample.py'],stdout=sample_output,stderr=subprocess.PIPE)
    inventory(trial+'-before')
    started = time.time()
    process = None
    try:
        with (OUT/(trial+'.log')).open('w') as log:
            process = subprocess.Popen(['kubectl','-n',NS,'exec','coordinator','--',PYTHON,'/tmp/t09a-test/verify.py',sid,trial]+(['--attach'] if trial=='interrupted-native' else [])+(driver_args or []),stdout=log,stderr=subprocess.STDOUT)
            while process.poll() is None:
                time.sleep(10)
                inventory(trial+'-during')
            if process.returncode: raise RuntimeError('Trial failed: '+trial+'; see '+str(OUT/(trial+'.log')))
    except BaseException:
        quiesce()
        if process is not None and process.poll() is None:
            process.terminate()
        raise
    finally:
        try:
            k('exec',worker,'--','touch','/tmp/t09a-stop-sampling')
            sampler.wait(timeout=15)
            k('cp',worker+':/tmp/t09a-samples.jsonl',str(OUT/(trial+'-samples.jsonl')))
            (OUT/(trial+'-worker.json')).write_text(k('get','pod',worker,'-o','json'))
        except subprocess.SubprocessError as error:
            (OUT/(trial+'-sampling-error.txt')).write_text(type(error).__name__)
        finally:
            if sampler.poll() is None: sampler.terminate()
            sample_output.close()
        inventory(trial+'-after')
        (OUT/(trial+'-controller.json')).write_text(json.dumps({'trial':trial,'worker':worker,'started':started,'finished':time.time()}))
    print((OUT/(trial+'.log')).read_text(),flush=True)

if __name__ == '__main__':
    with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print('Waiting: another qualification owns the shared host lock.',flush=True); sys.exit(75)
        try:
            print('T09a acquired shared host qualification lock',flush=True)
            for _ in range(3):
                k('get','pods')
                time.sleep(2)
            inventory('pre-lock-smoke')
            if sys.argv[1]=='fresh':
                subprocess.run([sys.executable,str(ROOT/'tests/pdf_processing/t09a/setup.py')],check=True)
                k('rollout','restart','deployment/workflows'); k('rollout','status','deployment/workflows','--timeout=90s')
                k('cp',str(ROOT/'tests/pdf_processing/t09a/verify.py'),'coordinator:/tmp/t09a-test/verify.py')
                for sid in sys.argv[2:] or ['native','06','07','08']:
                    run_trial(sid,'fresh-'+sid,True)
            elif sys.argv[1]=='recovery':
                k('cp',str(ROOT/'tests/pdf_processing/t09a/verify.py'),'coordinator:/tmp/t09a-test/verify.py')
                run_trial('native','interrupted-native',True)
            elif sys.argv[1]=='warm':
                for i,sid in enumerate(['06','07','08','native','06']):
                    run_trial(sid,'warm-'+str(i)+'-'+sid,i==0)
        finally:
            quiesce()
            fcntl.flock(lock,fcntl.LOCK_UN)
            print('T09a released shared host qualification lock',flush=True)
