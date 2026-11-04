"""Contract smoke: send a few #153 d3-mini test requests to a /v1/systemone server and compare
the noul score with the #153 in-process (MPS) result.

    python3 contract_smoke.py OUT URL N_PER_CATEGORY QUESTIONS_JSON > result.json
"""

import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

out, url = Path(sys.argv[1]), sys.argv[2].rstrip("/")
n = int(sys.argv[3])
questions = json.loads(Path(sys.argv[4]).read_text())
selection = json.loads((out / "selection" / "d3-mini.json").read_text())["models"]["d3-mini"]
inputs = {r["id"]: r for r in json.loads((out / "model-inputs.json").read_text())["items"]}
rows = [json.loads(line) for line in (out / "rows" / "d3-mini-test.jsonl").read_text().splitlines()]
results = {}
for p in (out / "runs" / "d3-mini" / "test").glob("*.result.json"):
    r = json.loads(p.read_text())
    results[r["id"]] = r

picked = []
for category in ("formula", "table", "ocr"):
    rs = sorted((r for r in rows if r["category"] == category and not r["failed"]), key=lambda r: r["score"])
    # lowest and highest scores, so both sides of the threshold are exercised
    picked += rs[: n // 2 or 1] + rs[-(n - n // 2) :]

report = []
for r in picked:
    item = inputs[r["id"]]
    question = selection[r["category"]]["question"]
    body = {
        "model": "vllm-sr/d3-mini",
        "state": item["state"],
        "images": [
            "data:image/png;base64," + base64.b64encode((out / im["path"]).read_bytes()).decode()
            for im in item["images"]
        ],
        "questions": {question: questions[r["category"]][question]},
    }
    req = urllib.request.Request(
        url + "/v1/systemone",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )
    t = time.monotonic()
    with urllib.request.urlopen(req, timeout=600) as resp:
        reply = json.loads(resp.read())
    seconds = time.monotonic() - t
    answer = reply["answers"][question]
    score = answer["noul"]
    reference = results[r["id"]]["safe_scores"][question]
    report.append(
        {
            "id": r["id"],
            "category": r["category"],
            "label": r["label"],
            "question": question,
            "answer_keys": sorted(answer),
            "score_vllm_sr": score,
            "score_153_mps": reference,
            "abs_diff": abs(score - reference),
            "seconds": round(seconds, 2),
            "usage": reply.get("usage"),
            "reply_keys": sorted(reply),
        }
    )
    print(r["id"], round(score, 4), round(reference, 4), f"{seconds:.1f}s", file=sys.stderr)
json.dump(report, sys.stdout, indent=1)
