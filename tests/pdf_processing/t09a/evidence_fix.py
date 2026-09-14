"""Actual-seam regression for retained zero-width combining-mark evidence."""
import fcntl
import hashlib
import json
import subprocess
from run import NS,ROOT,k,run_trial,quiesce

with open('/private/tmp/data-ingestion-pdf-qualification.lock','a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    try:
        k('get','pods')
        # Keep the exact pre-fix producer available for accepted old request replays.
        files={p.name:subprocess.check_output(['git','show','765d548:src/pdf_processing/'+p.name],text=True)
               for p in (ROOT/'src/pdf_processing').glob('*.py')}
        config={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'t09a-package-baseline','namespace':NS},'immutable':True,'data':files}
        subprocess.run(['kubectl','apply','-f','-'],input=json.dumps(config),text=True,check=True)
        subprocess.run(['python3',str(ROOT/'tests/pdf_processing/t09a/setup.py')],check=True)
        k('cp',str(ROOT/'tests/pdf_processing/t09a/verify.py'),'coordinator:/tmp/t09a-test/verify.py')
        run_trial('08','evidence-08',True,['--source-from','fresh-08','--expect-reuse'])
        script='''import json
from pathlib import Path
from pdf_processing.object_store import digest
r=Path('/tmp/t09a-results')
a=json.loads((r/'fresh-08-assembled-document.json').read_text())
b=json.loads((r/'evidence-08-document.json').read_text())
assert a==b
report=json.loads((r/'evidence-08-evidence.json').read_text())
observations=[x for x in report['representation_observations'] if x.get('origin')=='parser_zero_width_combining_mark']
assert len(observations)==2
for x in observations:
 assert x['text_rewritten'] is False and x['status']=='textual_or_mathematical_representation_unconfirmed'
 for g in x['regions']:
  assert g['bbox_top_left_points'][0]==g['bbox_top_left_points'][2]
  assert g['geometry_status']=='zero_width_combining_mark'
  assert g['crop_recipe']['scope']=='full_page_context'
  width,height=report['pages'][str(g['page'])]['size_points']
  assert g['crop_recipe']['box_pixels']==[0,0,width*3,height*3]
  node=next(n for n in report['items'] if n['ref'] in x['refs'])
  assert node['text']=='\\u0338' and node['actual_type']=='text'
result={'raw_document_unchanged':True,'isolated_marks_retained':2,'localization':'unconfirmed; explicit full-page recipe','formula_occurrences':len(report['formula_occurrences'])}
(r/'evidence-fix-checks.json').write_text(json.dumps(result,indent=2))
print(result)'''
        print(k('exec','coordinator','--','/experiment/.venv/bin/python','-c',script),flush=True)
        for sid in ('09','10'):run_trial(sid,'fresh-'+sid,True)
    finally:
        quiesce();fcntl.flock(lock,fcntl.LOCK_UN)
        print('Evidence fix window quiescent; lock released',flush=True)
