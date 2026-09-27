import ctypes, json, runpy, os
from pathlib import Path
os.environ.pop('NUMPY_MADVISE_HUGEPAGE',None)
libc=ctypes.CDLL(None,use_errno=True)
assert libc.prctl(41,1,0,0,0)==0, ctypes.get_errno()
assert libc.prctl(42,0,0,0,0)==1
Path('/probe/thp-control.json').write_text(json.dumps({'scope':'diagnostic process and descendants','PR_GET_THP_DISABLE':1,'parent_numpy_override':False,'candidate':'OCR-only Execution environment'}))
Path('/probe/vmstat-before').write_text(Path('/proc/vmstat').read_text())
try:
    runpy.run_path('/probe/run.py',run_name='__main__')

finally:
    Path("/probe/vmstat-after").write_text(Path("/proc/vmstat").read_text())

a=json.loads(Path('/probe/plain/ocr.json').read_text()); b=json.loads(Path('/probe/baseline/ocr.json').read_text())
for value in (a,b): value.pop('seconds_including_engine_load')
assert a==b, 'full OCR report changed'
assert Path('/probe/plain/figure.png').read_bytes()==Path('/probe/baseline/figure.png').read_bytes()
Path('/probe/baseline-comparison.json').write_text(json.dumps({'full_report_except_timing_equal':True,'crop_equal':True}))
