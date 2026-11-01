"""#133 accuracy of the VLM methods: the recorded gpt-6-luna answers against the #84 gold, and
claude-opus-5-5 on the same items as a ceiling (user ruling 2026-11-01).

    .venv/bin/python docs/validation/80/t4-accuracy/run.py collect GOLD_ROOT CORPUS_MANIFEST
    env ANTHROPIC_API_KEY=... uv run --with anthropic python docs/validation/80/t4-accuracy/run.py opus
    .venv/bin/python docs/validation/80/t4-accuracy/run.py packet OUT_DIR
    .venv/bin/python docs/validation/80/t4-accuracy/run.py score GOLD_ROOT

GOLD_ROOT is #84's live-preflight folder (kept outside git: it quotes third-party papers). The
real-model runs of t4-seam-b left every document of the 20 public papers in the S3 stand-in;
collect reads the items and Luna's answers from there, so nothing is re-sent to Luna.

  collect  targets.json: the #84 image-gold pictures that are in the corpus (matched to our
           picture-interpretation item by page and box overlap), and a fixed sample of display
           formulas (at most 3 per paper, seed 133), each with Luna's answer
  opus     responses/opus/<item label>.json: the same method request (method.request) sent to
           claude-opus-5-5 through the Messages API, effort max, the method's schema as
           output_config.format; parsed with method.parse
  packet   blind judging sheets in OUT_DIR (outside git): per item the gold obligations or the
           formula crop, and the two answers as A and B in a seeded random order
  score    evidence.json: chart values with #84's frozen comparator (formal = evaluator v2,
           diagnosis = v2 after the round6 axis view), descriptions and formulas from
           judgments.json, next to #84's own Luna and Sol results on the same images
"""

import asyncio
import hashlib
import json
import os
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE.parent / "t4-seam-b"))

TARGETS = HERE / "targets.json"
RESPONSES = HERE / "responses" / "opus"
JUDGMENTS = HERE / "judgments.json"
SEAMB = HERE.parent / "t4-seam-b"
MODEL = "claude-opus-5-5"
FORMULAS_PER_PAPER = 3


def item_label(paper: int, item_id: str) -> str:
    return f"p{paper:02d}-" + hashlib.sha256(item_id.encode()).hexdigest()[:12]


def runs() -> dict[int, tuple[str, str]]:
    """Paper index -> (bucket, request id) of its real-model run in t4-seam-b."""
    evidence = json.loads((SEAMB / "evidence.json").read_text())
    found = {evidence["paper"]["index"]: (f"seamb-{evidence['run']}-t4r", f"req_{evidence['run']}_r")}
    recorded = json.loads((SEAMB / "recorded.json").read_text())
    found |= {int(i): (f"seamb-{p['run']}-p{i}", f"req_{p['run']}_p{i}")
              for i, p in recorded["papers"].items()}  # fmt: skip
    return found


def iou(a: dict, b: dict) -> float:
    l, r = max(a["l"], b["l"]), min(a["r"], b["r"])
    bottom, top = max(a["b"], b["b"]), min(a["t"], b["t"])
    inter = max(0.0, r - l) * max(0.0, top - bottom)
    area = lambda x: (x["r"] - x["l"]) * (x["t"] - x["b"])  # noqa: E731
    return inter / (area(a) + area(b) - inter) if inter else 0.0


async def document(paper: int) -> tuple[object, list[dict], dict[str, dict]]:
    """The store, the inventory items and the enrichments by item_id of one paper's run."""
    import run as seamb

    bucket, request_id = runs()[paper]
    store = seamb.t2.store(bucket)
    result = json.loads(await store.get(f"requests/{request_id}/result.json"))
    items = json.loads(await store.get(result["inventory"]["ref"]))["items"]
    return store, items, {e["item_id"]: e for e in result["enrichments"]}


