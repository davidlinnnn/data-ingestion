"""One offline diagnostic execution. Writes only this new research directory."""
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import unittest

from PIL import Image, ImageStat
from docling_core.types.doc import DoclingDocument
from scoring import digest, score, score_math
from table_seam import replace_data
import test_gates as controls

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
INPUTS={}


def track(path):
    path=Path(path)
    INPUTS[str(path.relative_to(ROOT))]=sha256(path.read_bytes()).hexdigest()
    return path


def read(path):
    return json.loads(track(path).read_text())


def write(name,data):
    with (HERE/name).open("x") as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2)
        stream.write("\n")


def ac_diagnosis():
    ownerdir=ROOT/"docs/research/pdf-core-owner-context-2026-10-17"
    discoverydir=ROOT/"docs/research/pdf-core-page-discovery-2026-10-17"
    method=controls.load("offline_owner_context",ownerdir/"method.py")
    registration=read(ownerdir/"registration.json")
    for name,expected in registration["inputs"].items():
        assert sha256(track(ROOT/name).read_bytes()).hexdigest()==expected,name
    inv=read(method.INVENTORY)
    discovery=read(discoverydir/"registration.json")
    stored=read(ownerdir/"results.json")
    coverage=read(ownerdir/"coverage.json")
    adapter=controls.load("offline_A_scope",ROOT/"docs/research/pdf-core-stage1-followup-2026-10-17/A/method.py")
    page_inputs=[]
    for page in discovery["jobs"]:
        path=track(ROOT/page["image"])
        assert sha256(path.read_bytes()).hexdigest()==page["image_sha256"]
        with Image.open(path) as image:
            assert list(image.size)==page["pixels_wh"]
            variance=ImageStat.Stat(image.convert("L")).var[0]
            assert variance>0,"uniform/black model input"
        page_inputs.append(dict(id=page["id"],image=page["image"],sha256=page["image_sha256"],
                                pixels=page["pixels_wh"][0]*page["pixels_wh"][1],bytes=path.stat().st_size))
    replayed=[]
    fullpage_jobs=[]
    for source in inv["sources"]:
        raw=read(ROOT/source["document_path"])
        assert sha256((ROOT/source["document_path"]).read_bytes()).hexdigest()==source["document_sha256"]
        owners=method.catalog(source,discovery)
        pages={j["physical_page"]:j for j in discovery["jobs"] if j["id"].startswith(source["source"]+"-p")}
        for previous in stored["routes"]["native_plus_discovery"]:
            if previous["source"]!=source["source"]:continue
            group=dict(owners=previous["target_owner_refs"],reasons=previous["reasons"])
            actual=method.context(group,owners,pages,raw,adapter)
            for key,value in actual.items():assert previous[key]==value,(source["source"],key)
            actual.update(source=source["source"],job_id=previous["job_id"])
            replayed.append(actual)
        # New diagnostic hypothesis: complete page context, one original owner per write scope.
        # This inventory grants no cross-owner/parent write permission and creates no API jobs.
        for ref,owner in owners.items():
            if owner["responsibility"]=="table":continue
            ids=[f"{source['source']}-p{p}" for p in sorted({f["page"] for f in owner["fragments"]})]
            images=[p for p in page_inputs if p["id"] in ids]
            scope=False
            if owner["responsibility"]=="body":
                try:adapter.scope(raw,[ref]);scope=True
                except (ValueError,KeyError,TypeError,IndexError):pass
            fullpage_jobs.append(dict(source=source["source"],target=ref,
                responsibility=owner["responsibility"],context_page_ids=ids,
                input_pixels=sum(p["pixels"] for p in images),input_png_bytes=sum(p["bytes"] for p in images),
                existing_body_scope_available=scope,
                context_policy="whole source page read-only; only explicit original owner may be replaced"))
    unresolved=[j for j in replayed if j["binding"]=="unresolved"]
    assert len(replayed)==40 and len(unresolved)==2
    assert len(coverage["groups"])==44 and len(coverage["negatives"])==27 and len(coverage["legacy"])==41
    cdir=ROOT/"docs/research/pdf-core-eval-interfaces-2026-10-18/C"
    ccoverage=read(cdir/"source-coverage.json")
    cinventory=read(cdir/"producer-inventory.json")
    freshdir=ROOT/"docs/research/pdf-core-c-source-closure-2026-10-18"
    fresh=read(freshdir/"registration.json")
    fresh_pictures=0;fresh_pages=set()
    for entry in fresh["ranges"]:
        p=freshdir/"native"/entry["range_id"]/"document.json"
        document=DoclingDocument.model_validate_json(track(p).read_text())
        fresh_pictures+=len(document.pictures)
        for page in entry["pages"]:fresh_pages.add((entry["source_id"],page))
    assert len(fresh_pages)==55 and fresh_pictures==29
    sealpath=freshdir/"native/SRC11-cached-seal/document.json"
    seal=DoclingDocument.model_validate_json(track(sealpath).read_text())
    picture=seal.pictures[0]
    title=next(t for t in seal.texts if "RL Outer Loop Iteration t" in t.text)
    pb=picture.prov[0].bbox;tb=title.prov[0].bbox
    assert pb.coord_origin==tb.coord_origin
    outside=not (pb.l<=tb.l and pb.r>=tb.r and pb.b<=tb.b and pb.t>=tb.t)
    assert outside
    result=dict(hypothesis="full-page read-only context plus original-owner-only replacement",
        original_routes_replayed=len(replayed),unresolved_original_routes=unresolved,
        input_pages=page_inputs,fullpage_owner_inventory=fullpage_jobs,
        planned_owner_units=len(fullpage_jobs),not_registered_API_jobs=True,
        summed_fullpage_input_pixels=sum(j["input_pixels"] for j in fullpage_jobs),
        source_page_pixels=sum(p["pixels"] for p in page_inputs),
        source_groups=44,ordinary_negative_groups=27,legacy_units=41,
        fullpage_context_does_not_prove_target_discovery_or_quality=True,
        C=dict(source_groups=ccoverage["source_groups"],native_candidates=len(cinventory["pictures"]),
               fresh_pages=len(fresh_pages),fresh_pictures=fresh_pictures,
               title_present_in_body=True,title_outside_original_picture=outside,
               title_ref=title.self_ref,picture_ref=picture.self_ref),
        A_decision="NO_REGISTERABLE_METHOD",C_decision="NO_REGISTERABLE_METHOD",
        decision_reason=["Complete page input alone supplies no shared source/ordering contract for mixed picture+text formula occurrences.",
            "Splitting a multi-parent algorithm into original owners does not establish faithful code order or whole-unit delivery.",
            "C's old image-key/crop coordinates do not bind newly added outside-crop context; a new context/supplement contract has not passed the public seam controls."],
        limits="Negative result for this input-only/unchanged-output hypothesis; not proof that Docling or VLM cannot support the requirements.",
        remote_calls=0,model_quality_claim=False)
    write("AC-diagnosis.json",result)
    return result


