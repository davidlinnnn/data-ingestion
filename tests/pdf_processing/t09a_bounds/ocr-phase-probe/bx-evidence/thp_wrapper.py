import ctypes, json, runpy
from pathlib import Path
libc=ctypes.CDLL(None,use_errno=True)
assert libc.prctl(41,1,0,0,0)==0, ctypes.get_errno()
assert libc.prctl(42,0,0,0,0)==1
Path('/probe/thp-control.json').write_text(json.dumps({'scope':'diagnostic process and descendants','PR_GET_THP_DISABLE':1}))
runpy.run_path('/source/tests/pdf_processing/t09a_bounds/ocr-phase-probe/run.py',run_name='__main__')
