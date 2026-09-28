"""Replay CY exact OCR ownership and stop ordering from retained evidence."""
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
assert len(ocr)==230 and len({call['task']['tid'] for call in ocr})==18
assert all(by['inference_start']['time']<=call['time']<=by['inference_ready']['time'] for call in ocr)
created=set(by['engine_ready']['threads'])-set(by['engine_start']['threads'])
assert len(created.intersection(call['task']['nspid'][-1] for call in ocr))==17
assert all(call['time']<by['inference_start']['time'] for call in unknown)
analysis=read('ocr-allocation-attribution.json')
assert analysis['vm_counter_delta']['pgscan_direct']>0 and analysis['vm_counter_delta']['compact_stall']==0
assert analysis['first_positive_vm_avg10']['psi_full_avg10']==.18
assert by['result_written']['time']<analysis['controller_stop']['time']
activity=read('ocr-activity.json');assert activity['attempt']==1 and activity['non_retryable']
result=read('temporal-reconciliation.json')[0]
assert result['business']['error']['code']=='cy_diagnostic_first_component_complete'
assert result['business']['processing_complete'] is False and result['cancellation_time'] is None
assert read('independent-cleanup.json')['status']=='PASS'
print('PASS: 230 stalls/18 threads exactly map to OCR inference;17 engine-created threads; reclaim without compaction; planned non-retryable stop then delayed VM guard; cleanup')