async def collect(gold_root: Path, manifest: Path) -> None:
    papers = {p["sha256"]: p["index"] for p in json.loads(manifest.read_text())["papers"]}
    gold = json.loads((gold_root / "round2/evaluator/image-gold.json").read_text())["records"]
    crops = {c["index"]: c for c in json.loads(
        (gold_root / "round2/evaluator/crop-source-references.json").read_text())}  # fmt: skip
    targets: list[dict] = []
    for g in gold:
        paper = papers.get(g["source"]["sha256"])
        if paper is None:
            continue  # controls, scans and a personal document: never sent
        _, items, enrichments = await document(paper)
        box = crops[g["index"]]["crop"]["mapping"]["native_bbox"]
        pictures = [i for i in items if i["method"] == "picture-interpretation"
                    and i["page"] == g["physical_page"]]  # fmt: skip
        best = max(pictures, key=lambda i: iou(i["bbox"], box), default=None)
        if best is None or iou(best["bbox"], box) < 0.5:
            targets.append({"kind": "picture", "gold_index": g["index"], "paper": paper,
                            "matched": False})  # fmt: skip
            continue
        luna = {f: enrichments[f"{best['item_id']}/{f}"]["content"]
                for f in ("caption", "description", "figure_type", "chart_values")}  # fmt: skip
        targets.append({"kind": "picture", "gold_index": g["index"], "paper": paper,
                        "matched": True, "overlap": round(iou(best["bbox"], box), 3),
                        "label": item_label(paper, best["item_id"]), "item": best, "luna": luna})  # fmt: skip
    rng = random.Random(133)
    for paper in sorted(runs()):
        _, items, enrichments = await document(paper)
        formulas = [i for i in items if i["method"] == "formula"]
        for item in sorted(rng.sample(formulas, min(FORMULAS_PER_PAPER, len(formulas))),
                           key=lambda i: items.index(i)):  # fmt: skip
            e = enrichments[item["item_id"]]
            targets.append({"kind": "formula", "paper": paper, "label": item_label(paper, item["item_id"]),
                            "item": item, "luna": {"latex": e["content"], "status": e["status"],
                                                   "status_reason": e["status_reason"]}})  # fmt: skip
    TARGETS.write_text(json.dumps(targets, indent=2, ensure_ascii=False) + "\n")
    print(sum(t["kind"] == "picture" and t["matched"] for t in targets), "pictures,",
          sum(t["kind"] == "formula" for t in targets), "formulas,",
          sum(t["kind"] == "picture" and not t["matched"] for t in targets), "unmatched")  # fmt: skip


def anthropic_request(request: dict) -> dict:
    """The method's chat-completions request as Messages API parameters."""
    system = "\n".join(m["content"] for m in request["messages"] if m["role"] == "system")
    content = []
    for message in request["messages"]:
        if message["role"] != "user":
            continue
        parts = message["content"]
        for part in [{"type": "text", "text": parts}] if isinstance(parts, str) else parts:
            if part["type"] == "text":
                content.append({"type": "text", "text": part["text"]})
            else:
                header, data = part["image_url"]["url"].split(",", 1)
                media = header.removeprefix("data:").removesuffix(";base64")
                content.append({"type": "image",
                                "source": {"type": "base64", "media_type": media, "data": data}})  # fmt: skip
    schema = request["response_format"]["json_schema"]["schema"]
    return {"system": system, "messages": [{"role": "user", "content": content}],
            "output_config": {"effort": "max", "format": {"type": "json_schema", "schema": schema}}}  # fmt: skip


async def opus() -> None:
    import anthropic

    from kp_processing.methods import InvalidOutput
    from kp_processing.profile import load_profile

    profile = load_profile(REPO / "tests/profiles/paper-pdf-dev.yaml")
    client = anthropic.AsyncAnthropic()
    RESPONSES.mkdir(parents=True, exist_ok=True)
    targets = [t for t in json.loads(TARGETS.read_text()) if t.get("matched", True)]
    stores: dict[int, object] = {}
    limit = asyncio.Semaphore(4)

    async def one(t: dict) -> None:
        path = RESPONSES / f"{t['label']}.json"
        if path.exists():
            return
        if t["paper"] not in stores:
            stores[t["paper"]] = (await document(t["paper"]))[0]
        store, item = stores[t["paper"]], t["item"]
        package = profile.methods[item["method"]].package
        inputs = [await store.get(source["ref"]) for source in item["input_refs"]]
        request = package.request(item, inputs)
        async with limit, client.messages.stream(model=MODEL, max_tokens=64000,
                                                 **anthropic_request(request)) as stream:  # fmt: skip
            response = await stream.get_final_message()
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            output = package.parse(item, inputs, text)
            parsed = {"outcome": output.outcome, "content": output.content,
                      "contradictions": output.contradictions,
                      "fields": {k: [v.outcome, v.reason] for k, v in output.fields.items()}}  # fmt: skip
        except InvalidOutput as exc:
            parsed = {"outcome": "invalid", "reason": exc.reason}
        path.write_text(json.dumps({"label": t["label"], "model": response.model,
                                    "stop_reason": response.stop_reason,
                                    "usage": response.usage.to_dict(), "text": text,
                                    "parsed": parsed}, indent=2, ensure_ascii=False) + "\n")  # fmt: skip
        print(t["label"], response.stop_reason, parsed["outcome"], flush=True)

    await asyncio.gather(*(one(t) for t in targets))


