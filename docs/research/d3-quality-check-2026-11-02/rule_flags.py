"""#153 §6: the shipped formula status rule (FORMULA_NATIVE_MISMATCH) on every T4 formula answer.

    .venv/bin/python docs/research/d3-quality-check-2026-11-02/rule_flags.py OUT MANIFEST

For each T4 formula item, reads the native text of its box from the source PDF the way
formula.parse does and applies formula.mismatch to the answer's LaTeX. W4b's CodeFormulaV2
items have no box in this corpus and get no flag (null in score.py). Writes OUT/rule-flags.json.
"""

import json
import sys
from pathlib import Path

from kp_processing.methods import formula

REPO = Path(__file__).resolve().parents[3]
TARGETS = REPO / "docs/validation/80/t4-accuracy/targets.json"


def main(out: Path, manifest: Path) -> int:
    papers = {p["index"]: p for p in json.loads(manifest.read_text())["papers"]}
    targets = {t["label"]: t for t in json.loads(TARGETS.read_text()) if t["kind"] == "formula"}
    items = [json.loads(line) for line in (out / "items.jsonl").read_text().splitlines()]
    native, flags = {}, {}
    for item in items:
        if item["category"] != "formula" or not item["id"].startswith("t4/formula/"):
            continue
        label = item["id"].split("/")[2]
        if label not in native:
            target = targets[label]
            paper = papers[target["paper"]]
            source = (manifest.parent / paper["file"]).read_bytes()
            native[label] = formula._native_text(target["item"], source)
        flags[item["id"]] = formula.mismatch(native[label], item["reconstruction"])
    (out / "rule-flags.json").write_text(json.dumps(flags, indent=1, sort_keys=True) + "\n")
    print(
        len(flags), "T4 formula answers;", sum(flags.values()), "flagged;", len(native), "formulas"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
