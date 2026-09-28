"""Replay reading-order rules over retained page elements, without model inference."""
import hashlib
import inspect
import importlib.metadata
import json
from pathlib import Path
import sys
from docling_core.types.doc import BoundingBox, RefItem, Size
from docling_ibm_models.reading_order.reading_order_rb import PageElement, ReadingOrderPredictor

ROOT=Path(__file__).resolve().parent
RAW=Path('/private/tmp/t09a-r2-20260914/checkpoints')
elements=[]
for path in sorted(RAW.glob('page-*.json')):
    page=json.loads(path.read_text())
    for entry in page['assembled']['elements']:
        v=entry['value'];box=BoundingBox.model_validate(v['cluster']['bbox']).to_bottom_left_origin(page['size']['height'])
        elements.append(PageElement(cid=len(elements),ref=RefItem.model_validate({'$ref':f"#/{page['page_no']}/{v['cluster']['id']}"}),
            text=v.get('text') or '',page_no=page['page_no'],page_size=Size.model_validate(page['size']),label=v['label'],
            l=box.l,r=box.r,t=box.t,b=box.b,coord_origin=box.coord_origin))
predictor=ReadingOrderPredictor()
ordered=predictor.predict_reading_order(elements)
merges=predictor.predict_merges(ordered)
captions=predictor.predict_to_captions(ordered)
by_id={e.cid:e for e in elements}
def summary(e):return {'page':e.page_no,'cluster_ref':e.ref.cref,'label':str(e.label),
    'text_sha256':hashlib.sha256(e.text.encode()).hexdigest()}
prose=next(e for e in elements if e.page_no==5 and 'second path' in e.text)
expected=next(e for e in elements if e.page_no==6 and e.text.startswith('to Bucharest with cost'))
actual=[by_id[i] for i in merges.get(prose.cid,[])]
report={'predictor_source_sha256':hashlib.sha256(Path(inspect.getfile(ReadingOrderPredictor)).read_bytes()).hexdigest(),
    'upstream_packages':{n:importlib.metadata.version(n) for n in ('docling','docling-core','docling-ibm-models')},
    'checkpoint_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.glob('page-*.json'))},
    'prose':summary(prose),'expected_continuation':summary(expected),'actual_merge_targets':[summary(e) for e in actual],
    'association_correct':expected.cid in merges.get(prose.cid,[]),
    'algorithm_related':[{**summary(e),'caption_targets':[summary(by_id[i]) for i in captions.get(e.cid,[])]}
        for e in elements if any(t in e.text for t in ('BREADTH-FIRST-SEARCH','UNIFORM-COST-SEARCH','DEPTH-LIMITED-SEARCH','ITERATIVE-DEEPENING-SEARCH','Figure 3.14','Figure 3.18')) or e.text=='\u0338']}
(ROOT/'evidence/source-localization.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'association_correct':report['association_correct'],'actual_target_refs':[e.ref.cref for e in actual]}))
if '--assert-quality' in sys.argv:assert report['association_correct'],'Retained layout inputs reproduce upstream prose/margin merge'
