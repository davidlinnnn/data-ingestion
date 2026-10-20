"""Combine preserved W3b scorer rows with W3c visual adjudications; no inference."""
import csv, json, hashlib
from pathlib import Path
from collections import Counter, defaultdict
P=Path(__file__).resolve().parent; W=P.parent
def load(p): return json.loads(p.read_text())
original={v:load(W/f"table/results/{v}-v4.json") for v in ["E0","cellFalse"]}
reg=load(P/"regression-audit/adjudication.json")["cases"]
pa=load(P/"pass-audit/sample-audit.json")["records"]
assert len(reg)==8 and len(pa)==8
assert not ({x["id"] for x in reg}&{x["id"] for x in pa})
overrides={}
for case in reg:
    for v,key in [("E0","baseline"),("cellFalse","cellFalse")]:
        for ch in ["RAW","MAPPED"]:
            r=case[key][ch]
            assert case["Q13_error_threshold"]==(0.05 if case["Q13"]=="complex" else 0)
            overrides[(case["id"],v,ch)]=dict(r, review="regression-audit", manual=True)
for case in pa:
    assert case["Q13_failure_threshold"]==(0.05 if case["Q13"]=="complex" else 0)
    for v,key in [("E0","baseline_manual"),("cellFalse","cellFalse_manual")]:
        for ch in ["RAW","MAPPED"]:
            r=case[key][ch];b=case["error_rate_bounds"][v][ch]
            overrides[(case["id"],v,ch)]=dict(r, **b, rate_exact=b["status"]=="EXACT_MANUAL_COMPLETE_TABLE", numeric_denominator_N=case["N"], review="pass-audit", manual=True)
rows=[]; counts=defaultdict(Counter)
for v,data in original.items():
    assert len(data["semantic_tables"])==246
    selected=[t for t in data["semantic_tables"] if t["scope"]=="IN_SCOPE"]
    assert len(selected)==183
    for t in selected:
        for ch in ["RAW","MAPPED"]:
            a=t["channel_results"][ch];r=overrides.get((t["id"],v,ch),dict(a,manual=False,review="W3b scorer carried forward; not visually re-adjudicated in W3c"))
            exact=r.get("rate_exact", False) if r.get("manual") else (a.get("error_rate_lower") is not None and a.get("error_rate_upper")==a.get("error_rate_lower"))
            row=dict(id=t["id"],job_id=t["job_id"],pages=t["pages"],Q13=t["Q13"],variant=v,channel=ch,original_verdict=a["verdict"],original_machine_error_rate_lower=a.get("error_rate_lower"),original_machine_error_rate_upper=a.get("error_rate_upper"),verdict=r["verdict"],frozen_source_N=t["N"],effective_N=r.get("numeric_denominator_N",t["N"]),full_numeric_denominator_upper=r.get("full_numeric_denominator_upper"),error_rate_lower=r.get("error_rate_lower"),error_rate_upper=r.get("error_rate_upper"),rate_exact=exact,manual=r.get("manual",False),review=r["review"],reason=r.get("reason"),source_upper_bound_reason=r.get("upper_unresolved_reason",r.get("upper_bound_reason")))
            rows.append(row);counts[(v,ch,t["Q13"])][r["verdict"]]+=1
assert len(rows)==732
summary={}
for v in ["E0","cellFalse"]:
    summary[v]={}
    for ch in ["RAW","MAPPED"]:
        summary[v][ch]={q:{k:counts[(v,ch,q)][k] for k in ["PASS","FAIL","UNKNOWN"]} for q in ["ordinary","complex"]}
        total=Counter()
        for q in ["ordinary","complex"]: total.update(counts[(v,ch,q)])
        summary[v][ch]["total"]={k:total[k] for k in ["PASS","FAIL","UNKNOWN"]}
assert summary["E0"]["MAPPED"]["total"]==dict(PASS=11,FAIL=12,UNKNOWN=160)
assert summary["cellFalse"]["MAPPED"]["total"]==dict(PASS=30,FAIL=8,UNKNOWN=145)
assert summary["cellFalse"]["RAW"]["total"]==dict(PASS=27,FAIL=9,UNKNOWN=147)
fail=[r for r in rows if r["verdict"]=="FAIL"]
assert len(fail)==41
for r in fail:
    assert r["error_rate_lower"] is not None
    assert r["error_rate_lower"]>(.05 if r["Q13"]=="complex" else 0), r
for name,data in [("per-table-final.json",rows),("fail-tables-final.json",fail),("q13-summary.json",summary)]: (P/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
for name,data in [("per-table-final.csv",rows),("fail-tables-final.csv",fail)]:
    with (P/name).open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
lines=["# W3c Q13人工裁定後彙總","", "僅16張定向稽核表套用人工裁定；其他表沿用W3b機器結果，未冒稱全量人審。60張來源定位UNKNOWN、3張範圍外仍另列，Adam來源不可知。", "", "|版本|交付|一般 P/F/U|複雜 P/F/U|合計 P/F/U|", "|---|---|---|---|---|"]
for v in ["E0","cellFalse"]:
    for ch in ["RAW","MAPPED"]:
        s=summary[v][ch];fmt=lambda q:"/".join(str(s[q][k]) for k in ["PASS","FAIL","UNKNOWN"])
        lines.append(f"|{v}|{ch}|{fmt('ordinary')}|{fmt('complex')}|{fmt('total')}|")
lines += ["", "# 全部FAIL表的錯率", "", "精確率以=標示；≥為確證下界，未完成全點／多生裁定時無精確率或上界。沿用機器者另標。漏與多生都計錯，不將率硬截100%。RAW/MAPPED相同表仍保留兩行供核對。", "", "|版本/交付|表/頁|Q13|錯率|來源|", "|---|---|---|---|---|"]
for r in fail:
    rate=("=" if r["rate_exact"] else "≥")+f"{r['error_rate_lower']*100:.4f}%"
    lines.append(f"|{r['variant']}/{r['channel']}|{r['id']} p{','.join(map(str,r['pages']))}|{r['Q13']}|{rate}|{'本輪人審' if r['manual'] else '沿用機器，非本輪人審'}|")
lines += ["", "P04 p7 T1原frozen N344不是完整的主分數＋gain component分母；本輪用完整數字個數上界688與36個確證缺失，報≥36/688=5.2326%，不再冒稱36/344為精確率。原答案不改，來源缺陷另記。"]
(P/"q13-summary.md").write_text("\n".join(lines)+"\n")
print(json.dumps(summary,ensure_ascii=False))
