"""W3c final evidence/hash checks; reads old artifacts and writes only this directory."""
from pathlib import Path
import json, hashlib, datetime, re
P=Path(__file__).resolve().parent; W=P.parent
load=lambda q:json.loads(q.read_text())
sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
checks=[]
def check(name, condition, **info):
    assert condition,(name,info)
    checks.append(dict(check=name,passed=True,**info))
parent=load(W/"completion-manifest.json")
bad=[n for n,h in parent["files_sha256"].items() if sha(W/n)!=h]
check("W3b completion 26 files unchanged", not bad, bad=bad, files=len(parent["files_sha256"]))
source=load(W/"oracle-freeze.json")["files_sha256"]
bad=[n for n,h in source.items() if sha(W/n)!=h]
check("frozen source108 unchanged",not bad,files=len(source),bad=bad)
reg=load(P/"regression-audit/adjudication.json")["cases"]
pa=load(P/"pass-audit/sample-audit.json")["records"]
check("all8suspected and all3fixed plus5newPASS audited",len(reg)==8 and len(pa)==8 and len({r["id"] for r in reg+pa})==16)
check("all16visually reviewed",all(x["reviewed_visual"] for x in reg+pa))
regseal=load(P/"regression-audit/freeze.json")
bad=[n for n,h in regseal.items() if sha(P/"regression-audit"/n)!=h]
check("regression audit sealed files unchanged",not bad,files=len(regseal),bad=bad)
check("pass audit final SHA unchanged",sha(P/"pass-audit/sample-audit.json")=="ed1946d1a9b4507442a9232e1abb4a6ec25ee095b983b3bc009e5383802dae96")

base=load(W/"table/results/E0-v4.json")["semantic_tables"];new=load(W/"table/results/cellFalse-v4.json")["semantic_tables"]
ba={x["id"]:x for x in base};na={x["id"]:x for x in new}
expected={n for n in ba if ba[n].get("channel_results",{}).get("MAPPED",{}).get("verdict")=="UNKNOWN" and na[n].get("channel_results",{}).get("MAPPED",{}).get("verdict")=="FAIL"}
check("8regression cases exactly match original transitions",{x["id"] for x in reg}==expected)
sample=load(P/"pass-audit/sample-registration.json")
ids=sorted([n for n in ba if ba[n].get("channel_results",{}).get("MAPPED",{}).get("verdict")=="UNKNOWN" and na[n].get("channel_results",{}).get("MAPPED",{}).get("verdict")=="PASS"],key=lambda n:(hashlib.sha256((sample["seed"]+"\n"+n).encode()).hexdigest(),n))
check("fixed hash sample reproduced", ids[:5]==sample["UNKNOWN_to_PASS_selected"], population=len(ids))
for x in reg: check("regression Q13 threshold "+x["id"],x["Q13_error_threshold"]==(.05 if x["Q13"]=="complex" else 0))
for x in pa: check("sample Q13 threshold "+x["id"],x["Q13_failure_threshold"]==(.05 if x["Q13"]=="complex" else 0))
rows=load(P/"per-table-final.json");summary=load(P/"q13-summary.json")
check("183 tables times 2variants times 2channels",len(rows)==732)
for v in ["E0","cellFalse"]:
 for ch in ["RAW","MAPPED"]:
    check(v+ch+" totals183",sum(summary[v][ch]["total"].values())==183)
regressions={};fixes={}
for ch in ["RAW","MAPPED"]:
 old={r["id"]:r for r in rows if r["variant"]=="E0" and r["channel"]==ch}
 new={r["id"]:r for r in rows if r["variant"]=="cellFalse" and r["channel"]==ch}
 regressions[ch]=[n for n in old if old[n]["manual"] and new[n]["manual"] and old[n]["verdict"]=="PASS" and new[n]["verdict"]=="FAIL"]
 fixes[ch]=[n for n in old if old[n]["manual"] and new[n]["manual"] and old[n]["verdict"]=="FAIL" and new[n]["verdict"]=="PASS"]
check("confirmed regressions mapped3 raw4",len(regressions["MAPPED"])==3 and len(regressions["RAW"])==4)
check("confirmed fixes both4",all(len(x)==4 for x in fixes.values()))
for n in ["root-audit/P15-independent-adjudication.json","root-audit/P19-independent-adjudication.json"]:
 x=load(P/n);check("independent root decision agrees "+n,x["regression_confirmed"] and x["baseline_manual_data_point_verdict"]=="PASS")
check("body final report exists",(P/"body-impact/report.md").is_file())
bodyseal=load(P/"body-impact/freeze.json")
bad=[x["path"] for x in bodyseal["files"] if sha(P/"body-impact"/x["path"])!=x["sha256"]]
check("body208 sealed artifacts unchanged",not bad,files=len(bodyseal["files"]),bad=bad)
bodyinputs=load(P/"body-impact/source-manifest-final.json")["files"]
bad=[n for n,m in bodyinputs.items() if sha(Path(n))!=m["sha256"]]
check("body original895 source inputs unchanged",not bad,files=len(bodyinputs),bad=bad)
check("body replay all17 asserts PASS and no inference",bodyseal["all17_asserts_pass"] and bodyseal["conversion_calls"]==0 and bodyseal["neural_model_inference_calls"]==0 and bodyseal["API_calls"]==0)

text=(P/"report.md").read_text();bad=[]
for ref in re.findall(r"\]\(([^)]+)\)",text):
 if not ref.startswith(("https:","http:","#")) and not (P/ref.split("#")[0]).exists():bad.append(ref)
check("main report links exist",not bad,broken=bad)
now=datetime.datetime.now(datetime.timezone.utc)
check("within45minute budget",now<datetime.datetime.fromisoformat("2026-10-20T13:57:20+00:00"))
result=dict(completed_utc=now.isoformat(), checks=checks, all_checks_pass=True, confirmed_regressions=regressions, confirmed_fixes=fixes, inference_runs=0,conversion_runs=0,API_calls=0,source_answers_unchanged=True,old_results_unchanged=True)
(P/"completion-checks.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
files={str(q.relative_to(P)):sha(q) for q in P.rglob("*") if q.is_file() and q.name!="completion-manifest.json" and "chrome" not in q.relative_to(P).parts and q.suffix in {".json",".md",".py",".csv",".html",".png",".txt"}}
(P/"completion-manifest.json").write_text(json.dumps(dict(completed_utc=now.isoformat(), status="COMPLETE_AND_STOPPED",new_inference=False,files_sha256=files),ensure_ascii=False,indent=2)+"\n")
print(json.dumps(dict(checks=len(checks),all_pass=True,manifest_files=len(files),completed_utc=now.isoformat())))
