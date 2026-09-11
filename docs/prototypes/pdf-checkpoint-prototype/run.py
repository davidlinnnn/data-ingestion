"""One-command reproduction of the reconstruction gate, with fresh output directories."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parent
PYTHON=ROOT/'.venv/bin/python'
PDF=ROOT/'fixtures/llm-survey-2303.18223v1.pdf'
expected='d58be5fc39608dc9aec45194c602436d793f2f2bf56f267d0e38d6258a9f7a9e'
PDF.parent.mkdir(exist_ok=True)
if not PDF.exists():
    urllib.request.urlretrieve('https://arxiv.org/pdf/2303.18223v1',PDF)
assert hashlib.sha256(PDF.read_bytes()).hexdigest()==expected
subprocess.run([str(PYTHON),str(ROOT/'prepare_models.py')],check=True)
subprocess.run([str(PYTHON),str(ROOT/'fixtures.py')],check=True)
base=ROOT/'PROTOTYPE-wipe-me'/f'reproduction-{time.time_ns()}'
base.mkdir(parents=True)
for label,pdf,flags in [('native',PDF,[]),('scan',ROOT/'fixtures/scan-pages-3-5.pdf',['--scan'])]:
    for mode in ('baseline','capture','restore'):
        out=base/f'{label}-{mode}'
        args=[str(PYTHON),str(ROOT/'experiment.py'),mode,str(pdf),'--out',str(out),*flags]
        if mode=='capture': args+=['--crash-before-assembly']
        if mode=='restore': args+=['--checkpoint',str(base/f'{label}-capture')]
        with (base/f'{label}-{mode}.log').open('w') as log:
            r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'HF_HUB_OFFLINE':'1'})
        assert r.returncode==(73 if mode=='capture' else 0), f'Inspect {base}/{label}-{mode}.log'
    subprocess.run([str(PYTHON),str(ROOT/'compare.py'),str(base/f'{label}-baseline'),str(base/f'{label}-restore'),'--out',str(base/f'{label}-comparison.json')],check=True)
print(f'Reconstruction gate passed. Results: {base}')
print('Run sizing.py and recovery.py for the separately documented local Temporal experiments.')
