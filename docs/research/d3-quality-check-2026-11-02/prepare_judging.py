"""#153 B1/B4: fold the round-1-prompt Luna answers into items.jsonl and write the blind
judging packets.

    env AWS_ACCESS_KEY_ID=kpdev AWS_SECRET_ACCESS_KEY=kpdev-secret HF_HUB_OFFLINE=1 \
        .venv/bin/python docs/research/d3-quality-check-2026-11-02/prepare_judging.py OUT MANIFEST

OUT is the research folder outside git (items.jsonl, inputs/, luna-r1prompt/); MANIFEST is the
corpus manifest. Items: adds caption, description and figure_type rows for every
luna-r1prompt answer (judge_needed B1); sends the 18 unjudged #152 fixtures to B1 too; drops
the two fixtures whose real run timed out (their late responses never reach a consumer).
Packets: one task per picture (its B1 answers as A/B in seeded random order, producers hidden)
and one per B4 item, never with an old label; the answer-to-item key goes to judging/key.json,
which judges never see.
"""

import asyncio
import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
T4 = REPO / "docs/validation/80/t4-accuracy"
sys.path.insert(0, str(REPO / "docs/validation/80/t4-seam-b"))
TIMED_OUT = {"0902c38ed30a7f66", "a9764dfb78442403"}
PICTURE_FIELDS = ("caption", "description", "figure_type")
BATCH = 24
SEED = 153


def load_t4():
    spec = importlib.util.spec_from_file_location("t4acc", T4 / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def r1prompt_rows(out: Path, manifest: Path) -> list[dict]:
    t4 = load_t4()
    papers = {p["index"]: p for p in json.loads(manifest.read_text())["papers"]}
    rows = []
    for path in sorted((out / "luna-r1prompt").glob("*.json")):
        answer = json.loads(path.read_text())
        fields = json.loads(answer["text"])
        store, items, _ = await t4.document(answer["paper"])
        item = next(i for i in items if i["item_id"] == answer["item_id"])
        images = []
        for role, source in zip(
            ("crop", "page"), item["input_refs"], strict=True
        ):  # INPUTS = (picture_image, page_image)
            data = await store.get(source["ref"])
            target = out / "inputs" / f"{sha(data)}.png"
            if not target.exists():
                target.write_bytes(data)
            images.append({"role": role, "sha256": sha(data)})
        paper = papers[answer["paper"]]
        for field in PICTURE_FIELDS:
            rows.append(
                {
                    "id": f"r1prompt/{field}/{answer['label']}",
                    "category": field,
                    "producer": "luna-r1prompt",
                    "source_page": {
                        "paper": paper["sha256"],
                        "page": item["page"],
                        "name": Path(paper["file"]).name,
                    },
                    "reconstruction": fields.get(field) or "",
                    "images": images,
                    "old_label": "UNKNOWN",
                    "old_label_source": f"luna-r1prompt/{path.name}",
                    "judge_needed": "B1",
                }
            )
    return rows


def packets(rows: list[dict], out: Path) -> None:
    rng = random.Random(SEED)
    pictures: dict[str, list[dict]] = {}
    tasks, key = [], {}
    for row in rows:
        if row["judge_needed"] == "B1":
            crop = next(i["sha256"] for i in row["images"] if i["role"] == "crop")
            pictures.setdefault(crop, []).append(row)
        elif row["judge_needed"] == "B4":
            task = f"b4-{len(tasks):04d}"
            tasks.append(
                {
                    "task": task,
                    "category": row["category"],
                    "images": row["images"],
                    "answers": [{"key": "A", "text": row["reconstruction"]}],
                }
            )
            key[task] = {"A": [row["id"]]}
    for crop, group in pictures.items():
        task = f"b1-{len(tasks):04d}"
        by_producer: dict[str, dict[str, dict]] = {}
        for row in group:
            fields = by_producer.setdefault(row["producer"], {})
            assert row["category"] not in fields, f"two {row['producer']} answers share crop {crop}"
            fields[row["category"]] = row
        order = sorted(by_producer)
        rng.shuffle(order)
        answers, key[task] = [], {}
        for letter, producer in zip("AB", order, strict=False):
            fields = by_producer[producer]
            answers.append({"key": letter, **{f: fields[f]["reconstruction"] for f in fields}})
            key[task][letter] = [fields[f]["id"] for f in fields]
        tasks.append(
            {"task": task, "category": "picture", "images": group[0]["images"], "answers": answers}
        )
    rng.shuffle(tasks)
    folder = out / "judging"
    folder.mkdir(exist_ok=True)
    for n in range(0, len(tasks), BATCH):
        batch = [
            {
                **t,
                "images": [
                    {"role": i["role"], "path": str(out / "inputs" / f"{i['sha256']}.png")}
                    for i in t["images"]
                ],
            }
            for t in tasks[n : n + BATCH]
        ]
        (folder / f"batch-{n // BATCH:02d}.json").write_text(
            json.dumps(batch, indent=1, ensure_ascii=False)
        )
    (folder / "key.json").write_text(json.dumps(key, indent=1, sort_keys=True))
    print(len(tasks), "tasks in", -(-len(tasks) // BATCH), "batches")


async def main(out: Path, manifest: Path) -> int:
    rows = [json.loads(line) for line in (out / "items.jsonl").read_text().splitlines()]
    assert not any(r["producer"] == "luna-r1prompt" for r in rows), "already folded in"
    kept = []
    for row in rows:
        if row["id"].startswith("fixture/") and row["id"].rsplit("/", 1)[1] in TIMED_OUT:
            continue
        if row["id"].startswith("fixture/") and row["judge_needed"] == "none":
            row["judge_needed"] = "B1"
        kept.append(row)
    kept += await r1prompt_rows(out, manifest)
    assert len({r["id"] for r in kept}) == len(kept), "duplicate item ids"
    (out / "items.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept)
    )
    print(len(rows), "->", len(kept), "items; items.jsonl", sha((out / "items.jsonl").read_bytes()))
    packets(kept, out)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2]))))
