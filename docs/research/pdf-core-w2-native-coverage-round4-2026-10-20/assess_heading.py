"""Frozen heading reference/evaluator comparison; saved JSON only, no stage rerun."""
import collections
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
R2 = ROOT.parent / "pdf-core-w2-native-coverage-round2-2026-10-20"
R3 = ROOT.parent / "pdf-core-w2-native-coverage-round3-2026-10-20"


def load(path):
    return json.loads(path.read_text())


def main():
    spec = importlib.util.spec_from_file_location("frozen_heading_assessment", R2 / "heading/assess_headings.py")
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    index = load(R2 / "oracle/job-index.json")
    jobs = load(ROOT / "jobs.json")["jobs"]
    rows, changes = [], []
    for job in jobs:
        dest = ROOT / "runs/V4/jobs" / job["id"]
        if not (dest / "conversion.json").exists() or load(dest / "conversion.json").get("status") != "success":
            continue
        oracle = load(Path(index[job["id"]]))
        refs = [x for x in oracle["headings"] if x.get("scope") == "IN_SCOPE"]
        before = evaluator.assess(load(R3 / "runs/V3_B/jobs" / job["id"] / "document.json"), refs)
        after = evaluator.assess(load(dest / "document.json"), refs)
        for i, (b, a) in enumerate(zip(before["headings"], after["headings"])):
            if b["status"] != a["status"]:
                changes.append(dict(job_id=job["id"], reference_index=i, reference=a["reference"],
                                    before=b, after=a, new_bad=b["status"] == "correct" and a["status"] != "correct",
                                    fixed=b["status"] != "correct" and a["status"] == "correct"))
        row = dict(id=job["id"], family=oracle.get("template", {}).get("family") or job["family"],
                   evaluable_headings=len(refs), before=before, after=after)
        row["structural_counts"] = {
            mode: dict(collections.Counter(x["status"] for x in value["headings"]
                                          if x["reference"]["command"] not in ("paragraph", "subparagraph")))
            for mode, value in (("before", before), ("after", after))}
        rows.append(row)
    out = ROOT / "heading"
    out.mkdir(exist_ok=True)
    result = dict(documents=len(rows), jobs=rows,
                  structural_counts={mode: dict(sum((collections.Counter(r["structural_counts"][mode]) for r in rows), collections.Counter()))
                                     for mode in ("before", "after")},
                  fixed=sum(c["fixed"] for c in changes), new_bad=sum(c["new_bad"] for c in changes),
                  scope="Reference heading transitions, not automatically Q4 blocking; source pages require adjudication.")
    (out / "V4-assessment.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (out / "V4-changes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k != "jobs"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
