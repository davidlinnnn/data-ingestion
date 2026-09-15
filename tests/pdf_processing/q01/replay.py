"""Private checkpoint replay; never rewrites historical outputs or upstream code."""
import hashlib
import json
import inspect
import importlib.metadata
from pathlib import Path
import sys
from docling_core.types.doc import BoundingBox, RefItem, Size
from docling_ibm_models.reading_order.reading_order_rb import PageElement, ReadingOrderPredictor

ROOT = Path(__file__).resolve().parent
CHECKPOINTS = Path('/private/tmp/t09a-r2-20260914/checkpoints')


def load():
    expected = json.loads((ROOT.parent / 't09a_r2/evidence/source-localization.json').read_text())
    assert hashlib.sha256(Path(inspect.getfile(ReadingOrderPredictor)).read_bytes()).hexdigest() == expected['predictor_source_sha256']
    assert {name:importlib.metadata.version(name) for name in expected['upstream_packages']} == expected['upstream_packages']
    elements = []
    for path in sorted(CHECKPOINTS.glob('page-*.json')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected['checkpoint_sha256'][path.name]
        page = json.loads(path.read_text())
        for entry in page['assembled']['elements']:
            v = entry['value']
            box = BoundingBox.model_validate(v['cluster']['bbox']).to_bottom_left_origin(page['size']['height'])
            elements.append(PageElement(cid=len(elements), ref=RefItem(cref=f"#/{page['page_no']}/{v['cluster']['id']}"),
                text=v.get('text') or '', page_no=page['page_no'], page_size=Size.model_validate(page['size']),
                label=v['label'], l=box.l, r=box.r, t=box.t, b=box.b, coord_origin=box.coord_origin))
    assert len(list(CHECKPOINTS.glob('page-*.json'))) == 12
    return elements


def main():
    elements = load()
    predictor = ReadingOrderPredictor()
    ordered = predictor.predict_reading_order(elements)
    selected = {e.ref.cref: e for e in elements}
    predecessor, margin, continuation = (selected[r] for r in ('#/5/0', '#/6/14', '#/6/6'))
    if '--minimal' in sys.argv:
        ordered = [predecessor, margin, continuation]
    if '--candidate' in sys.argv:
        from pdf_processing.continuation import predict_merges
        merges = predict_merges(ordered)
    else:
        merges = predictor.predict_merges(ordered)
    targets = merges.get(predecessor.cid, [])
    verdict = continuation.cid in targets and margin.cid not in targets
    print(json.dumps({'association_correct': verdict, 'target_refs': [e.ref.cref for e in elements if e.cid in targets]}))
    assert verdict, 'False margin join or missing true continuation'


if __name__ == '__main__':
    main()
