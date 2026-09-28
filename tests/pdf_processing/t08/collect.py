"""Read-only final attribution and rollout comparison; never exports content bytes."""
import asyncio
import json
from pathlib import Path
import boto3
from temporalio.client import Client
from pdf_processing.object_store import Store, digest

OUT=Path('/tmp/t08-results')

async def main():
    store=Store(boto3.client('s3',endpoint_url='http://objects:9000'),'t08','rollout')
    client=await Client.connect('temporal:7233')
    routes=json.loads(Path('/tmp/t08-routes.json').read_text())
    records={n:json.loads((OUT/(n+'.json')).read_text()) for n in ('queued','loss','new','mixed','drain')}
    def read(identity,name):
        return json.loads(store.read_artifact(next(f for f in store.resolve(identity)['files'] if f['name']==name)))
    finals={n:read(r['result']['processing_result'],'processing-result.json') for n,r in records.items()}
    before=records['queued']['result']
    after=records['new']['result']
    reused=lambda r:[s['operation'] for s in r['steps'] if s['stage'] in ('group','assembly')]
    assert reused(before)==reused(after)
    assert before['parsed_result']!=after['parsed_result']
    assert before['selection']!=after['selection']
    assert before['processing_result']!=after['processing_result']
    assert finals['queued']['content_evidence']!=finals['new']['content_evidence']
    assert {o['operation'] for o in finals['queued']['enrichments']}.isdisjoint(o['operation'] for o in finals['new']['enrichments'])
    # Every preserved original registration and payload remains checked-readable.
    originals=[*reused(before),before['parsed_result'],before['selection'],
        before['processing_result'],finals['queued']['content_evidence'],
        *(o['operation'] for o in finals['queued']['enrichments'])]
    hashes={}
    for identity in originals:
        reg=store.resolve(identity)
        hashes[identity]={f['name']:digest(store.read_artifact(f)) for f in reg['files']}
    # No pending accepted workflow may be ignored when recording retirement.
    open_runs=[]
    async for execution in client.list_workflows("ExecutionStatus = 'Running'"):
        open_runs.append(execution.id)
    assert not open_runs,open_runs
    report={'same_registered_parsing_and_assembly':reused(before),
        'new_request_bound_parsed_selection_ocr_evidence_final':True,
        'original_checked_artifact_hashes':hashes,'open_executions':open_runs,
        'canonical_accepted':False,'image_model_upgrade_claimed':False}
    (OUT/'comparison.json').write_text(json.dumps(report,indent=2))
    print('Cross-release reuse, distinct bindings, original integrity and zero open executions: PASS')

if __name__=='__main__':asyncio.run(main())
