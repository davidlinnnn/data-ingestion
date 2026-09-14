"""Replay accepted requests on their exact retained producer after replacement."""
import fcntl
import json
from run import ROOT,k,run_trial,quiesce

def package(name):
    quiesce()
    volumes=json.loads(k('get','deployment','activities','-o','json'))['spec']['template']['spec']['volumes']
    for volume in volumes:
        if volume['name']=='code':volume['configMap']['name']=name
    k('patch','deployment','activities','--type=json','-p',json.dumps([{'op':'replace','path':'/spec/template/spec/volumes','value':volumes}]))

def request_copy(reference,trial):
    script=f'''from pathlib import Path
r=Path('/tmp/t09a-results')
(r/'{trial}-request.json').write_bytes((r/'{reference}-request.json').read_bytes())'''
    k('exec','coordinator','--','/experiment/.venv/bin/python','-c',script)

with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        k('cp',str(ROOT/'tests/pdf_processing/t09a/verify.py'),'coordinator:/tmp/t09a-test/verify.py')
        for producer,cases in [('t09a-package-baseline',[('native','fresh-native'),('06','fresh-06'),('07','fresh-07')]),
                               ('t09a-package',[('08','evidence-08'),('09','fresh-09'),('10','fresh-10')])]:
            package(producer)
            for i,(sid,reference) in enumerate(cases):
                trial='replay-'+sid;request_copy(reference,trial)
                run_trial(sid,trial,i==0,['--expect-reuse'])
                check=f'''import json
from pathlib import Path
r=Path('/tmp/t09a-results')
a=json.loads((r/'{reference}.json').read_text());b=json.loads((r/'{trial}.json').read_text())
assert a['result']['processing_result']==b['result']['processing_result']
assert all(s['reused'] for s in b['result']['steps'])
print('Identical final and all steps reused: {sid}, producer {producer}')'''
                print(k('exec','coordinator','--','/experiment/.venv/bin/python','-c',check),flush=True)
            if producer=='t09a-package-baseline':
                request_copy('fresh-08','replay-failed-08')
                run_trial('08','replay-failed-08',False,['--expect-failure','region_outside_page'])
    finally:
        package('t09a-package')
        fcntl.flock(lock,fcntl.LOCK_UN)
        print('Replay window quiescent; lock released',flush=True)
