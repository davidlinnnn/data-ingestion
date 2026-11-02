"""#153 §4: final labels and the dev/test split, written before any d3 output exists.

    python3 docs/research/d3-quality-check-2026-11-02/build_split.py OUT

Label per item: the blind verdict (judging/merged.jsonl) with the user's overrides
(judging/overrides.json) on top, else the old label for items that needed no judging.
PASS → correct, minor → minor, FAIL → meaning_changed; UNKNOWN and excluded items are dropped.
Split: the group is the source page. A category's items on a page W4b judged in that category
keep W4b's split (scoring is per category, so another category on the same page is free);
the rest are dealt
greedily (seed 153) to the side that keeps every category's meaning_changed count, then its
item count, closest to the other side. Writes labels.jsonl and split.json.
"""

import json
import random
import sys
from collections import Counter
from pathlib import Path

SEED = 153
LABEL = {"PASS": "correct", "minor": "minor", "FAIL": "meaning_changed"}


def main(out: Path) -> int:
    items = [json.loads(line) for line in (out / "items.jsonl").read_text().splitlines()]
    merged = {
        m["id"]: m["verdict"]
        for m in map(json.loads, (out / "judging/merged.jsonl").read_text().splitlines())
    }
    overrides = {
        x["id"]: x["label"] for x in json.loads((out / "judging/overrides.json").read_text())
    }
    rows, dropped = [], Counter()
    for item in items:
        verdict = overrides.get(item["id"]) or merged.get(item["id"]) or item["old_label"]
        if item.get("excluded") or verdict not in LABEL:
            dropped[item["category"]] += 1
            continue
        page = item["source_page"]
        rows.append(
            {
                "id": item["id"],
                "category": item["category"],
                "producer": item["producer"],
                "label": LABEL[verdict],
                "group": f"{page['paper']}:{page['page']}",
                "split": page.get("split"),
            }
        )
    inherited = {(r["group"], r["category"]): r["split"] for r in rows if r["split"]}
    for row in rows:
        row["split"] = inherited.get((row["group"], row["category"]))
    pages = {}
    for row in rows:
        if row["split"] is None:
            pages.setdefault(row["group"], []).append(row)
    rng = random.Random(SEED)
    order = sorted(
        pages,
        key=lambda g: (
            -sum(r["label"] == "meaning_changed" for r in pages[g]),
            -len(pages[g]),
            rng.random(),
        ),
    )
    tally = {"dev": Counter(), "test": Counter()}
    categories = sorted({r["category"] for r in rows})
    total = {c: Counter() for c in categories}
    for r in rows:
        total[r["category"]]["items"] += 1
        total[r["category"]]["changed"] += r["label"] == "meaning_changed"

    def add(side, group_rows, sign=1):
        for r in group_rows:
            tally[side][r["category"], "items"] += sign
            tally[side][r["category"], "changed"] += sign * (r["label"] == "meaning_changed")

    # Relative to each category's totals, so a scarce category weighs as much as a large one.
    def imbalance():
        return tuple(
            sum(
                abs(tally["dev"][c, k] - tally["test"][c, k]) / max(1, total[c][k])
                for c in categories
            )
            for k in ("changed", "items")
        )

    for r in rows:
        if r["split"]:
            add(r["split"], [r])
    for group in order:
        costs = {}
        for side in ("dev", "test"):
            add(side, pages[group])
            costs[side] = (*imbalance(), rng.random())
            add(side, pages[group], -1)
        side = min(costs, key=costs.get)
        add(side, pages[group])
        for row in pages[group]:
            row["split"] = side
    (out / "labels.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    summary = {}
    for row in rows:
        cell = summary.setdefault(row["category"], {}).setdefault(row["split"], Counter())
        cell[row["label"]] += 1
        cell["pages"] = len(
            {
                r["group"]
                for r in rows
                if r["category"] == row["category"] and r["split"] == row["split"]
            }
        )
    (out / "split.json").write_text(
        json.dumps(
            {
                "seed": SEED,
                "rule": "page groups per category; W4b (page, category) keep W4b split; rest "
                "greedy-"
                "balanced per category on relative meaning_changed then relative items",
                "inherited_page_categories": len(inherited),
                "assigned_pages": len(pages),
                "dropped": dropped,
                "categories": summary,
            },
            indent=1,
            sort_keys=True,
        )
    )
    for category, sides in sorted(summary.items()):
        print(
            f"{category:12s}",
            "  ".join(
                f"{s}: n={sum(v for k, v in c.items() if k != 'pages')}"
                f" changed={c['meaning_changed']} pages={c['pages']}"
                for s, c in sorted(sides.items())
            ),
        )
    print(len(rows), "labelled rows; dropped", dict(dropped))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
