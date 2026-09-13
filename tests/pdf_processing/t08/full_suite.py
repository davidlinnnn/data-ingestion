"""Run the existing full regression suite under the same qualification lock."""
import fcntl
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[3]
PYTHON='/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python'
FIXTURES='/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype'
with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    while True:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
        except BlockingIOError:
            print('Full suite waiting for qualification lock',flush=True);time.sleep(10)
    process=None
    try:
        env={**os.environ,'PYTHONPATH':str(ROOT/'src')+':/private/tmp/t01-type-deps',
            'PDF_TEST_FIXTURE_ROOT':FIXTURES,'HF_HUB_OFFLINE':'1'}
        with (ROOT/'tests/pdf_processing/t08/evidence/full-suite.log').open('w') as log:
            process=subprocess.Popen([PYTHON,str(ROOT/'tests/pdf_processing/t06/run_unit_suite.py')],
                cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            assert process.wait()==0, 'Full regression suite failed; inspect evidence/full-suite.log'
    finally:
        if process is not None and process.poll() is None:
            import signal
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
        fcntl.flock(lock,fcntl.LOCK_UN)
    print('Full suite finished; host child exited and lock released',flush=True)
