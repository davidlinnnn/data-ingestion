"""Host controller; all mutations are confined to the T07 coordinator /tmp."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
NS='pdf-t07-validation'
def k(*args,**kw):return subprocess.run(['kubectl','-n',NS,*args],check=True,**kw)
k('cp',str(ROOT/'tests/pdf_processing/t07/matrix.py'),'coordinator:/tmp/t07-matrix.py')
for case in sys.argv[1:] or ('baseline','ocr','unrelated','policy','revision','bytes','group-plan','parser-implementation','parser','legacy-v1','legacy-v2','unauthorized'):
    package={p.name:p.read_text() for p in (ROOT/'src/pdf_processing').glob('*.py')}
    if case=='ocr':package['ocr.py']=package['ocr.py'].replace("'seconds_including_engine_load':", "'qualification_implementation': 't07-b',\n        'seconds_including_engine_load':")
    if case=='unrelated':package['temporal.py']+='\nQUALIFICATION_REVISION = "unrelated-t07-b"\n'
    if case=='parser-implementation':package['parse.py']=package['parse.py'].replace('report = {"pid":', 'report = {"qualification_implementation": "parser-b", "pid":')
    writer="import json,sys,pathlib; p=pathlib.Path('/tmp/t07-runtime/pdf_processing');p.mkdir(parents=True,exist_ok=True); [(p/n).write_text(s) for n,s in json.load(sys.stdin).items()]"
    k('exec','-i','coordinator','--','/experiment/.venv/bin/python','-c',writer,input=json.dumps(package),text=True)
    k('exec','coordinator','--','env','PYTHONPATH=/tmp/t07-runtime','/experiment/.venv/bin/python','/tmp/t07-matrix.py',case)
k('cp','coordinator:/tmp/t07-matrix',str(ROOT/'tests/pdf_processing/t07/evidence/matrix'))
