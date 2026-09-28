"""Validate experiment coverage and fidelity metadata, not production behavior."""
import json
from pathlib import Path
E=Path(__file__).resolve().parent/'evidence'
M=E/'matrix'
index=json.loads((M/'index.json').read_text())
assert len(index)==24
ids={}
for r in index:
    variant=r.get('variant',Path(r['out']).name.rsplit('-',1)[1])
    key=(r['fixture'],r['repetition'],variant)
    assert key not in ids;ids[key]=True
    p=M/Path(r['out']).name
    if variant=='whole':
        assert not json.loads((p/'metrics.json').read_text())['errors']
        continue
    children=json.loads((p/'child-diagnostics.json').read_text())
    assert len(children)==(12 if r['fixture']=='native' else 3)
    pages=0;pipelines=set()
    for c in children:
        m=c['metrics.json'];perf=c['perf.json']
        assert not m['errors']
        if m['mode']=='capture':
            pages+=m['page_stage_inputs']['PageAssembleModel']
            if variant=='warm':
                assert perf['session']
                pipelines.add(tuple(perf['pipeline_ids']))
        elif m['mode']=='restore':
            assert not perf['session']
            assert not m['page_stage_inputs'].get('LayoutModel',0)
    assert pages==(51 if r['fixture']=='native' else 2)
    if variant=='warm':assert len(pipelines)==1
    ledger=json.loads((p/'ledger.json').read_text())
    assert sum(x['event']=='registered' for x in ledger)==len(children)
    assert not any(x['event']=='reused' for x in ledger)
result={'trials':len(index),'fresh_prefixes':True,'expected_page_stage_counts':True,'warm_pipeline_id_stable_per_trial':True,'fresh_restore_has_no_page_processing':True,'full_document_equality':'Asserted in each successful runner before its index registration; whole outputs retained in ignored evidence, grouped output assertion precedes S3 prefix deletion.'}
(E/'verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
