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
    """{slash-separated path: [before, after]} for every leaf that differs ("/": check-publish
    reads a dotted path through a method ref, a.b@c.d, as an email)."""
    if isinstance(before, dict) and isinstance(after, dict):
        found: dict = {}
        for key in sorted((before.keys() | after.keys()) - {"latency_ms"}):  # timing, not compared
            found |= diff(before.get(key), after.get(key), f"{path}/{key}" if path else key)
        return found
    return {} if before == after else {path: [before, after]}


def keyed(rows: list[dict], key: str) -> dict:
    found = {str(r[key]): r for r in rows}
    assert len(found) == len(rows), f"rows share a {key}"
    return found


def main() -> None:
    listed = subprocess.run(["git", "ls-tree", "--full-tree", "--name-only", f"{BASELINE}:docs/validation/199/papers"],
                            check=True, capture_output=True, text=True, cwd=HERE).stdout.split()  # fmt: skip
    paths = sorted((HERE / "papers").glob("*.json"))
    assert sorted(p.name for p in paths) == sorted(listed), "papers differ from pilot2's"
    papers = {}
    for path in paths:
        new, old = json.loads(path.read_text()), baseline(f"papers/{path.name}")
        assert set(PAPER_FIELDS) <= new.keys() & old.keys(), f"{path.name} lacks a compared field"
        papers[path.stem] = diff({k: old[k] for k in PAPER_FIELDS}, {k: new[k] for k in PAPER_FIELDS})
    old, new = baseline("accuracy.json"), json.loads((HERE / "accuracy.json").read_text())
    items = {"summary": diff(old["summary"], new["summary"])}
    for kind, key in (("charts", "gold_index"), ("descriptions", "label"), ("formulas", "label")):
        items[kind] = diff(keyed(old[kind], key), keyed(new[kind], key))
    items["code"] = diff(keyed(old["code"]["rows"], "unit"), keyed(new["code"]["rows"], "unit"))
    (HERE / "compare.json").write_text(json.dumps({"baseline": BASELINE, "papers": papers, "accuracy": items},
                                                  indent=1) + "\n")  # fmt: skip
    for name, found in papers.items():
        print(name, len(found), "differences")
    for kind, found in items.items():
        print(kind, len(found), "differences")


if __name__ == "__main__":
    main()
