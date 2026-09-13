"""After replacement, replay exact accepted requests and verify immutable complete refs."""
import fcntl
import json
import subprocess
from run import NS,ROOT,k,run_trial,quiesce

with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        k('cp',str(ROOT/'tests/pdf_processing/t09a/verify.py'),'coordinator:/tmp/t09a-test/verify.py')
        for i,sid in enumerate(('native','06','07','08','09','10')):
            script=f'''from pathlib import Path
root=Path('/tmp/t09a-results')
(root/'replay-{sid}-request.json').write_bytes((root/'fresh-{sid}-request.json').read_bytes())'''
            k('exec','coordinator','--','/experiment/.venv/bin/python','-c',script)
            run_trial(sid,'replay-'+sid,i==0,['--expect-reuse'])
            check=f'''import json
from pathlib import Path
r=Path('/tmp/t09a-results')
a=json.loads((r/'fresh-{sid}.json').read_text());b=json.loads((r/'replay-{sid}.json').read_text())
assert a['result']['processing_result']==b['result']['processing_result']
assert all(s['reused'] for s in b['result']['steps'])
print('Identical final and all registered steps reused: {sid}')'''
            print(k('exec','coordinator','--','/experiment/.venv/bin/python','-c',check),flush=True)
    finally:
        quiesce();fcntl.flock(lock,fcntl.LOCK_UN)
        print('Replay window quiescent; lock released',flush=True)
