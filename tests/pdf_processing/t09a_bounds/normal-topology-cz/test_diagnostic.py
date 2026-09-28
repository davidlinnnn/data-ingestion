"""Small Linux check for CZ stop boundary, repeat prevention and namespace identity."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent
subprocess.run([sys.executable,'-B','-c',
    'import sys,sitecustomize; assert sys.gettrace() is sitecustomize.trace; assert sys.getprofile() is sitecustomize.profile',
    'pdf_processing.ocr'], check=True, env={**os.environ,'PYTHONPATH':str(ROOT),
    'PYTHONDONTWRITEBYTECODE':'1','PDF_PROCESS_LIFECYCLE_FD':'0'})

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

hook=load('cy_hook',ROOT/'sitecustomize.py')
with tempfile.TemporaryDirectory() as temporary:
    hook.ROOT=Path(temporary)/'evidence'
    out=Path(temporary)/'output';out.mkdir()
    namespace={'Path':Path,'RapidOCR':lambda:lambda crop:None,'crop':None}
    import linecache
    source="def execute(request):\n out=Path(request['out'])\n result = RapidOCR()(crop)\n (out/'ocr.json').write_text('{}')\n (out/'figure.png').write_bytes(b'crop')\n"
    linecache.cache['/test/pdf_processing/ocr.py']=(len(source),None,source.splitlines(True),'/test/pdf_processing/ocr.py')
    exec(compile(source,'/test/pdf_processing/ocr.py','exec'),namespace)
    for expected in ('CZ_DIAGNOSTIC_FIRST_COMPONENT_COMPLETE','FileExistsError'):
        sys.settrace(hook.trace)
        try:
            namespace['execute']({'out':str(out),'component':'#/pictures/0'})
        except (RuntimeError,FileExistsError) as error:
            assert str(error)==expected or type(error).__name__==expected
        else:raise AssertionError('diagnostic did not stop')
        finally:sys.settrace(None)
    assert json.loads((hook.ROOT/'planned-stop.json').read_text())['business_success'] is False
    assert (hook.ROOT/'figure.png').read_bytes()==b'crop'
    assert json.loads((hook.ROOT/'runtime-override.json').read_text())['EngineConfig.onnxruntime.intra_op_num_threads']==4
    from rapidocr import RapidOCR
    engine=RapidOCR()
    assert engine.cfg.EngineConfig.onnxruntime.intra_op_num_threads==4
    for model in (engine.text_det,engine.text_cls,engine.text_rec):
        assert model.session.session.get_session_options().intra_op_num_threads==4
    failure=json.loads((out/'failure.json').read_text())
    sys.path.insert(0,str(ROOT.parents[3]/'src'))
    from pdf_processing.processing import reject
    from temporalio.exceptions import ApplicationError
    try:reject(failure['code'],failure['category'])
    except ApplicationError as error:assert error.non_retryable
    else:raise AssertionError('planned stop must prevent activity retry')
    rows=[json.loads(line) for line in (hook.ROOT/'phases.jsonl').read_text().splitlines()]
    assert [row['stage'] for row in rows]==['ocr_enter','result_written']
    assert all(row['pid']==os.getpid() and row['threads'] and row['start_ticks']>0 for row in rows)
tracer=load('cy_tracer',ROOT/'psi_call_trace.py')
identity=tracer.identity(os.getpid())
assert identity['nspid'][-1]==os.getpid() and identity['nstgid'][-1]==os.getpid()
assert identity['start_ticks']>0 and identity['threads']>0
assert identity['tgid_start_ticks']==identity['start_ticks']
print('PASS: first output retained then deliberate stop; second attempt blocked before OCR; PID namespace/start-time identity')
