"""This run's explicit source-correspondence record, then the independent scorer.

Row-order and column correspondences below were reviewed against all seven
frozen source crops. They are evaluator-only evidence, not a reusable matcher
for an unseen model, and never enter producer requests. Scoring lives separately.
"""
from collections import Counter, defaultdict
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sys

from docling_core.types.doc import DoclingDocument, RefItem

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
GATES=ROOT/"docs/research/pdf-core-offline-gates-2026-10-18"
sys.path.insert(0,str(GATES))
import run as offline
from scoring import digest,numbers,score,score_math
from test_gates import old
old.LIVE=HERE/"live"
B=ROOT/"docs/research/pdf-core-eval-interfaces-2026-10-18/B"


def read(path):return json.loads(Path(path).read_text())


def write(name,value):
    with (HERE/name).open("x") as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.write("\n")


def canonical(text):return " ".join(str(text).casefold().split())


def textkey(t):
    return (t.text,t.orig,str(t.label),digest([p.model_dump(mode="json") for p in t.prov]))


def source_text_state(before,after):
    original=Counter(map(textkey,before.texts));actual=Counter(map(textkey,after.texts))
    preserved=all(actual[k]>=n for k,n in original.items())
    keys=set(original)
    sequence=lambda doc:[textkey(t) for t,_ in doc.iterate_items() if hasattr(t,"text") and textkey(t) in keys]
    return preserved,sequence(before)==sequence(after)


def preservation(page):
    before=DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
    after=DoclingDocument.model_validate_json((HERE/"live"/page["name"]/"document.json").read_text())
    bindings=read(HERE/"live"/page["name"]/"bindings.json")
    source_texts_ok,order_ok=source_text_state(before,after)
    corrupted=after.model_copy(deep=True)
    corrupted.texts[0].text="CONTROL: altered required original source text"
    assert not source_text_state(before,corrupted)[0],"source-content mutation must be detected"
    target_before={k.split(":",1)[1] for k in page["target_keys"]}
    target_after={p["table_ref"] for b in bindings for p in b["panels"]}
    def tablekey(t,doc):
        return digest(dict(data=t.data.model_dump(mode="json"),prov=[p.model_dump(mode="json") for p in t.prov],
            captions=[r.resolve(doc).text for r in t.captions]))
    other_ok=Counter(tablekey(t,before) for t in before.tables if t.self_ref not in target_before)==Counter(
        tablekey(t,after) for t in after.tables if t.self_ref not in target_after)
    captions_ok=True;provenance_ok=True
    for binding in bindings:
        source=RefItem(cref=binding["target_key"].split(":",1)[1]).resolve(before)
        original_captions=Counter(textkey(r.resolve(before)) for r in source.captions)
        actual_captions=Counter(textkey(RefItem(cref=r).resolve(after)) for r in binding["captions"])
        captions_ok &= all(actual_captions[k]>=n for k,n in original_captions.items())
        provenance_ok &= binding["original_provenance"]==[p.model_dump(mode="json") for p in source.prov]
    result=dict(page=page["name"],all_original_texts_preserved=source_texts_ok,
        original_text_reading_order_preserved=order_ok,non_target_table_data_preserved=other_ok,
        original_caption_links_and_text_preserved=bool(captions_ok),native_envelopes_preserved=bool(provenance_ok),
        added_text_items=len(after.texts)-len(before.texts),
        addition_note="Adapter adds panel titles and empty derived caption items; original source items are checked separately.")
    assert all(result[k] for k in ["all_original_texts_preserved","original_text_reading_order_preserved",
        "non_target_table_data_preserved","original_caption_links_and_text_preserved","native_envelopes_preserved"])
    return result


def source_row_check(case,context,panel,row):
    dims=row["dimensions"]
    group=next((g["label"] for g in panel["groups"] if g["id"]==row["group"]),None)
    if case=="G1-T01":return canonical(context["method"])==canonical(dims["Method"])
    if case=="G1-T02":return (context["panel"]==panel["panel_label"].strip("()")
        and canonical(context["condition_dimension"])==canonical(panel["title"])
        and canonical(context["setting"])==canonical(dims["Setting"]))
    if case=="G1-T04":return (canonical(context["model_family"])==canonical(dims["Model"])
        and canonical(context["model_variant"])==canonical(dims["variant"])
        and canonical(context["method"])==canonical(dims["Method"]))
    if case=="G1-T05":return canonical(context["category"])==canonical(dims["Category"]) and context["row_group"]==group
    if case=="skillopt-p8-table1":return all(canonical(context[k])==canonical(dims[v]) for k,v in [("component","Component"),("setting","Setting")])
    return canonical(context["method"])==canonical(dims["Method"]) and context["group"]==group


