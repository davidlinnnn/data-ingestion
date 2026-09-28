"""Summarize copied real evidence. No success inferred from absent files."""
from collections import Counter
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
E=ROOT/'evidence-linux'
S=ROOT.parent/'PROTOTYPE-wipe-me/linux-k8s-evidence'
summary={}
for mode in ('normal','fault','reuse'):
    result=json.loads((E/f'{mode}-result.json').read_text())
    ledger=json.loads((E/f'{mode}-ledger.json').read_text())
    # Reuse ledger also contains the earlier fault trial; delimit using history/run start.
    history=json.loads((E/f'{mode}-history.json').read_text())
    from datetime import datetime
    begin=datetime.fromisoformat(history['events'][0]['eventTime'].replace('Z','+00:00')).timestamp()
    events=[v for v in ledger if v['time']>=begin]
    counts=Counter(); io=Counter()
    for entry in events:
        for line in entry.get('events','').splitlines():
            item=json.loads(line)
            counts[item['stage']]+=len(item['pages'])
        io.update(entry.get('io_delta',{}))
    accepted=[v for v in events if v['event']=='registered']
    starts=[v for v in events if v['event']=='started']
    # Starting again after a durable registration of that identity would violate reuse.
    violations=[]
    for entry in starts:
        if any(a['identity']==entry['identity'] and a['time']<entry['time'] for a in ledger if a['event']=='registered'):
            violations.append(entry['identity'])
    assert not violations
    ocr=[v['ocr'] for v in accepted if v.get('ocr')]
    summary[mode]={'wall_seconds':result['wall_seconds'],'started_activities':len(starts),
        'registered':len(accepted),'reused':sum(v['event']=='reused' for v in events),
        'observed_completed_stage_inputs':dict(counts),'io_successful_requests':dict(io),
        'accepted_payload_bytes':sum(v['payload_bytes'] for v in accepted),
        'completed_identity_recomputation':violations,
        'ocr_label_recall':ocr[-1]['label_recall'] if ocr else None}
    if mode=='fault':
        delays=[]
        for ready in events:
            if ready['event']=='fault_ready':
                next_events=[v for v in events if v['identity']==ready['identity'] and v['time']>ready['time'] and v['event'] in ('registered','reused')]
                assert next_events
                delays.append({'point':ready['point'],'seconds_to_registered_or_reused':next_events[0]['time']-ready['time']})
        summary[mode]['fault_recovery']=delays
summary['limits']='Single local kind node; stage counts are persisted completed-call observations, not exact in-flight model invocations. Upload polling adds up to one second per accepted Activity. I/O excludes failed requests and process-lost counters. No production throughput/HA claim.'
(E/'summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
