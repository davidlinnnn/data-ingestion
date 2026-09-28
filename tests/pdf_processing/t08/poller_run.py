"""Small cached-method rerun with live Pod-bound Temporal poller observations."""
import fcntl
import shutil
import time
from run import OUT, ROOT, STAGES, k, driver, scale, ready, absent, population, quiesce, copy_results

with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    while True:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
        except BlockingIOError:
            print('Poller window waiting for shared lock',flush=True);time.sleep(10)
    try:
        k('cp',str(ROOT/'tests/pdf_processing/t08/verify.py'),'coordinator:/tmp/t08-verify.py')
        saved=OUT/'rollout-results'
        if not saved.exists():shutil.copytree(OUT/'results',saved)
        print(driver('idle'),flush=True)
        scale('v1',('workflow','component_ocr'),1)
        scale('v2',('workflow',*STAGES),1)
        ready('v1',('workflow','component_ocr'));ready('v2')
        population('new-method')
        print(driver('submit','new','v2'),flush=True);print(driver('result','new'),flush=True)
        print(driver('idle'),flush=True)
        idle=tuple(s for s in STAGES if s!='component_ocr')
        scale('v2',idle,0);absent('v2',idle)
        scale('v1',idle,1);ready('v1')
        population('old-method')
        print(driver('submit','mixed','v1'),flush=True);print(driver('result','mixed'),flush=True)
        print(driver('idle'),flush=True)
        copy_results()
    finally:
        quiesce()
        fcntl.flock(lock,fcntl.LOCK_UN)
        print('Poller window quiescent; lock released',flush=True)