def delivered_cells(delivery):
    if delivery is None:return []
    binding,panels=delivery
    result=[]
    for provider,ref,grid,rendered,_ in panels:
        for ri,row in enumerate(provider["rows"],1):
            for ci,column in enumerate(provider["columns"]):
                column_index=int(bool(provider["groups"]))+len(provider["dimension_names"])+ci
                cell=next(c for c in row["cells"] if c["column"]==column["key"])
                assert cell["text"]==grid[ri][column_index]==rendered[ri][column_index]
                group=next((g for g in provider["groups"] if g["id"]==row["group"]),None)
                result.append(dict(locator=f"{ref}:{ri}:{column_index}",text=grid[ri][column_index],
                    semantics=dict(dimensions=row["dimensions"],header=column["path"],group=group,
                                   panel_label=provider["panel_label"],title=provider["title"],conditions=binding["semantic_provider"]["conditions"])))
    return result


def b_replay():
    cases=[]
    for case,page in (("G1-T01","memory-r1-p8"),("G1-T02","skillopt-p8"),("G1-T04","paper09-p17"),("G1-T05","wikiskill-p13")):
        worksheet=read(controls.B/"evaluator"/(case+".json"))
        historical=read(ROOT/"docs/research/pdf-core-fixed-seven-source-2026-10-18/worksheets"/(case+".json"))
        job=next(j for j in read(controls.B/"candidate.json")["jobs"] if j["name"]==worksheet["job"])
        delivery=controls.old.delivery(page,job["target_key"])
        cells=delivered_cells(delivery);by={c["locator"]:c for c in cells}
        matches={}
        for point in historical["points"]:
            observation=point["observed"];pid=point["expected"]["id"]
            if delivery is None:
                matches[pid]=dict(passed=True,evidence="Actual target rejected and whole page withheld",absent=True,locator=None)
            else:
                r,c=observation["normalized_anchor"]
                locator=f"{observation['canonical_ref']}:{r}:{c}"
                matches[pid]=dict(passed=True,evidence="Historical explicit source/anchor matching; not new independent structure QA",
                    locator=locator,component=observation["numeric_component_index"],observed_sha256=digest(by[locator]))
        # Prior flags were mechanically populated. Keep the new source review pending.
        review=dict(matches=matches,decisions={k:None for k in worksheet["manual_structure_review"] if k!="notes"})
        result=score(worksheet,cells,review)
        write(case+"-replay.json",dict(result=result,review=review,observed_cells=cells,
            interpretation="Numeric/transport replay only; source structure decisions pending, so no promotion."))
        cases.append(dict(case=case,**result))
    prior_math=read(ROOT/"docs/research/pdf-core-fixed-seven-source-2026-10-18/worksheets/table-math.json")
    current=controls.old.delivery("wikiskill-p22","p22:#/tables/2")
    grid=current[1][0][2]
    observations=[grid[i][1:] for i in range(1,5)]
    decisions=[dict(passed=g["math_meaning_equivalent"],evidence=g["rationale"],
                    observed_sha256=digest(g["observed_typed"])) for g in prior_math["source_groups"]]
    math=score_math(observations,decisions)
    assert math["correct"]==3 and not math["passed"]
    fixture=controls.ContinuationControls();fixture.setUp()
    out,sidecar=replace_data(fixture.doc,fixture.relation,fixture.replacements)
    dest=HERE/"T03-MOCK";dest.mkdir()
    (dest/"document.json").write_text(out.model_dump_json())
    (dest/"document.md").write_text(out.export_to_markdown())
    write("T03-MOCK/relation.json",dict(**sidecar,MOCK=True,source_accuracy_claim=False))
    return dict(historical_numeric_replay=cases,math_historical_review_replay=math,
        T03=dict(public_seam="PASS_CONTROLS",fragments=[f["table_ref"] for f in fixture.relation["fragments"]],
                 source_accuracy="NOT_RUN",numeric_denominator=264,comparisons=7,missing_marks=3,
                 location_precision=sidecar["location_precision"]),
        evaluator="Independent score/review interface controls pass; live source matching still manual and snapshot-bound.",
        new_model_calls=0)


