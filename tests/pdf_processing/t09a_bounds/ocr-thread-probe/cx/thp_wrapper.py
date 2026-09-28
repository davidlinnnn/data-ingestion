import ctypes, json, runpy, os
from pathlib import Path
os.environ.pop('NUMPY_MADVISE_HUGEPAGE',None)
libc=ctypes.CDLL(None,use_errno=True)
assert libc.prctl(41,1,0,0,0)==0, ctypes.get_errno()
assert libc.prctl(42,0,0,0,0)==1
Path('/probe/thp-control.json').write_text(json.dumps({'scope':'diagnostic process and descendants','PR_GET_THP_DISABLE':1,'parent_numpy_override':False,'candidate':'CS inherited supervisor THP policy; default OCR pool'}))
Path('/probe/vmstat-before').write_text(Path('/proc/vmstat').read_text())
try:
    runpy.run_path('/probe/run.py',run_name='__main__')

finally:
    Path("/probe/vmstat-after").write_text(Path("/proc/vmstat").read_text())
