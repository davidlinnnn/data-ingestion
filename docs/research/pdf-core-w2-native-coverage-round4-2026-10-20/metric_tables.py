"""Frozen-v3 descriptive metrics; do not convert alert deltas to Q4 verdicts."""
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def summarize(rows):
    out = dict(documents=len(rows), pages=sum(r["selected_pages"] for r in rows))
    for name in ("trusted_prose", "body_or_md_found", "missing", "duplicate", "md_lis_outside", "candidate_count", "furniture_contamination", "furniture_raw_body_matches"):
        out[name] = sum(r[name] for r in rows)
    out["anchor_coverage"] = out["body_or_md_found"] / out["trusted_prose"] if out["trusted_prose"] else None
    out["md_lis_aligned"] = sum(r["md_order"].get("aligned", 0) for r in rows)
    out["md_lis_ratio"] = out["md_lis_outside"] / out["md_lis_aligned"] if out["md_lis_aligned"] else None
    for metric, status in (("mixed_paragraphs", "mixed_paragraph_status"), ("column_jumps", "column_jump_status")):
        out[metric] = sum(r[metric] or 0 for r in rows)
        out[status] = dict(collections.Counter(r[status] for r in rows))
    out["classes"] = {kind: dict(sum((collections.Counter(r["classes"][kind]) for r in rows), collections.Counter())) for kind in ("caption", "footnote")}
    return out


def main():
    load = lambda p: json.loads(p.read_text())
    datasets = {name: load(HERE / "analysis" / name / "summary.json") for name in ("baseline", "V4")}
    assert all(len(rows) == 36 for rows in datasets.values())
    result = dict(scope="Frozen v3 alerts; symbolic/oracle/classification differences are not semantic fixes. Adam uses imperfect PDFium text-layer fallback; mixed and column metrics retain NOT_EVALUABLE states.",
                  total={name:summarize(rows) for name,rows in datasets.items()}, families=[], papers=[])
    for family in sorted({r["family"] for r in datasets["baseline"]}):
        result["families"].append(dict(family=family, **{name:summarize([r for r in rows if r["family"] == family]) for name,rows in datasets.items()}))
    before = {r["id"]:r for r in datasets["baseline"]}
    for after in datasets["V4"]:
        b = before[after["id"]]
        result["papers"].append(dict(id=after["id"], title=after["title"], family=after["family"], pages=after["selected_pages"],
                                     baseline=summarize([b]), V4=summarize([after])))
    (HERE / "comparison/metric-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["total"], ensure_ascii=False))


if __name__ == "__main__":
    main()
