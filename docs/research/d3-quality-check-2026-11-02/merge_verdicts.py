"""#153 B1/B4: merge the blind judges' verdicts into one verdict per item, list every B4
disagreement with its old label and draw the B1 spot-check sample.

    python3 docs/research/d3-quality-check-2026-11-02/merge_verdicts.py OUT

OUT is the research folder outside git. A task judged twice keeps its later batch: batches
20-23 re-judge b4-0040 under the amendments and the round-1-prompt tasks first judged with
swapped image roles. A verdict whose packet showed other images than its item's is dropped
(repack_r1prompt.py judged those items again). Writes judging/merged.jsonl,
judging/b4-disagreements.json and
judging/b1-spotcheck.json; labels in items.jsonl are not touched until the user's review.
"""

import json
import random
import sys
from pathlib import Path

SEED = 153
SPOT = 10


def main(out: Path) -> int:
    folder = out / "judging"
    items = {r["id"]: r for r in map(json.loads, (out / "items.jsonl").read_text().splitlines())}
    key = json.loads((folder / "key.json").read_text())
    shown = {}
    for path in sorted(folder.glob("batch-*.json")):
        for task in json.loads(path.read_text()):
            shown[task["task"]] = {Path(i["path"]).stem for i in task["images"]}
    latest: dict[str, tuple[int, list[dict]]] = {}
    for path in sorted(folder.glob("verdicts-*.jsonl")):
        batch = int(path.stem.split("-")[1])
        lines: dict[str, list[dict]] = {}
        for line in path.read_text().splitlines():
            if line.strip():
                verdict = json.loads(line)
                lines.setdefault(verdict["task"], []).append(verdict)
        for task, verdicts in lines.items():
            if task not in latest or batch > latest[task][0]:
                latest[task] = (batch, verdicts)
    merged, problems, mismatched = [], [], 0
    for task, answers in sorted(key.items()):
        if all(items[i].get("excluded") for ids in answers.values() for i in ids):
            continue  # W4b R5 inline math: out of scope, pilot verdicts discarded
        if task not in latest:
            problems.append(f"{task}: no verdict")
            continue
        batch, verdicts = latest[task]
        for letter, ids in answers.items():
            for item_id in ids:
                item = items[item_id]
                if {i["sha256"] for i in item["images"]} != shown[task]:
                    mismatched += 1  # packet showed another picture's images; judged again later
                    continue
                field = item["category"] if item["judge_needed"] == "B1" else None
                found = [
                    v
                    for v in verdicts
                    if v["key"] == letter and (field is None or v.get("field") == field)
                ]
                if len(found) != 1:
                    problems.append(f"{task}/{letter}/{field}: {len(found)} verdicts")
                    continue
                v = found[0]
                merged.append(
                    {
                        "id": item_id,
                        "category": item["category"],
                        "judge_needed": item["judge_needed"],
                        "task": task,
                        "batch": batch,
                        "verdict": v["verdict"],
                        "judge_type": v.get("judge_type"),
                        "reason": v["reason"],
                        "old_label": item["old_label"],
                    }
                )
    judged = [m["id"] for m in merged]
    if len(judged) != len(set(judged)):
        problems.append("an item has two verdicts")
    for item_id in sorted(
        {i for i, r in items.items() if r["judge_needed"] != "none" and not r.get("excluded")}
        - set(judged)
    ):
        problems.append(f"{item_id}: never judged")
    (folder / "merged.jsonl").write_text(
        "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in merged)
    )
    old_pass = {"PASS": "PASS", "minor": "PASS", "FAIL": "FAIL"}
    disagree = [
        m for m in merged if m["judge_needed"] == "B4" and old_pass[m["old_label"]] != m["verdict"]
    ]
    (folder / "b4-disagreements.json").write_text(
        json.dumps(disagree, indent=1, ensure_ascii=False)
    )
    rng = random.Random(SEED)
    b1 = sorted((m for m in merged if m["judge_needed"] == "B1"), key=lambda m: m["id"])
    spot = [
        s
        for verdict in ("FAIL", "PASS")
        for s in rng.sample([m for m in b1 if m["verdict"] == verdict], SPOT)
    ]
    (folder / "b1-spotcheck.json").write_text(json.dumps(spot, indent=1, ensure_ascii=False))
    counts: dict[tuple, int] = {}
    for m in merged:
        k = (m["judge_needed"], m["category"], m["verdict"])
        counts[k] = counts.get(k, 0) + 1
    for k, n in sorted(counts.items()):
        print(*k, n)
    print(mismatched, "verdicts dropped for an image mismatch")
    print(len(merged), "merged;", len(disagree), "B4 disagreements;", len(spot), "spot checks")
    for p in problems:
        print("PROBLEM", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