def main():
    registration=read(HERE/"registration.json")
    assert datetime.now(timezone.utc)<datetime.fromisoformat(registration["deadline"])
    if (HERE/"result.json").exists():raise SystemExit("Execution already exists; no overwrite/retry")
    # Freeze dependencies and saved outputs before any replay; assertions never refresh them.
    for base in (controls.B/"live",controls.B/"evaluator",ROOT/"docs/research/pdf-core-fixed-seven-source-2026-10-18/worksheets"):
        for path in base.rglob("*"):
            if path.is_file():track(path)
    for job in read(controls.B/"candidate.json")["jobs"]:track(Path(job["baseline"]))
    for path in HERE.glob("*.py"):track(path)
    seam=read(controls.B/"T03-native-seam.json");track(ROOT/seam["current_S0_inspection"]["document"])
    write("method-freeze.json",dict(inputs=dict(INPUTS),description="Frozen before tests and replay; no expected hash refresh"))
    stream=StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(controls))
    write("tests.json",dict(run=result.testsRun,failures=len(result.failures),errors=len(result.errors),output=stream.getvalue()))
    if not result.wasSuccessful():raise SystemExit("Offline controls failed; no model run")
    ac=ac_diagnosis();b=b_replay()
    assert datetime.now(timezone.utc)<datetime.fromisoformat(registration["deadline"])
    for name,expected in INPUTS.items():
        assert sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    write("input-verification.json",dict(files=INPUTS,unchanged=True))
    summary=dict(completed_at=datetime.now(timezone.utc).isoformat(),controls=result.testsRun,
        AC=dict(A=ac["A_decision"],C=ac["C_decision"],owner_units=ac["planned_owner_units"],
                summed_input_pixels=ac["summed_fullpage_input_pixels"],source_page_pixels=ac["source_page_pixels"]),
        B=b,paid_B="NOT_RUN: A/C still lack a registerable complete method; whole-goal checkpoint reached",
        new_model_calls=0,old_outputs_unchanged=True,full_profile_qualified=False)
    write("result.json",summary)
    write("artifact-seal.json",{str(p.relative_to(HERE)):sha256(p.read_bytes()).hexdigest()
        for p in HERE.rglob("*") if p.is_file() and p.name!="artifact-seal.json"})
    print(json.dumps(summary,ensure_ascii=False))


if __name__=="__main__":main()
