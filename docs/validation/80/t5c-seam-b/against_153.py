"""#161 against #153's frozen inputs and scores (d3-mini): the d3-check package builds the
requests #153 measured, and the DEV stand-in scores them as #153's run_d3.py did.

    .venv/bin/python docs/validation/80/t5c-seam-b/against_153.py R153_DIR \
        [D3_BASE_URL [KEY [NAME]]]

R153_DIR is #153's untracked output folder (third-party crops, outside git): model-inputs.json,
inputs/ (the original images, named by sha256) and rows/d3-mini-test.jsonl. questions.json is
read from the tag research/153-d3-quality-check.

Requests (no service). For every formula and ocr item of model-inputs.json, dev and test, the
package's request for the original image and the item's reconstruction is compared with what
#153 sent: the state, the Q2 question, and the sha256 of the image as sent against the image
#153 supplied. A table's text comes from the assembly, so tables are compared in run.py only.
None of those images is over 1.6 MP, so every image #153 downsized, of any category, is also
sent through the package (as a picture's) and its hash compared with #153's downsized image.

Scores (with D3_BASE_URL, the server root of `d3_server.py --device mps --batch-size 1`). Every
formula and ocr test item goes through SystemOne and the package's parse; its score is compared
with #153's (rows/d3-mini-test.jsonl), and so is the judgement each score gives.

With NAME, the service is not #153's own setup (vLLM Semantic Router on CPU, say): only the
lowest- and highest-scored test item of each category is sent, as #153's contract_smoke.py
picked them, and the scores need not equal #153's; the judgements must.

Writes evidence-153.json (evidence-NAME.json with NAME) next to this file: counts, timings, item
ids and scores only.
"""

import asyncio
import base64
import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx

from kp_processing.identity import canonical_json
from kp_processing.methods import InventoryItem, d3_check
from kp_processing.ports.inference import SystemOne

HERE = Path(__file__).resolve().parent
TAG = "refs/tags/research/153-d3-quality-check:docs/research/d3-quality-check-2026-11-02"
JUDGED = {"formula": "formula@1", "ocr": "picture-ocr@1"}  # #153's category: the judged method


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def item(row: dict) -> InventoryItem:
    return {"item_id": f"d3-check:{row['id']}", "method": "d3-check", "target_ref": "#",
            "page": 0, "bbox": {}, "input_refs": []}  # fmt: skip


def inputs(root: Path, row: dict) -> list[bytes]:
    """A check item's inputs for a #153 item: its original image and a judged outcome record."""
    (image,) = row["images"]
    original = (root / "inputs" / f"{image['original_sha256']}.png").read_bytes()
    assert sha(original) == image["original_sha256"], row["id"]
    method_id, version = JUDGED[row["category"]].split("@")
    record = {"method_ref": {"id": method_id, "version": int(version)}, "outcome": "success",
              "content": row["state"]["reconstruction"]}  # fmt: skip
    return [original, canonical_json(record)]


def flagged(row: dict, score: float) -> bool:
    """Whether the package's parse turns the score into a contradiction."""
    reply = json.dumps({"answers": {d3_check.QUESTION: {"type": "noul", "noul": score}}})
    return bool(d3_check.parse(item(row), [b"", canonical_json(
        {"method_ref": {"id": JUDGED[row["category"]].split("@")[0], "version": 1}}
    )], reply).contradictions)  # fmt: skip


