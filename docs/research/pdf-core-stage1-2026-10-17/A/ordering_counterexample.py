"""A whole-owner serializer cannot interleave another native owner's content."""
import json
from pathlib import Path
from docling_core.types.doc import DoclingDocument,DocItemLabel,Size
import producer as p
from controls import prov,block,content,bundle


def main():
    doc=DoclingDocument(name='synthetic-interleaved-fragments')
    doc.add_page(page_no=1,size=Size(width=200,height=200))
    owner=doc.add_text(label=DocItemLabel.TEXT,text='bodytitle',prov=prov(y=10,span=(0,4)))
    owner.prov.append(prov(y=70,span=(4,9)))
    middle=doc.add_text(label=DocItemLabel.TEXT,text='middle',prov=prov(y=40,span=(0,6)))
    raw=doc.model_dump(mode='json',by_alias=True)
    scope,inputs,response=bundle(raw,[owner.self_ref],[content(block(value='BODY'),block('heading','TITLE'))])
    result=p.apply(raw,scope,inputs,response)
    md=result['working']
    assert md.index('BODY')<md.index('TITLE')<md.index('middle')
    expected='BODY < middle < TITLE'
    row=next(r for r in p.plan(raw) if r['target_ref']==owner.self_ref)
    assert row['status']=='unsupported' and row['reason']=='same_page_multiple_fragments_order_unresolved'
    evidence={'status':'unresolved_ordering_gate','control':'synthetic distinct owners interleaved on same page',
              'desired_source_order':expected,'actual_markdown':md,'planner_refuses':row['reason'],
              'impact':'Legal multi-block payload and public serialization do not establish correct interleaved reading order.',
              'minimum_next_decision':'A general multi-owner/fragment ownership and ordering method is required; no oracle or document-specific merge.',
              'model_calls':0,'not_a_claim_of_sdk_impossibility':True}
    (Path(__file__).parent/'ordering-counterexample.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(evidence))


if __name__=='__main__':main()
