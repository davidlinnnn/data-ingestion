"""Synthetic public-interface checks; saved-source scores are not inferred."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from docling_core.types.doc import (BoundingBox, DocItemLabel, DoclingDocument,
                                    ProvenanceItem, Size)
import producer as p

HERE = Path(__file__).resolve().parent


def prov(page=1, y=10, span=(0, 0)):
    return ProvenanceItem(page_no=page, bbox=BoundingBox(l=10,t=y,r=190,b=y+10,coord_origin="TOPLEFT"), charspan=span)


def block(kind="paragraph", value="synthetic content", segment="text"):
    return {"kind":kind,"bbox":[0,0,100,100],"code_language":None,
            "segments":[{"kind":segment,"text":value}]}


def content(*blocks):
    return {"blocks":list(blocks),"uncertainties":[]}


def bundle(raw, targets, contents, contexts=()):
    scope=p.bind_scope(raw,targets,contexts)
    inputs=p.legacy.bind_input(scope,image_sha256="1"*64,image_pixels_wh=[100,100],
                               request_sha256="2"*64,manifest_row_sha256="3"*64)
    data={"targets":[{"target_ref":r,"content":c} for r,c in zip(targets,contents,strict=True)]}
    response=p.legacy.bind_response(inputs,data,response_sha256="4"*64)
    return scope,inputs,response


def main():
    started=time.monotonic()
    doc=DoclingDocument(name="synthetic-control")
    for page in (1,2):doc.add_page(page_no=page,size=Size(width=200,height=200))
    first=doc.add_text(label=DocItemLabel.TEXT,text="unchanged neighbor",prov=prov(span=(0,18)))
    formula=doc.add_formula(text="",prov=prov(y=30))
    paragraph=doc.add_text(label=DocItemLabel.TEXT,text="native text",prov=prov(y=50,span=(0,11)))
    code=doc.add_code(text="native_code()",prov=prov(y=70,span=(0,13)))
    cross=doc.add_text(label=DocItemLabel.TEXT,text="first second",prov=prov(y=90,span=(0,5)))
    cross.prov.append(prov(page=2,y=10,span=(6,12)))
    picture=doc.add_picture(prov=prov(y=110))
    child=doc.add_formula(text="",parent=picture,prov=prov(y=110))
    raw=doc.model_dump(mode="json",by_alias=True)
    frozen=p.digest(raw)
    positive={}
    cases=[("empty_native_display_formula",formula.self_ref,content(block("formula","x^{2}+1","math"))),
           ("picture_child_complete_envelope",picture.self_ref,content(block("formula",r"\frac{1}{x}","math"))),
           ("prose_inline",paragraph.self_ref,content({**block(),"segments":[{"kind":"text","text":"Let "},{"kind":"math","text":"x^2"}]})),
           ("code_instruction_literal_indent",code.self_ref,content(block("code","if x <= 1:\n    return '007'","code"))),
           ("crosspage_paragraph",cross.self_ref,content(block(value="first second"))),
           ("mixed_prose_heading_legal_payload",paragraph.self_ref,content(block(value="synthetic prose"),block("heading","synthetic title"))),
           ("ordinary_negative",paragraph.self_ref,content(block(value="native text")))]
    for name,reference,answer in cases:
        scope,inputs,response=bundle(raw,[reference],[answer],[first.self_ref])
        result=p.apply(raw,scope,inputs,response)
        assert "unchanged neighbor" in result["working"]
        assert p.digest(raw)==frozen
        restored=DoclingDocument.model_validate(json.loads(json.dumps(raw))).model_dump(mode="json",by_alias=True)
        assert p.digest(restored)==frozen
        positive[name]={"pass":True,"scope":scope,"result":result,
                        "limit":"synthetic structure/serialization only; not source semantic quality"}
    base=bundle(raw,[paragraph.self_ref],[content(block())],[first.self_ref])
    scope,inputs,response=base
    def apply(r=raw,s=scope,i=inputs,a=response):return p.apply(r,s,i,a)
    negatives={}
    def reject(name,action):
        try:action()
        except (ValueError,KeyError,TypeError,IndexError) as error:negatives[name]=str(error)
        else:raise AssertionError(name+" accepted")
    reject("foreign_ref",lambda:p.bind_scope(raw,["#/texts/999999"]))
    reject("duplicate_target",lambda:p.bind_scope(raw,[paragraph.self_ref]*2))
    reject("context_consumed",lambda:p.bind_scope(raw,[paragraph.self_ref],[paragraph.self_ref]))
    reject("nested_overlap",lambda:p.bind_scope(raw,[picture.self_ref,child.self_ref]))
    changed=deepcopy(raw);changed["texts"][0]["text"]+="changed"
    reject("stale_outside_document",lambda:apply(r=changed))
    changed=deepcopy(scope);changed["entries"][0]["sha256"]="0"*64
    reject("item_hash_changed",lambda:apply(s=changed))
    changed=deepcopy(scope);changed["entries"][0]["fragments"]=[]
    reject("missing_fragment",lambda:apply(s=changed))
    changed=deepcopy(raw);changed["body"]["children"].append({"$ref":paragraph.self_ref})
    reject("duplicate_owner",lambda:p.bind_scope(changed,[paragraph.self_ref]))
    changed=deepcopy(raw);changed["texts"][2]["prov"][0]["bbox"]["r"]=1000
    reject("invalid_geometry",lambda:p.bind_scope(changed,[paragraph.self_ref]))
    changed=deepcopy(inputs);changed["image_sha256"]="9"*64
    reject("changed_image",lambda:apply(i=changed))
    changed=deepcopy(inputs);changed["request_sha256"]="9"*64
    reject("changed_request",lambda:apply(i=changed))
    changed=deepcopy(inputs);changed["manifest_row_sha256"]="9"*64
    reject("changed_manifest",lambda:apply(i=changed))
    changed=deepcopy(inputs);changed["image_pixels_wh"]=[101,100]
    reject("changed_dimensions",lambda:apply(i=changed))
    changed=deepcopy(response);changed["input_fingerprint"]="9"*64
    reject("foreign_response",lambda:apply(a=changed))
    changed=deepcopy(response);changed["data"]["targets"]=[]
    reject("tampered_response",lambda:apply(a=changed))
    def invalid_data(data):return apply(a=p.legacy.bind_response(inputs,data,response_sha256="4"*64))
    reject("missing_target",lambda:invalid_data({"targets":[]}))
    reject("duplicate_response_target",lambda:invalid_data({"targets":response["data"]["targets"]*2}))
    changed=deepcopy(response["data"]);changed["targets"][0]["target_ref"]=first.self_ref
    reject("unknown_response_target",lambda:invalid_data(changed))
    reject("truncated_response",lambda:invalid_data(None))
    for name,answer in [("empty_blocks",content()),("empty_segment",content(block(value=""))),
                        ("null_segment",content(block(value=None))),
                        ("unknown_segment",content(block(value="unresolved",segment="unknown")))]:
        reject(name,lambda answer=answer:invalid_data({"targets":[{"target_ref":paragraph.self_ref,"content":answer}]}))
    changed=deepcopy(response["data"]);changed["extra"]=True
    reject("unknown_root_field",lambda:invalid_data(changed))
    changed=deepcopy(response["data"]);changed["targets"][0]["extra"]=True
    reject("unknown_target_field",lambda:invalid_data(changed))
    # Replay the exact historical 23 structural negatives, redirecting its sole save.
    old=p.load("stage1_legacy_negative_replay",p.REPO/"docs/research/pdf-core-g2-context-api-2026-10-15/integration/run.py")
    old.verify.save=lambda path,value:(HERE/"legacy-23-negative-controls.json").write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    legacy_count=old.selfcheck()
    assert legacy_count==23
    result={"positive_controls":positive,"negative_controls":negatives,"legacy_negative_controls":legacy_count,
            "role_policy":"Native label need not equal response block role; mixed legal blocks accepted. Duplicate blocks within one owner still need semantic review.",
            "ordering_limit":"Mixed-body/title payload acceptance does not prove interleaved same-page fragment order; producer rejects that topology.",
            "model_calls":0,"weights_loaded":0,"source_quality_assessed":False,
            "completed_at":datetime.now(timezone.utc).isoformat(),"elapsed_seconds":time.monotonic()-started}
    (HERE/"controls-results.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({"positive":len(positive),"negative":len(negatives),"legacy_negative":legacy_count,"model_calls":0}))


if __name__=="__main__":main()
