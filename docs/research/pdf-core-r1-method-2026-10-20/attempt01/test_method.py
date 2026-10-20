"""Protocol controls, not a model oracle or a source-specific router."""
from copy import deepcopy
import json
import unittest

from docling_core.types.doc import DoclingDocument, DocItemLabel, ProvenanceItem, BoundingBox, Size
from markdown_it import MarkdownIt
import method as m


def document():
    doc = DoclingDocument(name="control")
    for page in (1, 2):
        doc.add_page(page_no=page, size=Size(width=300, height=400))
    return doc


def prov(page=1):
    return ProvenanceItem(page_no=page, bbox=BoundingBox(l=10,t=20,r=200,b=50,coord_origin="TOPLEFT"),charspan=(0,0))


def raw(doc):
    return doc.model_dump(mode="json", by_alias=True)


def bound(doc, images=(), pages=(1,)):
    return m.bind(raw(doc), list(pages), [{"page_no":p,"sha256":str(p)*64,"pixels":[600,800]} for p in pages], images)


def block(text, kind="paragraph", segments=None):
    return {"kind":kind,"segments":segments or [{"kind":{"formula":"math","code":"code"}.get(kind,"text"),"text":text}]}


def action(refs, anchor, blocks, evidence=None, side="before"):
    return {"id":"output", "consume":refs,"evidence_refs":evidence or refs,"source_pages":[1],
            "placement":{"reference":anchor,"side":side},"blocks":blocks}


def response(scope, actions):
    used={r for a in actions for r in a["consume"]}
    return {"group_sha256":m.digest(scope),"keep":[r for r in scope["text_candidates"] if r not in used],"actions":actions}


def picture_record(doc, picture):
    revision=m.digest(raw(doc)); crop="a"*64
    return {"owner_ref":picture.self_ref,"document_revision":revision,"crop_sha256":crop,
            "image_key":m.digest([revision,picture.self_ref,crop])}


def picture_payload(scope):
    return {"context_key":scope["context_key"],
        "image_ocr":{"scope":"crop","text":"in-image text","status":"ok"},
        "context_ocr":{"scope":"page_context","text":"outside-crop context","status":"ok"},
        "description":{"image_kind":"diagram","description":"DERIVED_DESCRIPTION_ONLY","visible_text":[],
            "components":[],"relations":[],"ordered_steps":[],"uncertainties":[]},
        "chart":{"chart_type":"not_chart","unit":None,"data":[],"uncertainties":[]}}


