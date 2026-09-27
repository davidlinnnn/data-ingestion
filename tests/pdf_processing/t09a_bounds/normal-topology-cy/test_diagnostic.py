"""Small Linux check for CY stop boundary, repeat prevention and namespace identity."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

hook=load('cy_hook',ROOT/'sitecustomize.py')
with tempfile.TemporaryDirectory() as temporary:
    hook.ROOT=Path(temporary)/'evidence'
    out=Path(temporary)/'output';out.mkdir()
    namespace={'Path':Path}
    exec(compile("def execute(request):\n out=Path(request['out'])\n (out/'ocr.json').write_text('{}')\n (out/'figure.png').write_bytes(b'crop')\n", '/test/pdf_processing/ocr.py', 'exec'),namespace)
    for expected in ('CY_DIAGNOSTIC_FIRST_COMPONENT_COMPLETE','FileExistsError'):
        sys.settrace(hook.trace)
        try:
            namespace['execute']({'out':str(out),'component':'#/pictures/0'})
        except (RuntimeError,FileExistsError) as error:
            assert str(error)==expected or type(error).__name__==expected
        else:raise AssertionError('diagnostic did not stop')
        finally:sys.settrace(None)
    assert json.loads((hook.ROOT/'planned-stop.json').read_text())['business_success'] is False
    assert (hook.ROOT/'figure.png').read_bytes()==b'crop'
    rows=[json.loads(line) for line in (hook.ROOT/'phases.jsonl').read_text().splitlines()]
    assert [row['stage'] for row in rows]==['ocr_enter','result_written']
    assert all(row['pid']==os.getpid() and row['threads'] and row['start_ticks']>0 for row in rows)
tracer=load('cy_tracer',ROOT/'psi_call_trace.py')
identity=tracer.identity(os.getpid())
assert identity['nspid'][-1]==os.getpid() and identity['nstgid'][-1]==os.getpid()
assert identity['start_ticks']>0 and identity['threads']>0
print('PASS: first output retained then deliberate stop; second attempt blocked before OCR; PID namespace/start-time identity')
