"""Run with the retained prototype Python; reap owned descendants before unlocking."""
import fcntl
import os
from pathlib import Path
import subprocess
import time
import psutil

ROOT=Path(__file__).resolve().parents[3]
FIXED=Path('/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype')

with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    process=None
    parent=None
    owned={}
    try:
        env={**os.environ,'PYTHONPATH':str(ROOT/'src')+':/private/tmp/t01-type-deps',
             'PDF_TEST_FIXTURE_ROOT':str(FIXED)}
        with (ROOT/'tests/pdf_processing/q01/evidence/full-suite.log').open('w') as log:
            process=subprocess.Popen([str(FIXED/'.venv/bin/python'),str(ROOT/'tests/pdf_processing/q01/unit_suite.py')],
                env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            parent=psutil.Process(process.pid);owned[parent.pid]=parent
            deadline=time.monotonic()+600
            while process.poll() is None:
                for child in parent.children(recursive=True):owned[child.pid]=child
                if time.monotonic()>deadline:raise TimeoutError('Full regression suite deadline')
                time.sleep(.2)
            if process.returncode:raise subprocess.CalledProcessError(process.returncode,process.args)
    finally:
        if process is not None:
            # Freeze the runner before the final descendant inventory. psutil keeps
            # creation identities, protecting against PID reuse during cleanup.
            try:
                if parent is not None and parent.is_running():
                    parent.suspend()
                    for child in parent.children(recursive=True):owned[child.pid]=child
            except psutil.NoSuchProcess:pass
            for child in owned.values():
                try:child.resume();child.terminate()
                except psutil.NoSuchProcess:pass
            _,alive=psutil.wait_procs(list(owned.values()),timeout=5)
            for child in alive:
                try:child.kill()
                except psutil.NoSuchProcess:pass
            process.wait()
            while alive:
                _,alive=psutil.wait_procs(alive,timeout=1)
        fcntl.flock(lock,fcntl.LOCK_UN)
