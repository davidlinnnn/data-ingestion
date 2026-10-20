"""No-model gate: native traversal/writeback/export and observer transparency."""
import importlib.metadata as metadata
import json
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
from docling.document_converter import DocumentConverter
from docling_core.types.doc import DoclingDocument
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import ItemAndImageEnrichmentElement
from docling.models.inference_engines.vlm.base import VlmEngineOutput
from docling.models.stages.code_formula.code_formula_vlm_model import CodeFormulaVlmModel
import run

H=run.HERE
CODE='# MOCK_ONLY\nif x < n:\n    emit("<tag>")'
FORMULA=r'g(x)=\frac{1}{x+1}'

def fake(inputs):
    return [VlmEngineOutput(text=CODE if x.prompt=='<code>' else FORMULA,stop_reason='mock') for x in inputs]

def model():
    o=run.options().code_formula_options
    o.extract_code=True;o.extract_formulas=True
    m=CodeFormulaVlmModel(enabled=False,enable_remote_services=False,artifacts_path=None,
        options=o,accelerator_options=AcceleratorOptions(device='cpu',num_threads=4))
    m.enabled=True;m.engine=SimpleNamespace(predict_batch=fake,cleanup=lambda:None)
    return m

inventory=[]
for job in ['controls','wikiskill','seal','dgm']:
    d=DoclingDocument.load_from_json(run.PREVIOUS/'S0'/job/'document.json')
    m=model()
    items=[x for x,_ in d.iterate_items() if m.is_processable(d,x)]
    inventory.append(dict(job=job,items=[dict(ref=x.self_ref,label=x.label,parent=x.parent.model_dump(),prov=[p.model_dump(mode='json') for p in x.prov]) for x in items]))
assert [len(x['items']) for x in inventory]==[2,1,4,3]
checks=[]
for job,indexes in [('controls',[12,14]),('seal',[81])]:
    d=DoclingDocument.load_from_json(run.PREVIOUS/'S0'/job/'document.json');d.name='mock-'+job
    other=d.model_copy(deep=True)
    image=Image.new('RGB',(32,32),'white')
    m=model();n=model()
    a=[ItemAndImageEnrichmentElement(item=d.texts[i],image=image) for i in indexes]
    b=[ItemAndImageEnrichmentElement(item=other.texts[i],image=image) for i in indexes]
    before=[x.item.model_dump(mode='json') for x in b]
    expected=list(CodeFormulaVlmModel.__call__(m,d,a))
    observer=run.Observer(H/'mock',CodeFormulaVlmModel.__call__,real=False)
    actual=list(observer.invoke(n,other,b))
    assert [x.model_dump(mode='json') for x in expected]==[x.model_dump(mode='json') for x in actual]
    assert d.model_dump(mode='json')==other.model_dump(mode='json')
    assert all(x is el.item for x,el in zip(actual,b))
    assert all(x.orig==old['orig'] and [v.model_dump(mode='json') for v in x.prov]==old['prov'] for x,old in zip(actual,before))
    md=other.export_to_markdown()
    assert (CODE if job=='controls' else FORMULA) in md,md
    (H/f'mock-{job}.md').write_text(md)
    checks.append(dict(job=job,item_refs=[x.self_ref for x in actual],literal_indentation_or_math_in_stock_export=True,observer_transparent=True,orig_and_provenance_unchanged=True))
run.save(H/'eligibility.json',inventory)
run.save(H/'preflight.json',dict(status='pass',models_loaded=0,real_inference=0,checks=checks,known_unreachable=['controls picture-child formula3','ordinary paragraph inline formula'],mock_is_not_quality_evidence=True))
run.save(H/'runtime.json',sorted([dict(name=x.metadata['Name'],version=x.version) for x in metadata.distributions()],key=lambda x:x['name'].lower()))
run.save(H/'registered-options.json',run.options().model_dump(mode='json',serialize_as_any=True))
print('no-model gate passed: native eligibility10, root/group code, root formula, literal/indentation/math stock export and observer transparency')
