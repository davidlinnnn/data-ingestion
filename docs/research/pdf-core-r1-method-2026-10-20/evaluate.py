"""Evaluator-only MOCK transport and retained-source coverage, never a producer."""
from copy import deepcopy
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
import method as m
import bundle
from docling_core.types.doc import DoclingDocument
from PIL import Image, ImageChops
from markdown_it import MarkdownIt


def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")


def block(text,kind="paragraph",segments=None):
    return {"kind":kind,"segments":segments or [{"kind":{"formula":"math","code":"code"}.get(kind,"text"),"text":text}]}


def action(identifier,consume,evidence,blocks,anchor,side="before",pages=(4,)):
    return {"id":identifier,"consume":consume,"evidence_refs":evidence,"source_pages":list(pages),
        "placement":{"reference":anchor,"side":side},"blocks":blocks}


def response(bound,actions):
    used={r for a in actions for r in a["consume"]}
    return {"group_sha256":m.digest(bound),"keep":[r for r in bound["text_candidates"] if r not in used],"actions":actions}


def main():
    import producer
    producer.verify();producer.deadline()
    production=HERE/"production";inventory=read(production/"inventory.json")
    evaluations=HERE/"evaluation";evaluations.mkdir()
    input_paths=[HERE/"evaluate.py",HERE/"bundle.py",production/"inventory.json",
        ROOT/"docs/research/pdf-core-stage1-2026-10-17/A-evaluator/source-census.json",
        ROOT/"docs/research/pdf-core-eval-interfaces-2026-10-18/C/source-coverage.json"]
    write(evaluations/"registration.json",{"role":"evaluator_only",
        "inputs":{str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in input_paths},
        "model_calls":0,"responses_are_MOCK_not_model_outputs":True})
    A=[g for g in inventory["groups"] if g["component"]=="A"]
    C=[g for g in inventory["groups"] if g["component"]=="C"]
    # Fixed source census is read only after producer inventory and methods froze.
    census=read(ROOT/"docs/research/pdf-core-stage1-2026-10-17/A-evaluator/source-census.json")
    freeze=read(ROOT/"docs/research/pdf-core-stage1-2026-10-17/A-evaluator/source-census.freeze.json")
    assert sha256((ROOT/"docs/research/pdf-core-stage1-2026-10-17/A-evaluator/source-census.json").read_bytes()).hexdigest()==freeze["sha256"]
    coverage=[]
    for row in census["targets"]+census["ordinary_negatives"]:
        candidates=[g for g in A if g["source_name"]==row["source"] and row["physical_page"] in g["binding"]["pages"]]
        assert len(candidates)==1
        g=candidates[0];view=next(v for v in g["binding"]["views"] if v["page_no"]==row["physical_page"])
        original=ROOT/f"docs/research/pdf-core-stage1-2026-10-17/A-evaluator/{row['source']}-p{row['physical_page']}.png"
        with Image.open(original) as old,Image.open(production/view["asset"]) as new:
            assert old.size==new.size and ImageChops.difference(old.convert("RGB"),new.convert("RGB")).getbbox() is None
        coverage.append({"source_group":row["id"],"group_id":g["id"],"complete_source_page_pixels_equal":True,
            "interpretation":"input coverage only; not discovery recall or semantic quality"})
    identity=[]
    for g in A:
        baseline=read(ROOT/g["baseline"])
        result=m.apply(baseline,g["binding"],response(g["binding"],[]))
        expected=DoclingDocument.model_validate(baseline).model_dump(mode="json",by_alias=True)
        assert result["document"]==expected
        assert result["markdown"]==m.old.serialize(DoclingDocument.model_validate(baseline)).text
        identity.append({"group":g["id"],"unchanged_native_MOCK_transport":True})
    legacy=read(ROOT/"docs/research/pdf-core-g2-official-method-2026-10-15/review/contract.json")["units"]
    assert len(legacy)==41
    for unit in legacy:
        assert any(g["source_name"]==unit["source"] and set(unit["physical_pages_1based"])<=set(g["binding"]["pages"]) for g in A)
    old_C=read(ROOT/"docs/research/pdf-core-eval-interfaces-2026-10-18/C/source-coverage.json")
    keys={x["image_key"] for g in C for x in g["binding"]["images"]}
    assert len(keys)==29 and all(row["image_key"] in keys for row in old_C["groups"])
    write(evaluations/"coverage.json",{"A_source_groups":44,"ordinary_negatives":27,"legacy_units":41,
        "source_pixel_coverage":coverage,"keep_MOCK":identity,"C_source_groups":19,"C_native_images":29,
        "C_original_crop_partial_and_caption_failures_retained":{
            "partial":old_C["material_input_partial_groups"],"caption":old_C["material_caption_failure_groups"]},
        "new_context_does_not_repair_original_caption_or_prove_image_quality":True,"model_calls":0})
    seal=next(g for g in A if g["source_name"]=="seal")
    raw=read(ROOT/seal["baseline"]);scope=seal["binding"]
    C_scope=next(g["binding"] for g in C if g["source_name"]=="SRC11-cached-seal")
    # This case's refs/transcription are evaluator fixtures, never producer routing.
    first=raw["texts"][82];fragments=[first["text"][p["charspan"][0]:p["charspan"][1]] for p in first["prov"]]
    refs=[f"#/texts/{i}" for i in range(82,93)]
    native_code="\n".join(raw["texts"][i]["text"] for i in range(83,92))
    code_blocks=[block(fragments[0]+" "+raw["texts"][92]["text"]),block(fragments[1],"heading"),block(native_code,"code")]
    code_response=response(scope,[action("cross-parent-algorithm",refs,refs,code_blocks,"#/texts/82")])
    code_result=m.apply(raw,scope,code_response)
    assert native_code in code_result["markdown"] and code_result["markdown"].count(fragments[1])==1
    # Source-viewed notation, supplied as an ideal-response fixture, not an inference.
    formulas=[r"\theta_t",r"SE_1",r"\mathcal{L}(SE_1,\theta_t)",r"\theta'_t",r"\theta'_t",
        r"SE_2",r"\mathcal{L}(SE_2,\theta_t)",r"\theta'_t",r"\theta'_t",
        r"SE_3",r"\mathcal{L}(SE_3,\theta_t)",r"\theta'_t",r"\theta'_t",r"\theta_t",r"SE",r"\theta_{t+1}"]
    title=block("","heading",[{"kind":"text","text":"RL Outer Loop Iteration "},{"kind":"math","text":"t"}])
    figure_response=response(scope,[action("title",["#/texts/0"],["#/texts/0"],[title],"#/texts/0",pages=(2,)),
        action("figure-math",[],["#/pictures/0","#/texts/0"],[block(f,"formula") for f in formulas],
               "#/pictures/0",side="after",pages=(2,))])
    figure_result=m.apply(raw,scope,figure_response)
    assert len(figure_result["binding"]["outputs"])==17 and "$t$" in figure_result["markdown"]
    for f, count in Counter(formulas).items():assert figure_result["markdown"].count("$$"+f+"$$")==count
    key=C_scope["images"][0]["image_key"]
    C_mock={key:{"context_key":C_scope["context_key"],
        "image_ocr":{"scope":"crop","status":"ok","text":"MOCK: source graphic transcription transport"},
        "context_ocr":{"scope":"page_context","status":"ok","text":"RL Outer Loop Iteration t"},
        "description":{"image_kind":"flow diagram","description":"MOCK_DESCRIPTION_NOT_SOURCE_BODY", "visible_text":[],
            "components":[],"relations":[],"ordered_steps":[],"uncertainties":["MOCK transport; not model quality"]},
        "chart":{"chart_type":"not_chart","unit":None,"data":[],"uncertainties":[]}}}
    before=HERE/"bundles-before-move";before.mkdir()
    for name,result in (("actual-cross-parent",code_result),("actual-picture-title",figure_result)):
        markdown=bundle.save(before/name,production,ROOT/seal["baseline"],result,C_scope,C_mock)
        assert "MOCK_DESCRIPTION_NOT_SOURCE_BODY" not in markdown
        (before/name/"render-check.html").write_text(MarkdownIt("commonmark",{"html":True}).render(markdown))
        # The read-only view is not a bundle dependency; freeze it before relocation too.
        integrity=bundle.read(before/name/"integrity.json")
        integrity["render-check.html"]=bundle.sha(before/name/"render-check.html")
        bundle.write(before/name/"integrity.json",integrity)
    moved=HERE/"relocated-bundles";shutil.move(str(before),str(moved))
    results={name:bundle.verify(moved/name,m.digest(raw)) for name in ("actual-cross-parent","actual-picture-title")}
    negatives=[]
    try:bundle.verify(moved/"actual-picture-title","foreign")
    except ValueError:negatives.append("foreign_revision_rejected")
    image=moved/"actual-picture-title"/C_scope["images"][0]["asset"]
    image.rename(image.with_suffix(".held"))
    try:bundle.verify(moved/"actual-picture-title",m.digest(raw))
    except FileNotFoundError:negatives.append("missing_asset_rejected")
    finally:image.with_suffix(".held").rename(image)
    assert len(negatives)==2
    results["actual-picture-title"]=bundle.verify(moved/"actual-picture-title",m.digest(raw))
    producer.verify();producer.deadline()
    write(evaluations/"results.json",{"actual_source_MOCK_transports":results,"negative_controls":negatives,
        "figure_math_occurrences_including_title":17,"code_sources_across_parents":len(refs),
        "legacy_cross_page_source_units_accounted":41,"new_model_calls":0,
        "full_method_model_quality_verified":False,
        "source_caption_baseline_failure_not_repaired_by_context_alone":True})
    print(json.dumps({"A_pixel_coverage":44,"ordinary_negative_inputs":27,"legacy":41,"C_images":29,
        "C_source_groups":19,"actual_counterexample_MOCK_bundles":2,"relocated_reload":"passed","new_model_calls":0}))


if __name__=="__main__":
    def guard(event,args):
        if event in {"socket.connect","socket.getaddrinfo"}:raise RuntimeError("network forbidden")
        if event=="open" and isinstance(args[0],str) and ("holdout" in args[0] or args[0].endswith((".safetensors",".onnx",".pdparams"))):
            raise RuntimeError("model/holdout reads forbidden")
    sys.addaudithook(guard)
    main()
