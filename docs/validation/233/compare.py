"""#233: this rerun of #199's validation against #199's pilot2, paper by paper and item by item.

    .venv/bin/python docs/validation/233/compare.py

Reads #199's evidence as committed at BASELINE (pilot2) and this folder's (what #199's run.py
and score.py wrote for this rerun, moved here), and writes compare.json here: per paper the
values that differ (inventory counts, statuses, receipts by method, outcome), and per scored
chart, description, formula and code unit the fields that differ. Equal values are left out,
so an empty entry means no difference; every difference still needs an attribution in the
README.
"""

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = "19b92af"  # dev when the rerun started; its docs/validation/199 is pilot2's evidence
PAPER_FIELDS = ("outcome", "inventory_items", "inventory_counts", "statuses", "receipts", "d3", "pass")


def baseline(path: str) -> dict:
    shown = subprocess.run(["git", "show", f"{BASELINE}:docs/validation/199/{path}"],
                           check=True, capture_output=True, text=True, cwd=HERE)  # fmt: skip
    return json.loads(shown.stdout)


def diff(before, after, path: str = "") -> dict:
    """{dotted path: [before, after]} for every leaf that differs."""
    if isinstance(before, dict) and isinstance(after, dict):
        found: dict = {}
        for key in sorted((before.keys() | after.keys()) - {"latency_ms"}):  # timing, not compared
            found |= diff(before.get(key), after.get(key), f"{path}.{key}" if path else key)
        return found
    return {} if before == after else {path: [before, after]}


def by(rows: list[dict], key: str) -> dict:
    return {str(r[key]): r for r in rows}


def main() -> None:
    papers = {}
    for row in sorted((HERE / "papers").glob("*.json")):
        new, old = json.loads(row.read_text()), baseline(f"papers/{row.name}")
        papers[row.stem] = diff({k: old.get(k) for k in PAPER_FIELDS}, {k: new.get(k) for k in PAPER_FIELDS})
    old, new = baseline("accuracy.json"), json.loads((HERE / "accuracy.json").read_text())
    items = {"summary": diff(old["summary"], new["summary"])}
    for kind, key in (("charts", "gold_index"), ("descriptions", "label"), ("formulas", "label")):
        items[kind] = {k: d for k, d in diff(by(old[kind], key), by(new[kind], key)).items()}
    items["code"] = diff(by(old["code"]["rows"], "unit"), by(new["code"]["rows"], "unit"))
    (HERE / "compare.json").write_text(json.dumps({"baseline": BASELINE, "papers": papers, "accuracy": items},
                                                  indent=1) + "\n")  # fmt: skip
    for name, found in papers.items():
        print(name, len(found), "differences")
    for kind, found in items.items():
        print(kind, len(found), "differences")


if __name__ == "__main__":
    main()
