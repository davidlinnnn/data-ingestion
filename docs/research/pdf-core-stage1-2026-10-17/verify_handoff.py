"""Check sealed stage1 evidence and stop decisions without opening evaluator answers."""
from datetime import datetime
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    registration=read(HERE/'registration.json')
    assert sha(REPO/'docs/research/pdf-core-three-stage-plan-2026-10-17.md')==registration['plan_sha256']
    inventory=read(HERE/'A/inventory.json')
    assert sha(HERE/'A/inventory.json')=='8f1961552cd6574a5d6f29614b1f5c297362d6310d63140ceb096ae349cbd593'
    assert sha(HERE/'A/producer.py')==inventory['method_sha256']
    refs=0
    for source in inventory['sources']:
        assert sha(REPO/source['document_path'])==source['document_sha256']
        assert sha(REPO/source['pdf']['path'])==source['pdf']['sha256']
        refs+=2
    for name in ['B/registration.json','C/evidence-hashes.json','C/sdk-source-hashes.json']:
        value=read(HERE/name)
        maps=[value['method_hashes'],value['public_sdk_source_hashes']] if name.startswith('B') else [value]
        for mapping in maps:
            for filename,expected in mapping.items():
                path=Path(filename) if Path(filename).is_absolute() else REPO/filename
                assert 'holdout' not in str(path).lower()
                if isinstance(expected,dict):expected=expected['sha256']
                assert sha(path)==expected,(name,filename)
                refs+=1
    a=read(HERE/'A/results.json');b=read(HERE/'B/results.json');c=read(HERE/'C/results.json')
    assert a['full_coverage_gate']=='fail' and b['single_page_gate']=='pass' and b['multipage_gate']=='fail'
    assert c['integration_gate']=='pass' and c['full_C_readiness']=='partial'
    assert len(read(HERE/'A/controls-results.json')['positive_controls'])==7
    assert read(HERE/'A/controls-results.json')['legacy_negative_controls']==23
    assert b['negative_count']==30 and not b['errors']
    assert c['second_process']['relocated_bundle_verified'] and c['pinned_cached_S0_second_process']['relocated_bundle_verified']
    for branch in ['A','B','C']:
        r=read(HERE/branch/'registration.json')
        completed=r.get('completed_at',r.get('finished_at'))
        assert datetime.fromisoformat(completed)<=datetime.fromisoformat(r['deadline'])
    assert registration['ready_for_stage2'] is False and registration['ready_for_stage3'] is False
    assert registration['remote_calls']==registration['local_model_inference']==0
    evidence=[]
    for path in sorted(HERE.rglob('*')):
        if path.is_file() and 'A-evaluator' not in path.parts and path.name not in {'handoff-verification.json','artifact-hashes.json'}:
            evidence.append({'path':str(path.relative_to(HERE)),'sha256':sha(path),'bytes':path.stat().st_size})
    (HERE/'artifact-hashes.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    result={'status':'pass','meaning':'handoff internally consistent; full stage1 method not passed',
            'history_and_sdk_references_verified':refs,'artifact_files_hashed':len(evidence),
            'producer_inventory_frozen':True,'evaluator_answers_opened_by_verifier':False,
            'remote_calls':0,'ready_for_stage2':False,'ready_for_stage3':False}
    (HERE/'handoff-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
