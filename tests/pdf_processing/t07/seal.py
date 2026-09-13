"""Verify final tested producer attribution and hash the reviewable evidence set."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
producer={p.name:sha(p) for p in (ROOT/'src/pdf_processing').glob('*.py')}
cases=('baseline','ocr','unrelated','policy','revision','bytes','group-plan','parser-implementation','parser','legacy-v1','legacy-v2','unauthorized')
summary={}
for case in cases:
    report=json.loads((HERE/f'evidence/matrix/{case}.json').read_text())
    changed={k for k,v in report['producer'].items() if producer[k]!=v}
    expected={'ocr':{'ocr.py'},'unrelated':{'temporal.py'},'parser-implementation':{'parse.py'}}.get(case,set())
    assert changed==expected,(case,changed,expected)
    assert set(producer)==set(report['producer'])
    wanted='failed' if case in ('parser','unauthorized') else 'parsed_ready' if case=='legacy-v1' else 'complete'
    assert report['result']['status']==wanted,(case,report['result'])
    summary[case]={'status':wanted,'request_id':report['request']['request_id'],
        'changed_producers':sorted(changed),'steps':[{k:s[k] for k in ('stage','operation','reused')} for s in report['result']['steps']],
        'child_process_modules':report.get('child_process_modules')}
for case in ('ocr','policy','unrelated'):
    assert summary[case]['child_process_modules'] is not None
    assert 'pdf_processing.parse' not in summary[case]['child_process_modules']
assert summary['ocr']['child_process_modules'].count('pdf_processing.ocr')==4
runtime=json.loads((HERE/'evidence/runtime.json').read_text());runtime['producer']=producer
(HERE/'evidence/runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
(HERE/'evidence/summary.json').write_text(json.dumps(summary,indent=2)+'\n')
paths=[*(ROOT/'src/pdf_processing').glob('*.py'),ROOT/'src/pdf_processing/README.md',
       ROOT/'deploy/pdf-processing/worker.py',*HERE.glob('*.py'),*HERE.glob('*.md'),
       *(p for p in (HERE/'evidence').rglob('*') if p.is_file() and p.name!='manifest.json')]
manifest={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
(HERE/'evidence/manifest.json').write_text(json.dumps({'base':'42f90f4da93ac7ad702744ba1870300ee34a4ebf','sha256':manifest},indent=2)+'\n')
print('Final producer attribution and evidence manifest: PASS')
