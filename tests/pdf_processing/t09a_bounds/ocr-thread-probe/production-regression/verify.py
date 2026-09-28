"""Replay the real production-path regression artifacts."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
read=lambda name:json.loads((ROOT/name).read_text())
assert read('red2/controller.json')['exit_code']==1
assert read('red2/thread-budget-check.json')['intra_op_threads']==[0,0,0]
assert 'component OCR thread budget not applied' in (ROOT/'red2/observed/process.log').read_text()
assert read('green/controller.json')['exit_code']==0
assert read('green/thread-budget-check.json')['intra_op_threads']==[4,4,4]
assert read('green/baseline-comparison.json')=={'full_report_except_timing_equal':True,'crop_equal':True}
for label in ('red','red2','green'):
    assert read(label+'/controller.json')['removed']
    cleanup=read(label+'/independent-cleanup.json')
    assert cleanup['container_absent'] and cleanup['held_deployments_off']==32 and cleanup['object_memory']=='512Mi'
print('PASS: real OCR constructor assertion red before / green after; complete report and crop preserved; cleanup')
