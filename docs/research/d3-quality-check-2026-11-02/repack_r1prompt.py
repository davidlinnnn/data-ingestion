"""#153 B1: judge again every round-1-prompt picture whose first packet showed the wrong images.

    python3 docs/research/d3-quality-check-2026-11-02/repack_r1prompt.py OUT

The first packets grouped round-1-prompt answers by an image that was really the page, so
pictures sharing a page collapsed into one task: the task showed the first picture's images
with the last picture's answer, and the other answers were never sent. This writes one task
per affected picture (images taken from the item itself) as batches 24 onward and adds them
to judging/key.json. merge_verdicts.py drops the old tasks by their image mismatch.
"""

import json
import random
import sys
from pathlib import Path

BATCH = 24
SEED = 153
FIELDS = ("caption", "description", "figure_type")


def main(out: Path) -> int:
    folder = out / "judging"
    rows = {r["id"]: r for r in map(json.loads, (out / "items.jsonl").read_text().splitlines())}
    key = json.loads((folder / "key.json").read_text())
    shown = {}
    for path in sorted(folder.glob("batch-*.json")):
        for task in json.loads(path.read_text()):
            shown[task["task"]] = {Path(i["path"]).stem for i in task["images"]}
    sound = {
        i
        for task, answers in key.items()
        for ids in answers.values()
        for i in ids
        if {x["sha256"] for x in rows[i]["images"]} == shown.get(task)
    }
    labels = sorted(
        {
            i.rsplit("/", 1)[1]
            for i, r in rows.items()
            if r["producer"] == "luna-r1prompt" and i not in sound
        }
    )
    first = max(int(t.split("-")[1]) for t in key) + 1
    rng = random.Random(SEED)
    rng.shuffle(labels)
    tasks = []
    for n, label in enumerate(labels):
        ids = [f"r1prompt/{f}/{label}" for f in FIELDS]
        task = f"b1-{first + n:04d}"
        key[task] = {"A": ids}
        tasks.append(
            {
                "task": task,
                "category": "picture",
                "images": [
                    {"role": i["role"], "path": str(out / "inputs" / f"{i['sha256']}.png")}
                    for i in rows[ids[0]]["images"]
                ],
                "answers": [
                    {
                        "key": "A",
                        **{f: rows[i]["reconstruction"] for f, i in zip(FIELDS, ids, strict=True)},
                    }
                ],
            }
        )
    start = 1 + max(int(p.stem.split("-")[1]) for p in folder.glob("batch-*.json"))
    for n in range(0, len(tasks), BATCH):
        path = folder / f"batch-{start + n // BATCH:02d}.json"
        assert not path.exists(), path
        path.write_text(json.dumps(tasks[n : n + BATCH], indent=1, ensure_ascii=False))
    (folder / "key.json").write_text(json.dumps(key, indent=1, sort_keys=True))
    print(len(tasks), "tasks in batches", start, "to", start + (len(tasks) - 1) // BATCH)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
