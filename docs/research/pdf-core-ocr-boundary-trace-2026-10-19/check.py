"""Replay the real page-assembly seam; this is one-case paragraph integrity, not accuracy."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "pdf-core-native-round-2026-10-17"
SOURCE_PHRASE = "review articles on PLMs or LLMs"


def inspect(result):
    from docling.models.stages.page_assemble.page_assemble_model import PageAssembleModel
    page = result["pages"][0]
    elements = page["assembled"]["elements"]
    element = next(e for e in elements if "We are also aware" in e.get("text", ""))
    cluster = next(c for c in page["predictions"]["layout"]["clusters"] if c["id"] == element["id"])
    lines = [c["text"].replace("\x02", "-").strip() for c in cluster["cells"] if c["text"].strip()]
    replay = PageAssembleModel.sanitize_text(None, lines.copy())
    assert replay == element["text"], "capture does not replay actual assembly"
    return {"paragraph_integrity_pass": SOURCE_PHRASE in " ".join(replay.split()),
            "foror_present": "foror" in replay,
            "mixed_left_right_cells": [c["index"] for c in page["parsed_page"]["textline_cells"]
                if "or LLMs" in c["text"] and "introduced by" in c["text"]],
            "cluster_id": cluster["id"], "replayed_actual_assembly": True,
            "scope": "one fixed source paragraph only; not full reading-order qualification"}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("result", nargs="?", type=Path, default=OLD / "S0/scan/result.json")
    args = p.parse_args()
    verdict = inspect(json.loads(args.result.read_text()))
    print(json.dumps(verdict, ensure_ascii=False))
    raise SystemExit(0 if verdict["paragraph_integrity_pass"] else 1)
