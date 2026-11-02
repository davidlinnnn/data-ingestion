"""#153: d3 result files to score.py rows.

    python3 docs/research/d3-quality-check-2026-11-02/to_rows.py \
        OUT MODEL SPLIT [--rule-flags FLAGS]

Joins OUT/runs/MODEL/SPLIT/*.result.json to OUT/labels.jsonl by item id and writes
OUT/rows/MODEL-SPLIT.jsonl. Dev rows carry both raw scores; test rows carry the asked
question's score. FLAGS (JSON id -> bool) supplies formula rule flags for test. Every labelled
item of the split must have exactly one result.
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("model")
    parser.add_argument("split", choices=["dev", "test"])
    parser.add_argument("--rule-flags", type=Path)
    a = parser.parse_args()
    labels = {
        r["id"]: r
        for r in map(json.loads, (a.out / "labels.jsonl").read_text().splitlines())
        if r["split"] == a.split
    }
    flags = json.loads(a.rule_flags.read_text()) if a.rule_flags else {}
    results = [
        json.loads(p.read_text())
        for p in (a.out / "runs" / a.model / a.split).glob("*.result.json")
    ]
    by_id = {r["id"]: r for r in results}
    assert len(by_id) == len(results), "duplicate results"
    assert set(by_id) == set(labels), (len(set(labels) - set(by_id)), len(set(by_id) - set(labels)))
    rows = []
    for item_id, label in sorted(labels.items()):
        result = by_id[item_id]
        ok = result["state"] == "OK"
        scores = result.get("safe_scores", {}) if ok else {}
        row = {
            "id": item_id,
            "model": a.model,
            "category": label["category"],
            "split": a.split,
            "group": label["group"],
            "label": label["label"],
            "q1": scores.get("Q1") if a.split == "dev" else None,
            "q2": scores.get("Q2") if a.split == "dev" else None,
            "score": None,
            "failed": not ok,
            "rule_flag": flags.get(item_id) if label["category"] == "formula" else None,
        }
        if a.split == "test" and ok:
            (question,) = result["questions"]
            row["score"] = scores[question]
        rows.append(row)
    target = a.out / "rows" / f"{a.model}-{a.split}.jsonl"
    target.parent.mkdir(exist_ok=True)
    target.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(len(rows), "rows;", sum(r["failed"] for r in rows), "failed ->", target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
