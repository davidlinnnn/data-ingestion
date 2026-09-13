"""Run the existing complete regression suite under the shared inference lock."""
import fcntl
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
FIXED=Path('/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype')
with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        env={**os.environ,'PYTHONPATH':str(ROOT/'src')+':/private/tmp/t01-type-deps',
             'PDF_TEST_FIXTURE_ROOT':str(FIXED)}
        with (ROOT/'tests/pdf_processing/t09a/evidence/full-suite.log').open('w') as log:
            subprocess.run([str(FIXED/'.venv/bin/python'),str(ROOT/'tests/pdf_processing/t06/run_unit_suite.py')],
                env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
    finally:fcntl.flock(lock,fcntl.LOCK_UN)
