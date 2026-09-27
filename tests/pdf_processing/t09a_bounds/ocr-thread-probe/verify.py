"""Replay retained component controls; never runs inference or changes the cluster."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
for name in ('ct','ct2','cu','cv','cw','cx'):
    root=ROOT/name
    controller=read(root/'controller.json')
    assert controller['removed'] and controller['automatic_retry'] is False
    cleanup=read(root/'independent-cleanup.json')
    assert cleanup['container_absent'] and cleanup['held_deployments_off']==32
    assert cleanup['object_memory']=='512Mi' and cleanup['object_ready']
for name,expected in (('ct2',58),('cu',16)):
    root=ROOT/name
    assert read(root/'controller.json')['exit_code']==0
    rows=[json.loads(line) for line in (root/'threads.jsonl').read_text().splitlines()]
    engine=next(row for row in rows if row['label']=='engine_ready')
    assert len(engine['threads'])==expected
reports=[read(ROOT/name/'plain/ocr.json') for name in ('ct2','cu')]
for report in reports:report.pop('seconds_including_engine_load')
assert reports[0]==reports[1]
assert (ROOT/'ct2/plain/figure.png').read_bytes()==(ROOT/'cu/plain/figure.png').read_bytes()
assert read(ROOT/'cx/controller.json')['exit_code']==0
assert read(ROOT/'cx/parser-cleanup.json')['process_absent']
assert read(ROOT/'cx/warm-parser.json')['observation']['ready']
samples=[json.loads(line) for line in (ROOT/'cx/samples.jsonl').read_text().splitlines()]
assert all(float(row['vm_psi']['avg10'])==0 and row['oom']==samples[0]['oom']
           and not any(row['events'][k] for k in ('max','oom','oom_kill')) for row in samples)
policy=read(ROOT/'cx/policy-comparison.json')
assert policy['cw_sample_passes_original_cs_vm_guard'] and policy['cs_trigger_0_18_rejected']
print('PASS: thread-pool contrast/output equality; resident-parser control; unchanged CS VM predicate; cleanup. CS root cause remains unproven.')
