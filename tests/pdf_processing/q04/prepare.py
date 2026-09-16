"""Freeze portable private inputs/oracles before any service access. No cluster calls."""
import argparse
import copy
import json
from pathlib import Path
import shutil

from consumer import ROOT, require, sha


EDGES = [('3/0', '4/14', False), ('4/2', '5/10', False),
         ('5/0', '6/14', False), ('8/4', '9/11', False), ('5/0', '6/6', True),
         ('3/36', '3/37', True), ('3/36', '3/38', True), ('3/36', '3/39', True)]


def prepare(manifest, profile_path, oracle_dir, checkpoints, transcript, out, references):
    pinned = json.loads((Path(__file__).with_name('fixtures.json')).read_text())
    source_manifest = json.loads(manifest.read_text())
    require({e['id'] for e in source_manifest} == {e['id'] for e in pinned}, 'six fixture inventory required')
    profile = json.loads(profile_path.read_text())
    producer = {p.name: sha(p.read_bytes()) for p in (ROOT/'src/pdf_processing').glob('*.py')}
    require(profile['method']['continuation'] == {'version': 'column-edge-continuation-v1', 'sha256': producer['continuation.py']}, 'freeze runtime continuation method first')
    require(profile.get('group_pages', 5) == 5, 'fixed five-page groups')
    # Validate every input before creating a new bundle.
    entries = []
    for item in pinned:
        source = next(x for x in source_manifest if x['id'] == item['id'])
        require(sha(Path(source['pdf']).read_bytes()) == item['sha256'], 'fixture bytes drift')
        require(sha(Path(source['original']).read_bytes()) == item['original_sha256'], 'original bytes drift')
        require(source['source_revision'] == item['source_revision'], 'Source Revision drift')
        review = copy.deepcopy(source['review'])
        require([review['original_pages'][str(i+1)] for i in range(len(item['original_pages']))] == item['original_pages'], 'source page map drift')
        entries.append({**item, 'review': review})
    names = ('06-table-full-audit.json', '07-table-full-audit.json', 'new-source-oracle.json')
    files = {name: (oracle_dir/name).read_bytes() for name in names}
    files['quality-oracle.json'] = (ROOT/'tests/pdf_processing/t06/quality-oracle.json').read_bytes()
    files['aima-code.json'] = transcript.read_bytes()
    historical = json.loads((ROOT/'tests/pdf_processing/t09a/evidence/code-source-oracle.json').read_text())
    texts = json.loads(files['aima-code.json'])
    for row in historical:
        value = next(t for t in texts if t['processed_page'] == row['processed_page'])
        require(sha(value['source_native_text'].encode()) == row['source_text_sha256'], 'AIMA transcript drift')
    checkpoint_hashes = json.loads((ROOT/'tests/pdf_processing/t09a_r2/evidence/source-localization.json').read_text())['checkpoint_sha256']
    anchors = {}
    for a, b, _ in EDGES:
        for key in (a, b):
            page, cid = map(int, key.split('/'))
            path = checkpoints/f'page-{page:04}.json'
            require(sha(path.read_bytes()) == checkpoint_hashes[path.name], 'Q01 checkpoint drift')
            value = json.loads(path.read_text())
            element = next(e['value'] for e in value['assembled']['elements'] if e['value']['cluster']['id'] == cid)
            anchors[key] = {'page': page, 'bbox': element['cluster']['bbox'], 'text': element['text']}
    files['continuation-oracle.json'] = json.dumps({'authority': 'Q01 SOURCE-REVIEW.md',
        'anchors': anchors, 'edges': [{'members': [a, b], 'joined': joined} for a, b, joined in EDGES]}, indent=2).encode()
    matrix = json.loads((ROOT/'tests/pdf_processing/t09a_r3/evidence/20260914-0b537d0-c/matrix.json').read_text())
    graph_hashes = {sid: next(r['checks']['document_sha256'] for r in matrix if r['trial'] == 'fresh-'+sid) for sid in ('native', '06', '07', '09', '10')}
    graph_hashes['08'] = json.loads((ROOT/'tests/pdf_processing/q01/evidence/checkpoint.json').read_text())['sha256']['corrected']
    for sid, digest in graph_hashes.items():
        require(sha((references/(sid+'.json')).read_bytes()) == digest, 'historical graph reference drift')
    out.mkdir(parents=True, exist_ok=False)
    (out/'references').mkdir()
    for sid in graph_hashes:
        shutil.copyfile(references/(sid+'.json'), out/'references'/(sid+'.json'))
    (out/'oracles').mkdir()
    for name, raw in files.items():
        (out/'oracles'/name).write_bytes(raw)
    (out/'fixtures').mkdir()
    (out/'originals').mkdir()
    for entry in entries:
        source = next(x for x in source_manifest if x['id'] == entry['id'])
        shutil.copyfile(source['pdf'], out/'fixtures'/(entry['id']+'.pdf'))
        shutil.copyfile(source['original'], out/'originals'/(entry['id']+'.pdf'))
    inventory = {'version': 1, 'producer': producer, 'base_profile': profile, 'fixtures': entries,
        'reference_graphs': graph_hashes,
        'oracles': {name: sha(raw) for name, raw in files.items()},
        'test_files': {str(p.relative_to(ROOT)): sha(p.read_bytes()) for root in
            (Path(__file__).parent, ROOT/'tests/pdf_processing/q02/oracle') for p in root.rglob('*') if p.is_file() and p.suffix in ('.py', '.json') and 'evidence' not in p.parts},
        'representation': json.loads((ROOT/'tests/pdf_processing/q03/reviewed-representation.json').read_text())}
    (out/'inputs.json').write_text(json.dumps(inventory, indent=2)+'\n')
    return inventory


def verify_bundle(root):
    bundle = json.loads((root/'inputs.json').read_text())
    for entry in bundle['fixtures']:
        for directory, field in [('fixtures', 'sha256'), ('originals', 'original_sha256')]:
            require(sha((root/directory/(entry['id']+'.pdf')).read_bytes()) == entry[field], 'bundle source drift')
    for sid, digest in bundle['reference_graphs'].items():
        require(sha((root/'references'/(sid+'.json')).read_bytes()) == digest, 'bundle graph reference drift')
    for name, digest in bundle['oracles'].items():
        require(sha((root/'oracles'/name).read_bytes()) == digest, 'bundle oracle drift')
    actual = {p.name: sha(p.read_bytes()) for p in (ROOT/'src/pdf_processing').glob('*.py')}
    require(actual == bundle['producer'], 'bundle producer drift')
    for name, digest in bundle['test_files'].items():
        require(sha((ROOT/name).read_bytes()) == digest, 'bundle harness drift; prepare a new bundle')
    return bundle


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'profile', 'oracles', 'checkpoints', 'transcript', 'out', 'references'):
        cli.add_argument('--'+name, type=Path, required=True)
    args = cli.parse_args()
    prepare(args.manifest, args.profile, args.oracles, args.checkpoints, args.transcript, args.out, args.references)
    print('Private input bundle prepared; no runtime qualification performed.')