class SourceGroupControls(unittest.TestCase):
    def reload(self, result):
        doc=DoclingDocument.model_validate_json(json.dumps(result["document"]))
        self.assertEqual(m.old.serialize(doc).text,result["markdown"])
        self.assertTrue(doc.validate_tree(doc.body,raise_on_error=True))
        self.assertFalse(result["source_quality_verified"])

    def test_cross_parent_code_and_non_target_order(self):
        doc=document()
        first=doc.add_text(label=DocItemLabel.TEXT,text="first",prov=prov())
        middle=doc.add_text(label=DocItemLabel.TEXT,text="KEEP BETWEEN",prov=prov())
        group=doc.add_group()
        last=doc.add_text(label=DocItemLabel.TEXT,text="last",parent=group,prov=prov())
        tail=doc.add_text(label=DocItemLabel.TEXT,text="KEEP TAIL",prov=prov())
        scope=bound(doc); code='if x_i < y_j:\n    return "$5 & <tag>"'
        value=action([first.self_ref,last.self_ref],first.self_ref,[block(code,"code")])
        result=m.apply(raw(doc),scope,response(scope,[value]))
        self.assertIn(code,result["markdown"])
        self.assertEqual(result["markdown"].count("KEEP BETWEEN"),1)
        self.assertLess(result["markdown"].index("KEEP BETWEEN"),result["markdown"].index("KEEP TAIL"))
        self.assertIn("&lt;tag&gt;",MarkdownIt().render(result["markdown"]))
        self.reload(result)

    def test_mixed_picture_title_can_add_many_formula_occurrences(self):
        doc=document()
        title=doc.add_heading(text="Original title",level=2,prov=prov())
        picture=doc.add_picture(prov=prov())
        caption=doc.add_text(label=DocItemLabel.CAPTION,text="SOURCE CAPTION",parent=picture,prov=prov())
        picture.captions=[caption.get_ref()]
        context=doc.add_text(label=DocItemLabel.TEXT,text="READ ONLY CONTEXT",prov=prov())
        scope=bound(doc)
        replace=action([title.self_ref],title.self_ref,[block("RECONSTRUCTED TITLE","heading")])
        formulas=action([],picture.self_ref,[block(f"x_{{{i}}}^2","formula") for i in range(17)],
                        evidence=[picture.self_ref,title.self_ref],side="after")
        formulas["id"]="pixel-formulas"
        result=m.apply(raw(doc),scope,response(scope,[replace,formulas]))
        self.assertEqual(len(result["binding"]["outputs"]),18)
        self.assertEqual(result["markdown"].count("SOURCE CAPTION"),1)
        self.assertEqual(result["markdown"].count("READ ONLY CONTEXT"),1)
        self.assertLess(result["markdown"].index("x_{0}"),result["markdown"].index("x_{16}"))
        for row in result["binding"]["outputs"]:
            self.assertEqual(row["precision"],"page-envelope")
        self.reload(result)

    def test_inline_math_code_and_source_caption_edge(self):
        doc=document(); picture=doc.add_picture(prov=prov())
        caption=doc.add_text(label=DocItemLabel.CAPTION,text="native caption",parent=picture,prov=prov())
        picture.captions=[caption.get_ref()]; scope=bound(doc)
        segments=[{"kind":"text","text":"Let "},{"kind":"math","text":"x_i^2"},
                  {"kind":"text","text":"; call "},{"kind":"code","text":"items[i]"}]
        value=action([caption.self_ref],picture.self_ref,[block("",segments=segments)])
        result=m.apply(raw(doc),scope,response(scope,[value]))
        self.assertIn("$x_i^2$",result["markdown"])
        self.assertIn("`items[i]`",result["markdown"])
        self.assertEqual(result["markdown"].count("Let "),1)
        self.reload(result)

    def test_keep_all_is_an_identity_transport_not_quality_acceptance(self):
        doc=document();doc.add_text(label=DocItemLabel.TEXT,text="ordinary prose",prov=prov())
        scope=bound(doc); result=m.apply(raw(doc),scope,response(scope,[]))
        self.assertEqual(result["document"],raw(doc)); self.reload(result)

    def test_native_multi_page_owner_not_split_by_page(self):
        doc=document(); item=doc.add_text(label=DocItemLabel.TEXT,text="joined",prov=prov())
        item.prov.append(prov(2))
        self.assertEqual(m.groups(raw(doc),"A"),[[1,2]])
        with self.assertRaisesRegex(ValueError,"partial owner"):
            bound(doc)
        scope=bound(doc,pages=(1,2));value=action([item.self_ref],item.self_ref,[block("joined")]);value["source_pages"]=[1,2]
        result=m.apply(raw(doc),scope,response(scope,[value]));self.reload(result)
        self.assertEqual(result["markdown"].count("joined"),1)

    def test_scope_does_not_route_by_document_name_or_text_signal(self):
        doc=document();doc.add_text(label=DocItemLabel.TEXT,text="no symbols",prov=prov())
        original=m.groups(raw(doc),"A");doc.name="unknown-document";doc.texts[0].text="x_i = 17"
        self.assertEqual(m.groups(raw(doc),"A"),original)
        self.assertEqual(len(bound(doc)["text_candidates"]),1)

    def test_missing_duplicate_foreign_stale_and_unreachable_reject(self):
        doc=document();a=doc.add_text(label=DocItemLabel.TEXT,text="A",prov=prov())
        b=doc.add_text(label=DocItemLabel.TEXT,text="B",prov=prov())
        scope=bound(doc); valid=response(scope,[action([a.self_ref],a.self_ref,[block("R")])])
        variants=[]
        bad=deepcopy(valid);bad["keep"]=[];variants.append(bad)
        bad=deepcopy(valid);bad["keep"].append(a.self_ref);variants.append(bad)
        bad=deepcopy(valid);bad["actions"][0]["consume"].append(a.self_ref);variants.append(bad)
        bad=deepcopy(valid);bad["group_sha256"]="foreign";variants.append(bad)
        bad=deepcopy(valid);bad["actions"][0]["source_pages"]=[2];variants.append(bad)
        bad=deepcopy(valid);bad["actions"][0]["placement"]["reference"]="#/texts/999";variants.append(bad)
        bad=deepcopy(valid);bad["actions"][0]["blocks"]=[];variants.append(bad)
        bad=deepcopy(valid);bad["actions"][0]["blocks"][0]["segments"][0]["text"]="";variants.append(bad)
        for i,value in enumerate(variants):
            with self.subTest(i=i),self.assertRaises((ValueError,KeyError)):
                m.apply(raw(doc),scope,value)
        changed=raw(doc);changed["texts"][1]["text"]="stale"
        with self.assertRaisesRegex(ValueError,"stale"):
            m.apply(changed,scope,valid)

    def test_context_supplement_keeps_crop_identity_and_never_enters_source_MD(self):
        doc=document();p=doc.add_picture(prov=prov());record=picture_record(doc,p)
        scope=bound(doc,[record]); original_md=m.old.serialize(doc).text
        payload=picture_payload(scope); result=m.supplement(raw(doc),scope,{record["image_key"]:payload})
        self.assertEqual(result["images"][0]["image"]["image_key"],record["image_key"])
        self.assertEqual(result["images"][0]["observations"]["context_ocr"]["scope"],"page_context")
        self.assertNotIn("DERIVED_DESCRIPTION_ONLY",original_md)
        self.assertEqual(m.old.serialize(doc).text,original_md)

    def test_stale_context_wrong_OCR_view_and_exempted_work_reject(self):
        doc=document();p=doc.add_picture(prov=prov());record=picture_record(doc,p);scope=bound(doc,[record])
        valid=picture_payload(scope)
        for kind in ("stale","view","missing","empty"):
            value=deepcopy(valid)
            if kind=="stale":value["context_key"]="old"
            elif kind=="view":value["context_ocr"]["scope"]="crop"
            elif kind=="missing":del value["chart"]
            else:value["image_ocr"]["text"]=""
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                m.supplement(raw(doc),scope,{record["image_key"]:value})


if __name__ == "__main__":
    unittest.main()
