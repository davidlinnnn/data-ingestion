"""#153: the d3 model inputs, prepared once before any d3 output exists.

    python3 docs/research/d3-quality-check-2026-11-02/prepare_inputs.py OUT

Joins labels.jsonl to items.jsonl; downsizes every image to at most 1.6 MP (LANCZOS, as W4b
did; the official processor reads up to 1.6 MP) into OUT/inputs-1.6mp/; writes
OUT/model-inputs.json (state = category name and reconstruction only, no gold, id or locator)
and OUT/test-counts.json (meaning_changed per category in test, for score.py select).
"""

import hashlib
import json
import math
import sys
from pathlib import Path

from PIL import Image

MODELS = ("d3-nano", "d3-mini", "d3-flash")
# What the question calls the reconstruction; W4b's names are kept for its categories.
STATE_NAME = {
    "formula": "formula LaTeX",
    "description": "generated image description",
    "chart": "reconstructed chart data point",
    "ocr": "recognised text",
    "caption": "generated caption",
    "table": "table grid (Markdown)",
    "figure_type": "figure type",
}
# Images each category sends, in order; page context only where the method itself sends the page.
IMAGE_ROLES = {
    "formula": ("crop",),
    "chart": ("crop",),
    "ocr": ("crop",),
    "table": ("crop",),
    "description": ("page", "crop"),
    "caption": ("page", "crop"),
    "figure_type": ("page", "crop"),
}
MAX_PIXELS = 1_600_000


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(out: Path) -> int:
    labels = [json.loads(line) for line in (out / "labels.jsonl").read_text().splitlines()]
    items = {r["id"]: r for r in map(json.loads, (out / "items.jsonl").read_text().splitlines())}
    folder = out / "inputs-1.6mp"
    folder.mkdir(exist_ok=True)
    supplied, inputs = {}, []
    for row in labels:
        item = items[row["id"]]
        by_role = {i["role"]: i["sha256"] for i in item["images"]}
        images = []
        for role in IMAGE_ROLES[row["category"]]:
            key = by_role[role]
            if key not in supplied:
                source = out / "inputs" / f"{key}.png"
                image = Image.open(source).convert("RGB")
                before = image.size
                scale = min(1, math.sqrt(MAX_PIXELS / (before[0] * before[1])))
                target = folder / f"{key}.png"
                if scale < 1:
                    image = image.resize(
                        (max(1, int(before[0] * scale)), max(1, int(before[1] * scale))),
                        Image.Resampling.LANCZOS,
                    )
                    image.save(target)
                else:
                    target.write_bytes(source.read_bytes())
                assert image.size[0] * image.size[1] <= MAX_PIXELS
                supplied[key] = {
                    "path": str(target.relative_to(out)),
                    "sha256": sha(target),
                    "original_sha256": key,
                    "original_size": list(before),
                    "supplied_size": list(image.size),
                }
            images.append({"role": role, **supplied[key]})
        inputs.append(
            {
                "id": row["id"],
                "category": row["category"],
                "split": row["split"],
                "group": row["group"],
                "state": {
                    "category": STATE_NAME[row["category"]],
                    "reconstruction": item["reconstruction"],
                },
                "images": images,
            }
        )
    (out / "model-inputs.json").write_text(
        json.dumps({"items": inputs}, ensure_ascii=False, indent=1) + "\n"
    )
    counts = {}
    for row in labels:
        if row["split"] == "test" and row["label"] == "meaning_changed":
            counts[row["category"]] = counts.get(row["category"], 0) + 1
    for row in labels:
        counts.setdefault(row["category"], 0)
    (out / "test-counts.json").write_text(
        json.dumps({m: counts for m in MODELS}, indent=1, sort_keys=True) + "\n"
    )
    print(
        len(inputs),
        "inputs;",
        len(supplied),
        "images;",
        sum(v["supplied_size"] != v["original_size"] for v in supplied.values()),
        "downsized; test changed",
        counts,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