def answers(t: dict) -> dict[str, dict]:
    """Luna's and Opus's answers for one target, as the judge compares them."""
    opus_answer = json.loads((RESPONSES / f"{t['label']}.json").read_text())["parsed"]
    if t["kind"] == "formula":
        return {"luna": {"latex": t["luna"]["latex"]},
                "opus": {"latex": opus_answer.get("content")}}  # fmt: skip
    content = opus_answer.get("content") or {}
    return {"luna": {"description": t["luna"]["description"], "figure_type": t["luna"]["figure_type"]},
            "opus": {"description": content.get("description"),
                     "figure_type": content.get("figure_type")}}  # fmt: skip


async def packet(out: Path) -> None:
    """Blind sheets: A/B order seeded per item; the key to unblind stays next to the sheets."""
    from kp_processing.methods.formula import _crop

    out.mkdir(parents=True, exist_ok=True)
    gold_root = Path(os.environ["GOLD_ROOT"])
    gold = {g["index"]: g for g in json.loads(
        (gold_root / "round2/evaluator/image-gold.json").read_text())["records"]}  # fmt: skip
    sheets, key = [], {}
    for t in json.loads(TARGETS.read_text()):
        if not t.get("matched", True):
            continue
        pair = answers(t)
        order = ["luna", "opus"]
        random.Random(t["label"]).shuffle(order)
        key[t["label"]] = {"A": order[0], "B": order[1]}
        sheet = {"label": t["label"], "kind": t["kind"], "A": pair[order[0]], "B": pair[order[1]]}
        if t["kind"] == "picture":
            sheet["obligations"] = gold[t["gold_index"]]["description_obligations"]
            sheet["gold_index"] = t["gold_index"]
        else:
            store = (await document(t["paper"]))[0]
            inputs = [await store.get(s["ref"]) for s in t["item"]["input_refs"]]
            (out / f"{t['label']}.png").write_bytes(_crop(t["item"], inputs))
            sheet["crop"] = f"{t['label']}.png"
        sheets.append(sheet)
    (out / "sheets.json").write_text(json.dumps(sheets, indent=2, ensure_ascii=False) + "\n")
    (out / "key.json").write_text(json.dumps(key, indent=2) + "\n")
    print(len(sheets), "sheets in", out)


def axis_view(chart: dict, index: int) -> dict:
    """round6-sol/binding_diagnostic.py axis_view, copied: maps schema-permitted axis labels
    without looking at values or answers; plus a trailing parenthetical dropped from series."""
    result = json.loads(json.dumps(chart))
    for point in result["data"]:
        if index == 6 and point.get("category") is None and isinstance(point.get("x"), str):
            point["category"] = point["x"]
        if index == 16 and isinstance(point.get("category"), str) and isinstance(point.get("x"), str) \
                and not point["category"].endswith(point["x"]):  # fmt: skip
            point["category"] = point["category"] + " " + point["x"]
        # added here: v2 strips only #84 Luna's "(cumulative boundary)"; drop any trailing note
        if isinstance(point.get("series"), str):
            point["series"] = re.sub(r"\s*\([^)]*\)\s*$", "", point["series"])
        if index == 26 and point.get("category") is None and point.get("x") is None \
                and isinstance(point.get("series"), str):  # fmt: skip
            point["category"] = point["series"]
    return result


