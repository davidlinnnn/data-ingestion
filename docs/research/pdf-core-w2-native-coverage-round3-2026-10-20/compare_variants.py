"""Source-identity candidate changes, explicitly separate from Q4 adjudication."""
import collections
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent


def load(path):return json.loads(path.read_text())


def key(c):
    kind=c["kind"]
    if kind=="furniture_in_body":
        return (kind,tuple(c["pages"]),tuple(c.get("source_raw_char_range",[])))
    return (kind,tuple(c.get("anchor_ids",[])),tuple(c.get("pages",[])))


def compare(name):
    base=load(HERE/"analysis/baseline/summary.json")
    variant=load(HERE/"analysis"/name/"summary.json")
    bc=load(HERE/"analysis/baseline/candidate-catalog.json")
    vc=load(HERE/"analysis"/name/"candidate-catalog.json")
    summaries={r["id"]:r for r in variant}
    cases=[];papers=[];aggregate=collections.defaultdict(lambda:collections.Counter())
    for b in base:
        v=summaries[b["id"]]
        pair=dict(id=b["id"],family=b["family"],baseline_status=b["conversion_status"],variant_status=v["conversion_status"])
        if b["metric_status"]!="SCORED_CANDIDATES" or v["metric_status"]!="SCORED_CANDIDATES":
            pair.update(comparison="UNKNOWN_MISSING_OUTPUT");papers.append(pair);continue
        original={key(c):c for c in bc if c["job_id"]==b["id"]}
        changed={key(c):c for c in vc if c["job_id"]==b["id"]}
        changes=[]
        for direction,keys in (("removed",original.keys()-changed.keys()),("added",changed.keys()-original.keys())):
            for identity in sorted(keys):
                c=(original if direction=="removed" else changed)[identity]
                row=dict(variant=name,direction=direction,job_id=b["id"],family=b["family"],kind=c["kind"],
                         identity=identity,candidate=c,semantic_verdict="PENDING_ADJUDICATION")
                cases.append(row);changes.append(row)
                aggregate[(b["family"],c["kind"])][direction]+=1
        pair.update(comparison="SCORED_CANDIDATE_DIFFERENCES",removed=len([c for c in changes if c["direction"]=="removed"]),
                    added=len([c for c in changes if c["direction"]=="added"]),
                    missing_before=b["missing"],missing_after=v["missing"],
                    duplicate_before=b["duplicate"],duplicate_after=v["duplicate"],
                    md_lis_before=b["md_lis_outside"],md_lis_after=v["md_lis_outside"],
                    caption_body_before=b["classes"]["caption"]["in_body"],caption_body_after=v["classes"]["caption"]["in_body"])
        papers.append(pair)
    out=HERE/"comparison";out.mkdir(exist_ok=True)
    byfamily=[dict(family=f,kind=k,**counts) for (f,k),counts in sorted(aggregate.items())]
    data=dict(variant=name,definition="Source-identity automatic candidate disappearances/additions. They are not confirmed fixes/regressions until page-image adjudication.",
              removed=sum(c["direction"]=="removed" for c in cases),added=sum(c["direction"]=="added" for c in cases),
              papers=papers,by_family_and_type=byfamily)
    (out/(name+".json")).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
    (out/(name+"-changed-cases.json")).write_text(json.dumps(cases,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"variant":name,"removed":data["removed"],"added":data["added"],"changed_job_pages":len({(c['job_id'],p) for c in cases for p in c['candidate'].get('pages',[])})}))


if __name__=="__main__":
    assert key({"kind":"missing_anchor","anchor_ids":["a"],"pages":[1],"id":"old"})==key({"kind":"missing_anchor","anchor_ids":["a"],"pages":[1],"id":"new"})
    compare(sys.argv[1])
