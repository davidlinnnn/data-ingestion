"""Final W3b bookkeeping only: no scoring, inference, or source mutations."""
import datetime, hashlib, json, re
from pathlib import Path
P = Path(__file__).resolve().parent
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(n): return json.loads((P/n).read_text())
def sha(n): return hashlib.sha256((P/n).read_bytes()).hexdigest()
def write(n, obj): (P/n).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n")
checks=[]
for name, base in [("oracle-freeze.json", ""), ("table/analysis-freeze-v4.json", "table"), ("formula/assessment/freeze-v1.json", "formula"), ("formula/assessment-v2/freeze.json", "formula"), ("code-native/analysis-freeze.json", "code-native"), ("code-native-v4-utf16/analysis-freeze.json", "code-native-v4-utf16"), ("signals/analysis-freeze.json", "")]:
    seal=load(name); files=seal.get("files_sha256",seal.get("files",seal))
    if isinstance(files,list): files={x["path"]:x["sha256"] for x in files}
    changed=[n for n,h in files.items() if not (P/base/n).is_file() or sha(str(Path(base)/n))!=h]
    checks.append(dict(check="sealed files unchanged", freeze=name, count=len(files), changed=changed, passed=not changed))
rows=load("signals/cohort-combined.json")["rows"]
checks.append(dict(check="207 source records retained; subviews not added", count=len(rows), passed=len(rows)==207))
f=load("formula/combined-summary-root.json")
checks.append(dict(check="formula independent source denominators", E1=f["E1_independent_scored"], E0=f["E0orig_independent_scored"], passed=f["E1_independent_scored"]==40 and f["E0orig_independent_scored"]==126))
c=load("code-native-v4-utf16/summary.json")
checks.append(dict(check="99 code/algorithm source units retained", count=c["inventory_units"], passed=c["inventory_units"]==99))
text=(P/"report.md").read_text(); broken=[]
for ref in re.findall(r"\]\(([^)]+)\)",text):
    if not ref.startswith(("https:","http:","#")) and ref not in {"results-index.json", "completion-manifest.json", "completion-checks.json"} and not (P/ref.split("#")[0]).exists(): broken.append(ref)
checks.append(dict(check="main report relative links exist", broken=broken, passed=not broken))
for name in ["table/summary.json", "formula/combined-summary-root.json", "code-native-v4-utf16/summary.json", "signals/metrics.json"]:
    json.loads((P/name).read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
checks.append(dict(check="summary metrics JSON has no NaN or Infinity", passed=True))
qa=load("signals/independent-qa.json")
checks.append(dict(check="signal independent QA", passed=qa["all_checks_pass"]))
assert all(c["passed"] for c in checks), checks
write("completion-checks.json",dict(created_utc=now, checks=checks, all_passed=True))
s=load("stage-log.json"); s["stage4"]["analysis_version"]="v4-utf16-final"; s["stage5"].update(status="complete", completed_utc=now)
write("stage-log.json",s)
selected=["report.md","oracle-freeze.json","html-manifest.json","source-trust.md","registration.json","access-scope-amendment.json","stage-log.json","completion-checks.json","table/analysis-freeze-v4.json","table/family-summary-supplement.json","table/per-table.csv","formula/assessment-v2/freeze.json","formula/combined-summary-root.json","code-native-v4-utf16/analysis-freeze.json","code-native/line-diagnostics-root.csv","signals/analysis-freeze.json","signals/report.md","signals/metrics.json","signals/independent-qa.json","signals/figures/roc-by-cohort.png","signals/figures/roc-by-cohort.pdf","cell-resources.json","execution-checks.json","page-scope-control.json","finalize_root.py"]
missing=[n for n in selected if not (P/n).is_file()]
assert not missing, missing
write("results-index.json", dict(created_utc=now, authoritative={"source":"oracle-freeze.json","tables":"table/analysis-freeze-v4.json","table_family":"table/family-summary-supplement.json","formula":"formula/assessment-v2/freeze.json","code":"code-native-v4-utf16/analysis-freeze.json","signals":"signals/analysis-freeze.json"}, no_new_E1=True, no_commit_push_or_GitHub_write=True))
selected.append("results-index.json")
write("completion-manifest.json",dict(completed_utc=now, source_start_utc="2026-10-20T11:00:36+00:00", deadline_utc="2026-10-20T14:00:36+00:00", all_checks_passed=True, files_sha256={n:sha(n) for n in selected}))
assert all((P/n).is_file() for n in ["results-index.json", "completion-manifest.json", "completion-checks.json"])
print(json.dumps(dict(completed_utc=now,checks=len(checks),manifest_files=len(selected),all_passed=True)))