def score(gold_root: Path) -> None:
    sys.path[:0] = [str(gold_root / "round5-strict"), str(gold_root / "round3-luna"), str(gold_root)]
    import evaluate_v2 as v2

    golds = {g["index"]: g for g in json.loads(
        (gold_root / "round2/evaluator/image-gold.json").read_text())["records"]}  # fmt: skip
    prior = {
        model: {r["index"]: r for r in json.loads(
            (gold_root / folder / "evaluation-v2.json").read_text())["C_images"]}
        for model, folder in (("luna_84", "round5-strict"), ("sol_84", "round6-sol"))
    }  # fmt: skip
    # #84 re-scored Sol's label-binding misses with the axis view; Luna's needed none
    sol_axis = {
        r["index"]: sum(x["state"] == "PASS" for x in r["axis_binding_diagnostic"])
        for r in json.loads((gold_root / "round6-sol/binding-diagnostic.json").read_text())["rows"]
    }  # fmt: skip
    reviewed = {i["image_index"]: i["description_state"] for i in json.loads(
        (gold_root / "round5-strict/human-C-review-v1.json").read_text())["images"]}  # fmt: skip
    judgments = json.loads(JUDGMENTS.read_text()) if JUDGMENTS.exists() else {}
    targets = json.loads(TARGETS.read_text())
    charts, descriptions, formulas = [], [], []

    def numeric(chart_values, index: int, diagnosis: bool) -> list[str]:
        chart = {"data": chart_values}
        if diagnosis:
            chart = axis_view(chart, index)
        chart, _ = v2.comparison_view(chart, index == 16)
        return [r["state"] for r in v2.e.chart_receipts(golds[index], chart)]

    for t in targets:
        if t["kind"] == "picture" and t["matched"]:
            index = t["gold_index"]
            opus_answer = json.loads((RESPONSES / f"{t['label']}.json").read_text())["parsed"]
            opus_values = (opus_answer.get("content") or {}).get("chart_values") or []
            if golds[index].get("numeric_points"):
                row = {"gold_index": index, "points": golds[index]["numeric_points"]}
                for model, values in (("luna", t["luna"]["chart_values"]), ("opus", opus_values)):
                    for view in ("formal", "diagnosis"):
                        states = numeric(values, index, view == "diagnosis")
                        row[f"{model}_{view}"] = states.count("PASS")
                for model in ("luna_84", "sol_84"):
                    receipts = prior[model].get(index, {}).get("numeric_receipts") or []
                    row[f"{model}_formal"] = sum(r["state"] == "PASS" for r in receipts)
                    row[f"{model}_diagnosis"] = row[f"{model}_formal"]
                if index in sol_axis:
                    row["sol_84_diagnosis"] = sol_axis[index]
                charts.append(row)
            verdict = judgments.get(t["label"], {})
            descriptions.append({"gold_index": index, "label": t["label"],
                                 "luna": verdict.get("luna"), "opus": verdict.get("opus"),
                                 "luna_84": reviewed.get(index),
                                 "note": verdict.get("note")})  # fmt: skip
        elif t["kind"] == "formula":
            verdict = judgments.get(t["label"], {})
            formulas.append({"label": t["label"], "paper": t["paper"],
                             "luna_status": t["luna"]["status"], "luna": verdict.get("luna"),
                             "opus": verdict.get("opus"), "note": verdict.get("note")})  # fmt: skip
    passes = lambda rows, model: sum(r[model] in ("PASS", "PASS_MEANING_SLICE") for r in rows)  # noqa: E731
    wrong = [f for f in formulas if f["luna"] == "FAIL"]
    flagged = [f for f in formulas if f["luna_status"] == "disputed"]
    summary = {
        "charts": {k: sum(c[k] for c in charts) for k in charts[0] if k != "gold_index"},
        "descriptions": {m: passes(descriptions, m) for m in ("luna", "opus", "luna_84")},
        "formulas": {m: passes(formulas, m) for m in ("luna", "opus")},
        "disputed": {"flagged": len(flagged), "luna_wrong": len(wrong),
                     "flagged_and_wrong": sum(f in wrong for f in flagged)},
    }  # fmt: skip
    evidence = {"model": MODEL, "summary": summary, "charts": charts, "descriptions": descriptions,
                "formulas": formulas,
                "unmatched_gold": [t["gold_index"] for t in targets
                                   if t["kind"] == "picture" and not t["matched"]]}  # fmt: skip
    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    if command == "collect":
        asyncio.run(collect(Path(args[0]), Path(args[1])))
    elif command == "opus":
        asyncio.run(opus())
    elif command == "packet":
        asyncio.run(packet(Path(args[0])))
    elif command == "score":
        score(Path(args[0]))
