"""Merge disjoint page reviews and count source events, not metric alerts."""
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R3 = HERE.parent / "pdf-core-w2-native-coverage-round3-2026-10-20"


def load(path):
    return json.loads(path.read_text())


def identity(row):
    return row["direction"], row["job_id"], json.dumps(row["identity"], sort_keys=True)


def main():
    changed = load(HERE / "comparison/V4-changed-cases.json")
    original = load(HERE / "comparison/original30-semantic-records.json")
    recovery = load(HERE / "comparison/recovery-semantic-records.json")
    records = original + recovery["changed_records"]
    keys = [identity(r) for r in records]
    assert len(set(keys)) == len(keys), "Overlapping review ownership"
    assert set(keys) == {identity(c) for c in changed}, dict(missing=len({identity(c) for c in changed}-set(keys)), extra=len(set(keys)-{identity(c) for c in changed}))
    assert all(r.get("reviewed_visual") and r.get("reviewed_native_and_markdown") for r in records)
    assert all("PENDING" not in r["semantic_verdict"] and "UNKNOWN" not in r["semantic_verdict"] for r in records)
    checks = load(HERE / "adjudication/original30-baseline-group-checks.json") + recovery["baseline_group_checks"]
    frozen = load(R3 / "adjudication/root-groups.json")
    ids = [r["source_rootcause_group"] for r in checks]
    assert len(ids) == 26 and len(set(ids)) == 26 and set(ids) == {r["group_id"] for r in frozen}
    assert all("PENDING" not in r["semantic_verdict"] and r.get("page_images") and r.get("variant_reason") for r in checks)
    papers = {r["job_id"]:r for r in load(R3 / "adjudication/papers.json")}
    fixed = [r for r in checks if r.get("q4_fixed")]
    partial = [r for r in checks if r.get("q4_partial_fix") or r["semantic_verdict"].startswith("PARTIAL_")]
    new = [r for r in records if r.get("q4_new_bad")]
    newgroups = []
    for gid in sorted({r["source_rootcause_group"] for r in new}):
        rows = [r for r in new if r["source_rootcause_group"] == gid]
        jobs = {r["job_id"] for r in rows}
        assert len(jobs) == 1
        job = next(iter(jobs))
        newgroups.append(dict(group_id=gid, job_id=job, family=papers[job]["family"],
                              affected_pages=sorted({p for r in rows for p in r.get("affected_pages", r.get("pages", []))}),
                              alert_rows=len(rows), failure_types=sorted({r.get("failure_type", r["kind"]) for r in rows}),
                              source_reason=rows[0]["source_reason"], variant_reason=rows[0]["variant_reason"],
                              evidence_records=rows))
    families = []
    for family in sorted({p["family"] for p in papers.values()}):
        families.append(dict(family=family,
                             fixed_groups=sum(papers[r["job_id"]]["family"] == family for r in fixed),
                             partial_groups=sum(papers[r["job_id"]]["family"] == family for r in partial),
                             new_blocking_groups=sum(r["family"] == family for r in newgroups)))
    result = dict(variant="V4", documents=36, pages=715, removed=sum(c["direction"]=="removed" for c in changed),
                  added=sum(c["direction"]=="added" for c in changed), changed_identity_rows_reviewed=len(records),
                  changed_identity_coverage="COMPLETE", original_groups_reviewed=len(checks),
                  full_fixed_groups=len(fixed), partial_fixed_groups=len(partial),
                  persisting_without_full_fix=len(checks)-len(fixed),
                  new_blocking_groups=len(newgroups), new_blocking_documents=len({g["job_id"] for g in newgroups}),
                  new_blocking_job_pages=len({(g["job_id"],p) for g in newgroups for p in g["affected_pages"]}),
                  recommendation="ADOPT" if not newgroups and fixed else "DO_NOT_ADOPT",
                  fixed_group_ids=[r["source_rootcause_group"] for r in fixed],
                  partial_group_ids=[r["source_rootcause_group"] for r in partial],
                  baseline_group_checks=checks, changed_records=records, new_groups=newgroups, families=families,
                  distinction="26 frozen source events remain the repair denominator. Alert churn, newly discovered pre-existing defects, heading role transitions, and within-group newly missing objects are reported separately. Review is source-anchor/known-event scoped, not full-word equivalence.")
    (HERE / "comparison/V4-adjudicated.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("baseline_group_checks","changed_records","new_groups","families")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
