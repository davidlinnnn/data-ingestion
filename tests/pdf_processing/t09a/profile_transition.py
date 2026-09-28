"""Supported OCR render-policy change: bounded replacement, compatible native reuse."""
import fcntl
import json
from pathlib import Path
import subprocess
from run import NS,ROOT,OUT,k,quiesce,run_trial,inventory

with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    original=None
    try:
        inventory('profile4-before')
        rows=json.loads(k('get','pods','-l','app=t09a-activities','-o','json'))['items']
        assert not rows,'Prior parser must be quiescent before profile replacement'
        deployment=json.loads(k('get','deployment','activities','-o','json'))
        original=deployment['spec']['template']['spec']['volumes']
        profile=json.loads(Path('/private/tmp/t09a-profile.json').read_text())
        profile['picture_ocr']={'render_scale':4}
        config={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'t09a-driver-ocr4','namespace':NS},
            'data':{'native-v1.json':json.dumps(profile),'worker.py':(ROOT/'deploy/pdf-processing/worker.py').read_text()}}
        subprocess.run(['kubectl','apply','-f','-'],input=json.dumps(config),text=True,check=True)
        volumes=json.loads(json.dumps(original))
        for volume in volumes:
            if volume['name']=='driver':volume['configMap']['name']='t09a-driver-ocr4'
        k('patch','deployment','activities','--type=json','-p',json.dumps([{'op':'replace','path':'/spec/template/spec/volumes','value':volumes}]))
        k('cp',str(ROOT/'tests/pdf_processing/t09a/verify.py'),'coordinator:/tmp/t09a-test/verify.py')
        (OUT/'profile4.json').write_text(json.dumps(profile,indent=2))
        run_trial('06','profile4-06',True,['--source-from','fresh-06','--expect-reuse'])
    finally:
        quiesce()
        if original is not None:
            k('patch','deployment','activities','--type=json','-p',json.dumps([{'op':'replace','path':'/spec/template/spec/volumes','value':original}]))
        fcntl.flock(lock,fcntl.LOCK_UN)
        print('Profile transition quiescent; lock released',flush=True)