def evaluate(case,worksheet,job,preservation_result):
    d=old.delivery(job["page_name"],job["target_key"])
    cells=offline.delivered_cells(d);by={c["locator"]:c for c in cells}
    rows={}
    for p in worksheet["points"]:rows.setdefault(p["expected"]["row_id"],p["expected_row_context"])
    actual=[(provider,ref,ri,row) for provider,ref,grid,rendered,ordinal in d[1]
            for ri,row in enumerate(provider["rows"],1)]
    assert len(rows)==len(actual),"review correspondence must account for every source and delivered row"
    columns=list(dict.fromkeys(p["expected"]["column_key"] for p in worksheet["points"]))
    # Source-reviewed positional correspondences for this complete output only.
    positions=([0,0,1,1,2,3,4,5] if case=="G1-T05" else list(range(len(columns))))
    components=([0,1,0,1,0,0,0,0] if case=="G1-T05" else [0]*len(columns))
    rowmap={};source_records=[]
    for (row_id,context),(panel,ref,ri,row) in zip(rows.items(),actual,strict=True):
        passed=source_row_check(case,context,panel,row)
        note=("Source image and full row/panel/group meaning agree (case/spacing typography allowed)." if passed else
              "Source family Qwen2.5 is rendered as Qwen2-1.5b, including variant 3b; required model condition is wrong.")
        rowmap[row_id]=(panel,ref,ri,row,passed,note)
        source_records.append(dict(source_row_id=row_id,source_context=context,canonical_ref=ref,row=ri,
            observed_dimensions=row["dimensions"],source_binding_correct=passed,evidence=note))
    matches={};raw_correct=0;raw_values={};pair_records=defaultdict(list)
    for point in worksheet["points"]:
        e=point["expected"];panel,ref,ri,row,valid,note=rowmap[e["row_id"]]
        index=columns.index(e["column_key"]);ci=positions[index];component=components[index]
        col=panel["columns"][ci]
        offset=int(bool(panel["groups"]))+len(panel["dimension_names"])+ci
        locator=f"{ref}:{ri}:{offset}";cell=by[locator]
        matches[e["id"]]=dict(locator=locator,component=component,passed=valid,evidence=note,observed_sha256=digest(cell))
        values=numbers(cell["text"]);value=values[component] if len(values)>component else None
        raw_correct+=value==Decimal(e["decimal_value"])
        if value is not None:raw_values[e["id"]]=value
        if e.get("source_cell_id"):pair_records[e["source_cell_id"]].append((locator,component,cell["text"]))
    pairs_ok=all(len(v)==2 and v[0][0]==v[1][0] and [v[0][1],v[1][1]]==[0,1] for v in pair_records.values())
    if case=="G1-T05":assert len(pair_records)==20 and pairs_ok
    row_ok=all(v[4] for v in rowmap.values())
    decisions={}
    notes=dict(header_condition_binding="Reviewed all source column paths and panel conditions; Qwen family mismatch blocks T04.",
        row_dimension_binding="Compared every source row context to the delivered dimensions; explicit records attached.",
        group_membership="T05's two aggregation sections and collateral model groups reviewed; T04 model family mismatch blocks.",
        caption_ownership="Original refs/text preserved by independent baseline-to-output checks.",
        paired_cell_identity_and_role_order="T05 20 source physical pairs retain one cell with Proposed then Accepted; other cases not applicable.",
        non_target_preservation="Independent original text/order/table/caption/provenance checks passed.")
    for key in worksheet["manual_structure_review"]:
        if key=="notes":continue
        passed=(row_ok if key in {"header_condition_binding","row_dimension_binding","group_membership"} else
                pairs_ok if key=="paired_cell_identity_and_role_order" else True)
        decisions[key]=dict(passed=passed,evidence=notes[key])
    review=dict(matches=matches,decisions=decisions,source_rows=source_records,
        source_column_correspondences=[dict(source_key=k,observed_path=[h["text"] for h in actual[0][0]["columns"][positions[i]]["path"]],
            component=components[i],review="Source crop reviewed; path is table-local, panel conditions checked separately.") for i,k in enumerate(columns)],
        source_image_sha256=job["image_sha256"],source_review_kind="explicit candidate-specific source correspondence, not generic model matching")
    result=score(worksheet,cells,review)
    raw_comparisons=[]
    for comparison in worksheet["comparisons"]:
        e=comparison["expected"];l,r=raw_values.get(e["left"]),raw_values.get(e["right"])
        op=None if l is None or r is None else ">" if l>r else "<" if l<r else "="
        raw_comparisons.append(op==e["operator"])
    result.update(raw_position_value_correct=raw_correct,raw_position_comparisons_passed=sum(raw_comparisons),
                  paired_source_cells=len(pair_records),source_rows_wrong=sum(not r["source_binding_correct"] for r in source_records))
    write(case+"-evaluation.json",dict(result=result,review=review,cells=cells,preservation=preservation_result))
    return result


