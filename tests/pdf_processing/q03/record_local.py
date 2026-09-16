"""Record bounded local delivery evidence; never claim Temporal/K8s acceptance."""
import asyncio
import hashlib
import json
from pathlib import Path
import uuid
from delivery import deliver, serialized_document
from freeze_review import freeze
from q03_fixtures import ROOT, policy
from fixtures import BASELINE, SOURCE
from oracle.score import score
from pdf_processing.processing import encoded

REPO = ROOT.parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

async def main():
    assert freeze() == json.loads((ROOT/'reviewed-representation.json').read_text())
    final, binding, store = await deliver()
    report = binding['relationships']
    candidate = {**report['candidates'], 'relationships': [{**r, 'disposition': 'candidate'} for r in report['resolved']]}
    scores = score(serialized_document(), candidate)
    assert len(scores) == 4 and all(s['structure_pass'] for s in scores)
    private = Path('/private/tmp')/('q03-local-delivery-'+uuid.uuid4().hex)
    private.mkdir()
    (private/'final.json').write_bytes(encoded(final))
    (private/'relationships.json').write_bytes(encoded(binding))
    for label, identity in [('assembly', final['assembly']), ('evidence', final['content_evidence'])]:
        registration = store.resolve(identity)
        assert registration is not None
        (private/label).mkdir()
        for entry in registration['files']:
            (private/label/entry['name']).write_bytes(store.read_artifact(entry))
    producer = {p.name: sha(p) for p in sorted((REPO/'src/pdf_processing').glob('*.py'))}
    (ROOT/'evidence/producer.json').write_bytes(encoded({'producer': producer}))
    inputs = [BASELINE, Path('/private/tmp/t09a-fixtures/08.pdf'), Path('/private/tmp/t09a-code-oracle.json'),
              Path('/private/tmp/aima-quality-candidate/caption-source.json')]
    inputs += [Path(f'/private/tmp/aima-quality-candidate/source-{page:02}.png') for page in (3,5,9,10)]
    inputs += [Path('/private/tmp/aima-p2-main-recheck-20260915')/name for name in
               ('baseline-relationships.json', 'candidate-document.json', 'candidate-relationships.json')]
    files = [p for p in ROOT.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.md','.log')
             and p.name != 'manifest.json' and '__pycache__' not in p.parts]
    files += [REPO/'tests/pdf_processing/q01_q02/runtime.py']
    files += sorted((REPO/'tests/pdf_processing/q02/oracle').rglob('*.py'))
    files += sorted((REPO/'tests/pdf_processing/q02/oracle').rglob('*.json'))
    manifest = {
        'version': 1, 'base_commit': '4571eea1c6492de7c097fe3fa6ce99494c34dbef',
        'issue': 'https://github.com/davidlinnnn/data-ingestion/issues/50',
        'specification': 'https://github.com/davidlinnnn/data-ingestion/issues/47',
        'scope': 'Local checkpoint and seeded finalization; in-memory S3 transport, real source rendering. No actual Temporal/K8s/new native/OCR qualification.',
        'runtime_status': 'NOT_RUN_NEW_CAPACITY_WINDOW_REQUIRED',
        'q04_and_44_acceptance': False, 'source_sha256': SOURCE, 'producer': producer,
        'policy_sha256': hashlib.sha256(encoded(policy())).hexdigest(),
        'relationship_method': 'local-function-block-v1',
        'representation_policy': 'source-reviewed-representation-v1',
        'source_reviews': json.loads((ROOT/'reviewed-representation.json').read_text()),
        'scores': [{k:v for k,v in s.items() if k not in ('members','symbols')} for s in scores],
        'local_result': {'path': str(private), 'final_sha256': sha(private/'final.json'),
                         'relationships_sha256': sha(private/'relationships.json'),
                         'transport': 'MemoryS3; registration names are not shared-storage locators'},
        'private_retained_inputs': [{'path': str(p), 'sha256': sha(p)} for p in inputs],
        'files': {str(p.relative_to(REPO)): sha(p) for p in sorted(set(files))},
        'handoff_gates': ['new-producer actual Activities/shared-storage seeded matrix',
                         'full native/selected OCR and actual checked reuse',
                         'interruption/recovery and affected warm/drain/resource qualification',
                         'Q04 six-fixture acceptance']}
    (ROOT/'evidence/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('four source structures PASS; exact raw extraction/source preserved;', private)

if __name__ == '__main__': asyncio.run(main())