async def main(argv: list[str]) -> int:
    root, name = Path(argv[0]), argv[3] if len(argv) > 3 else None
    shown = subprocess.run(["git", "show", f"{TAG}/questions.json"], capture_output=True,
                           check=True, cwd=HERE)  # fmt: skip
    questions = json.loads(shown.stdout)
    every = json.loads((root / "model-inputs.json").read_text())["items"]
    rows = [r for r in every if r["category"] in JUDGED]
    requests: dict[str, dict] = {}
    compared: dict[str, dict[str, int]] = {}
    differing = []
    for row in rows:
        (image,) = row["images"]
        request = requests[row["id"]] = d3_check.request(item(row), inputs(root, row))
        sent = base64.b64decode(request["images"][0].split(",", 1)[1])
        same = {
            "state": request["state"] == row["state"],
            "question": request["questions"] == {"Q2": questions[row["category"]]["Q2"]},
            "image": sha(sent) == image["sha256"],
        }
        counts = compared.setdefault(f"{row['category']} {row['split']}", {
            "items": 0, "state": 0, "question": 0, "image": 0, "downsized": 0})  # fmt: skip
        counts["items"] += 1
        counts["downsized"] += image["sha256"] != image["original_sha256"]
        for field, equal in same.items():
            counts[field] += equal
        if not all(same.values()):
            differing.append({"id": row["id"], **same})
    large = {i["original_sha256"]: i["sha256"] for r in every for i in r["images"]
             if i["sha256"] != i["original_sha256"]}  # fmt: skip
    downsized = {"images": len(large), "equal": 0}
    for original, supplied in large.items():
        row = {"id": original, "category": "ocr", "state": {"reconstruction": ""},
               "images": [{"original_sha256": original}]}  # fmt: skip
        (url,) = d3_check.request(item(row), inputs(root, row))["images"]
        equal = sha(base64.b64decode(url.split(",", 1)[1])) == supplied
        downsized["equal"] += equal
        if not equal:
            differing.append({"id": original, "image": False})
    evidence: dict = {"requests": dict(sorted(compared.items())), "downsized": downsized,
                      "requests_differing": differing}  # fmt: skip
    print(json.dumps(evidence["requests"]), downsized, "differing:", len(differing), flush=True)

    if len(argv) > 1:
        lines = (root / "rows/d3-mini-test.jsonl").read_text().splitlines()
        want = {r["id"]: r["score"] for r in map(json.loads, lines)}
        scores: dict = {}
        seconds = []
        tests = [r for r in rows if r["split"] == "test"]
        if name:
            by_score = sorted(tests, key=lambda r: want[r["id"]])
            ends = [[r for r in by_score if r["category"] == c] for c in JUDGED]
            tests = [r for of_category in ends for r in (of_category[0], of_category[-1])]
        async with httpx.AsyncClient() as http:
            d3 = SystemOne(http, argv[1], argv[2] if len(argv) > 2 else "", 5, 120)
            for row in tests:
                begin = time.monotonic()
                answer = await d3.complete(requests[row["id"]])
                seconds.append(time.monotonic() - begin)
                output = d3_check.parse(item(row), inputs(root, row), answer.content)
                score, was = output.signals["d3"]["score"], want[row["id"]]
                s = scores.setdefault(row["category"], {
                    "items": 0, "equal": 0, "max_abs_diff": 0.0, "flagged": 0, "flagged_153": 0,
                    "judgements_differ": []})  # fmt: skip
                s["items"] += 1
                s["equal"] += score == was
                s["max_abs_diff"] = max(s["max_abs_diff"], abs(score - was))
                s["flagged"] += bool(output.contradictions)
                s["flagged_153"] += flagged(row, was)
                if bool(output.contradictions) != flagged(row, was):
                    s["judgements_differ"].append(row["id"])
                answered = json.loads(answer.content)
                s["model"], s["usage_keys"] = answered["model"], sorted(answered["usage"])
                if name:
                    s.setdefault("sent", []).append(
                        {"id": row["id"], "score": score, "score_153": was,
                         "seconds": round(seconds[-1], 2), "reply_keys": sorted(answered)}
                    )  # fmt: skip
        evidence["scores"] = scores
        evidence["seconds"] = {"min": round(min(seconds), 2),
                               "median": round(statistics.median(seconds), 2),
                               "max": round(max(seconds), 2)}  # fmt: skip
        print(json.dumps({"scores": scores, "seconds": evidence["seconds"]}, indent=1), flush=True)
    (HERE / f"evidence-{name or '153'}.json").write_text(json.dumps(evidence, indent=2) + "\n")
    ok = not differing and all(
        (name or s["equal"] == s["items"]) and not s["judgements_differ"]
        for s in evidence.get("scores", {}).values()
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