def collateral_worksheet(name,source):
    base=read(B/"evaluator/G1-T01.json")
    rows={};points=[]
    for i,record in enumerate(source["records"]):
        context={k:v for k,v in record["expected_context"].items() if k not in {"metric","metric_path"}}
        row_key=json.dumps(context,sort_keys=True);rows.setdefault(row_key,str(len(rows)+1))
        points.append(dict(expected_row_context=context,expected=dict(id=f"{name}:{i}",row_id=rows[row_key],
            column_key=record["expected_context"].get("metric",record["expected_context"].get("metric_path")),
            value_kind="number",raw_value=record["expected_raw"],decimal_value=record["expected_raw"])))
    base.update(points=points,comparisons=[]);base["acceptance_reference"]["numeric_error_rate_max"]=.05
    return base


def main():
    reg=read(HERE/"candidate.json")
    assert read(HERE/"model-identity-check.json")["all_received_identities_match"]
    preservation_results={p["name"]:preservation(p) for p in reg["pages"]}
    results={}
    for case in ["G1-T01","G1-T02","G1-T04","G1-T05"]:
        worksheet=read(B/"evaluator"/(case+".json"))
        job=next(j for j in reg["jobs"] if j["name"]==worksheet["job"])
        results[case]=evaluate(case,worksheet,job,preservation_results[job["page_name"]])
    collateral=read(B/"evaluator/collateral.json")
    for name in ["skillopt-p8-table1","paper09-p17-table1"]:
        job=next(j for j in reg["jobs"] if j["name"]==name)
        results[name]=evaluate(name,collateral_worksheet(name,collateral[name]),job,preservation_results[job["page_name"]])
    math=old.delivery("wikiskill-p22","p22:#/tables/2")
    grid=math[1][0][2];observations=[grid[i][1:] for i in range(1,5)]
    rationales=["Trace2Skill fraction denominator is c-1, with Ntrain, batch division and both additions retained.",
        "EvoSkill per-iteration 2*Ntrain/B retained; big-O drops constant 2 equivalently.",
        "SkillOpt Kopt*Ntrain/B and asymptotic Ntrain/B retained.",
        "WikiSkill (1+TReAct)*Ntrain/B and asymptotic Ntrain/B retained."]
    decisions=[dict(passed=True,evidence=note,observed_sha256=digest(o)) for o,note in zip(observations,rationales,strict=True)]
    math_result=score_math(observations,decisions)
    write("table-math-evaluation.json",dict(result=math_result,observations=observations,explicit_source_decisions=decisions,
        note="Root visually reviewed all four source rows; no automated algebra-equivalence claim."))
    all_pass=all(r["passed"] for r in results.values()) and math_result["passed"]
    summary=dict(cases=results,table_math=math_result,preservation=preservation_results,
        T03_live="eligible only if all seven sources pass" if all_pass else "NOT_RUN: fixed single-page quality gate failed",
        external_28_page_regression="NOT_RUN: DEV gate failed" if not all_pass else "pending T03 gate",
        promoted=all_pass,execution=read(HERE/"live/execution.json"),
        conclusion="B candidate not promoted: required model family condition wrong" if not all_pass else "single-page gates pass; T03 still pending",
        source_review_evidence="All seven frozen input crops viewed; same-source oracle and Core/rendered correspondence recorded per case.")
    write("evaluation.json",summary)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=="__main__":main()
