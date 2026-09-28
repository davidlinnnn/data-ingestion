"""Replay CZ bounded contrast and output equality from retained evidence."""
import gzip
import json
from pathlib import Path
from summarize import direct_calls
ROOT=Path(__file__).resolve().parent/'first-window-evidence'
read=lambda path:json.loads((ROOT/path).read_text())
phases=[json.loads(line) for line in (ROOT/'ocr-diagnostic/phases.jsonl').read_text().splitlines()]
by={row['stage']:row for row in phases}
trace=[json.loads(line) for line in gzip.decompress((ROOT/'object-stall-trace.jsonl.gz').read_bytes()).splitlines()]
assert trace[-1]['kind']=='end'
for stats in trace[-1]['buffer_stats'].values():
    values=dict(line.split(':',1) for line in stats.splitlines())
    assert all(int(values[key])==0 for key in ('overrun','commit overrun','dropped events'))
calls,unknown=direct_calls(trace,'/')
ocr=[call for call in calls if call['task'].get('nstgid',[-1])[-1]==by['ocr_enter']['pid']
     and call['task'].get('tgid_start_ticks')==by['ocr_enter']['start_ticks']]
assert len(ocr)==30 and len({call['task']['tid'] for call in ocr})==4
assert all(by['inference_start']['time']<=call['time']<=by['inference_ready']['time'] for call in ocr)
created=set(by['engine_ready']['threads'])-set(by['engine_start']['threads'])
assert len(created.intersection(call['task']['nspid'][-1] for call in ocr))==3
assert all(call['time']<by['inference_start']['time'] for call in unknown)
analysis=read('ocr-allocation-attribution.json')
assert analysis['vm_counter_delta']['pgscan_direct']>0 and analysis['vm_counter_delta']['compact_stall']==0
assert analysis['maximum_vm_full_avg10']==0
assert analysis['controller_stop']['reason']=='Pod workload failed; no retry'
assert by['result_written']['time']<analysis['controller_stop']['time']
activity=read('ocr-activity.json');assert activity['attempt']==1 and activity['non_retryable']
result=read('temporal-reconciliation.json')[0]
assert result['business']['error']['code']=='cz_diagnostic_first_component_complete'
assert result['business']['processing_complete'] is False and result['cancellation_time'] is None
assert read('independent-cleanup.json')['status']=='PASS'
reference=ROOT.parent.parent/'normal-topology-cy/first-window-evidence/ocr-diagnostic'
a=read('ocr-diagnostic/ocr.json');b=json.loads((reference/'ocr.json').read_text())
for value in (a,b):value.pop('seconds_including_engine_load')
assert a==b
assert (ROOT/'ocr-diagnostic/figure.png').read_bytes()==(reference/'figure.png').read_bytes()
assert read('ocr-diagnostic/runtime-override.json')['EngineConfig.onnxruntime.intra_op_num_threads']==4
assert len(by['engine_ready']['threads'])==16
print('PASS: 30 allocator entries/4 exact OCR threads; VM avg10=0; full OCR/crop equal CY; planned stop/no retry and cleanup')
