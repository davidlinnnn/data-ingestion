"""Apply synthetic answers to every reachable cached-S0 owner, without inference."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import producer as p
from controls import block, bundle, content

HERE=Path(__file__).resolve().parent


def main():
    clock=json.loads((HERE.parent/'registration.json').read_text())['branches']['A']
    assert datetime.now(timezone.utc)<datetime.fromisoformat(clock['deadline'])
    inventory=json.loads((HERE/'inventory.json').read_text())
    assert hashlib.sha256((HERE/'producer.py').read_bytes()).hexdigest()==inventory['method_sha256']
    outcomes=[]
    for source in inventory['sources']:
        raw_path=p.REPO/source['document_path']
        assert hashlib.sha256(raw_path.read_bytes()).hexdigest()==source['document_sha256']
        raw=json.loads(raw_path.read_text())
        rows=[r for r in source['rows'] if r['eligible']]
        refs=[r['target_ref'] for r in rows]
        answers=[]
        for row in rows:
            kind='formula' if row['kind'] in {'formula','formula_picture_envelope'} else 'paragraph'
            answers.append(content(block(kind,'MOCK_SOURCE_NOT_TRANSCRIPTION','math' if kind=='formula' else 'text')))
        scope,inputs,response=bundle(raw,refs,answers)
        before=p.digest(raw)
        result=p.apply(raw,scope,inputs,response)
        assert p.digest(raw)==before
        folder=HERE/'cached-mock'/source['source'];folder.mkdir(parents=True,exist_ok=True)
        (folder/'working.md').write_text(result['working'])
        (folder/'association.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        formula_rows=[r for r in rows if r['kind']=='formula']
        outcomes.append({'source':source['source'],'mock_delivered_owners':len(rows),
                         'empty_native_formula_owners_delivered':sum(not p.legacy.item(raw,r['target_ref']).get('text') for r in formula_rows),
                         'provider_unchanged':True,'non_target_literals_unchanged':True,
                         'model_outputs':0,'semantic_acceptance':False})
    result={'scope':'current pinned cached-S0 structural mock; not model scores',
            'outcomes':outcomes,'model_calls':0,'actual_inference_delivered_targets':0,
            'complete_source_coverage_claim':False,'completed_at':datetime.now(timezone.utc).isoformat()}
    (HERE/'cached-mock-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
