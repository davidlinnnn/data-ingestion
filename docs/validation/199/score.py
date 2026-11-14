"""#199 accuracy: the enrichments the workflow registered, scored with the gold and the scorers of
t3-accuracy, t4-accuracy and t5b-accuracy, beside the scores of the methods run alone. run.py
calls accuracy() with the S3 stand-in up; no paper text leaves OUT.

  picture-ocr, table-status  t3's score_ocr and score_tables, unchanged, on the workflow's items,
           outcome records and OCR lines, each unit or table beside t3's row
  code     each #84 code unit: the workflow's code items that overlap the unit's region on its
           pages, joined in inventory order, against the unit's source text with #84's
           metrics.compare. t3 ran the method on the unit's fixed region instead
  pictures t4's gold pictures matched to a picture-interpretation item as t4 matched them (page,
           box overlap >= 0.5): chart values with t4's comparator in both views; a description
           equal to t4's recorded one keeps t4's verdict, any other is judged blind
  formulas t4's 46 sampled formulas, by item_id: a LaTeX equal to t4's recorded one (whitespace
           aside) keeps t4's verdict, any other is judged blind
  Every scored VLM item says whether its request body is one the method-alone runs sent
  (recorded): the same request with another answer is the model's run-to-run variation.

Blind judging: OUT/judging/sheets.json holds each pending item with the recorded and the
workflow answer as A and B in a seeded order (key.json beside it), with the gold obligations or
the formula crop; the judge writes OUT/judging/verdicts.json, {label: {"A", "B", "note"}}, by
t4-accuracy's rules. accuracy() unblinds it into judgments.json here.

    set -a; . ~/.config/kp-dev/anthropic.env; . ~/.config/kp-dev/openai.env; set +a
    .venv/bin/python docs/validation/199/score.py summary OUT SET_NAME N INDEX...

runs t5b-accuracy's planted-error check unchanged on OUT/summaries (written by run.py); it writes
evidence-SET_NAME.json here.
"""

import asyncio
import hashlib
import importlib.util
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V80 = HERE.parent / "80"
REPO = HERE.parents[2]
FIXTURES = REPO / "tests/fixtures/vlm"
JUDGMENTS = HERE / "judgments.json"
PASSES = ("PASS", "PASS_MEANING_SLICE")


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


t3 = load("t3_accuracy", V80 / "t3-accuracy/run.py")
t4 = load("t4_accuracy", V80 / "t4-accuracy/run.py")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def recorded(receipt: dict) -> bool:
    """Whether the method-alone runs (t4-seam-b, #152) sent this very request body."""
    method = receipt["method"].rpartition("@")[0]
    return (FIXTURES / method / f"{receipt['params_digest']}.json").exists()


async def outputs(store, request_id: str) -> dict:
    """One request's result, inventory items, enrichments by item_id, the outcome records of the
    local methods, picture-ocr's OCR lines, and per VLM item whether its last request was
    recorded."""
    result = json.loads(await store.get(f"requests/{request_id}/result.json"))
    items = json.loads(await store.get(result["inventory"]["ref"]))["items"]
    records, provider = {}, {}
    for e in result["enrichments"]:
        if e["method_ref"]["id"] in ("picture-ocr", "table-status", "code"):
            record = records[e["item_id"]] = json.loads(await store.get(e["result_ref"]))
            if e["method_ref"]["id"] == "picture-ocr" and record["provider_artifact_ref"]:
                provider[e["item_id"]] = json.loads(await store.get(record["provider_artifact_ref"]))
    keys = sorted(k for k in await store.list_prefix(f"requests/{request_id}/attempts/")
                  if "/receipts/" in k)  # fmt: skip
    last = {}
    for key in keys:
        receipt = json.loads(await store.get(key))
        last[receipt["item_id"]] = receipt
    return {"result": result, "items": items, "records": records, "provider": provider,
            "enrichments": {e["item_id"]: e for e in result["enrichments"]},
            "recorded": {item_id: recorded(r) for item_id, r in last.items()
                         if not r["method"].startswith(("document-summary", "d3-check"))}}  # fmt: skip


def alone(name: str) -> dict:
    return json.loads((V80 / name).read_text())


def score_code(archive: Path, by_sha: dict[str, dict]) -> dict:
    metrics = t3.load(archive / t3.CODE_GOLD / "metrics.py", "code_metrics")
    gold = {u["unit_id"]: u for u in json.loads((archive / t3.CODE_GOLD / "per-unit.json").read_text())}
    method_alone = {r["unit"]: r for r in alone("t3-accuracy/evidence.json")["code"]["rows"]}
    rows = []
    for uid in method_alone:
        evidence = json.loads((archive / t3.CODE_GOLD / "native-evidence" /
                               (uid.replace(":", "__") + ".json")).read_text())  # fmt: skip
        paper = by_sha.get(evidence["pdf_sha256"])
        if paper is None:
            continue  # not run
        unions: dict[int, dict] = {}
        for region in evidence["regions"]:
            l, b, r, t = region["bbox"]
            u = unions.setdefault(region["page"], {"l": l, "b": b, "r": r, "t": t,
                                                   "coord_origin": "BOTTOMLEFT"})  # fmt: skip
            u.update(l=min(u["l"], l), b=min(u["b"], b), r=max(u["r"], r), t=max(u["t"], t))
        covering = [i for i in paper["items"] if i["method"] == "code" and i["page"] in unions
                    and t3.iou(i["bbox"], unions[i["page"]]) > 0]  # fmt: skip
        text = "\n".join(paper["records"][i["item_id"]]["content"] or "" for i in covering)
        ours = metrics.compare(gold[uid]["source_text"], text)
        before = method_alone[uid]
        rows.append({"unit": uid, "pages": sorted(unions), "items": len(covering),
                     "outcomes": [paper["records"][i["item_id"]]["outcome"] for i in covering],
                     "cer": ours["raw"]["CER"], "operators_exact": ours["operator_sequences"]["exact"],
                     "numbers_exact": ours["number_sequences"]["exact"],
                     "alone": {k: before[k] for k in ("cer", "operators_exact", "numbers_exact",
                                                      "inventory_covers_region")}})  # fmt: skip
    cers = [r["cer"] for r in rows if r["cer"] is not None]
    return {"units": len(rows), "of": len(method_alone),
            "cer_median": sorted(cers)[len(cers) // 2] if cers else None,
            "cer_median_alone": sorted(r["alone"]["cer"] for r in rows)[len(rows) // 2] if rows else None,
            "operators_exact": sum(r["operators_exact"] for r in rows),
            "numbers_exact": sum(r["numbers_exact"] for r in rows),
            "operators_exact_alone": sum(r["alone"]["operators_exact"] for r in rows),
            "numbers_exact_alone": sum(r["alone"]["numbers_exact"] for r in rows),
            "rows": rows}  # fmt: skip


def side_by_side(found: dict, before: list[dict], key: str, field: str, passing) -> dict:
    """t3's score on the workflow beside t3's own rows for the same units or tables."""
    rows = {r[key]: r for r in before}
    summary = {k: v for k, v in found.items() if k not in ("rows", "bar", "pass")}
    return {**summary, "alone": sum(passing(rows[r[key]].get(field)) for r in found["rows"]),
            "differing": [{key: r[key], "now": r.get(field), "alone": rows[r[key]].get(field)}
                          for r in found["rows"] if r.get(field) != rows[r[key]].get(field)]}  # fmt: skip


def same(a: str | None, b: str | None) -> bool:
    return a is not None and b is not None and re.sub(r"\s+", "", a) == re.sub(r"\s+", "", b)


def chart_scorer(gold_root: Path):
    """t4-accuracy's numeric(): PASS states of a chart against #84's frozen comparator."""
    sys.path[:0] = [str(gold_root / "round5-strict"), str(gold_root / "round3-luna"), str(gold_root)]
    import evaluate_v2 as v2  # type: ignore[import-not-found]

    golds = {g["index"]: g for g in json.loads(
        (gold_root / "round2/evaluator/image-gold.json").read_text())["records"]}  # fmt: skip

    def numeric(values: list, index: int, diagnosis: bool) -> int:
        chart = {"data": values or []}
        if diagnosis:
            chart = t4.axis_view(chart, index)
        chart, _ = v2.comparison_view(chart, index == 16)
        return [r["state"] for r in v2.e.chart_receipts(golds[index], chart)].count("PASS")

    return golds, numeric


async def accuracy(store, ran: dict[str, dict], archive: Path, judging: Path) -> dict:
    """ran: {index: {"request_id", "sha256", ...}} of the papers run; the scores and the sheets
    of the answers still to judge."""
    papers = {}
    for index, paper in ran.items():
        if await store.head(f"requests/{paper['request_id']}/result.json") is not None:
            papers[index] = await outputs(store, paper["request_id"])
    by_sha = {ran[i]["sha256"]: p for i, p in papers.items()}
    by_name = {Path(ran[i]["file"]).name: p for i, p in papers.items() if i != "w2"}
    before = alone("t3-accuracy/evidence.json")
    ocr = side_by_side(t3.score_ocr(archive, by_name), before["picture_ocr"]["rows"], "unit",
                       "ours", lambda state: state == "PASS_LITERAL")  # fmt: skip
    ocr["of"] = len(before["picture_ocr"]["rows"])
    tables = side_by_side(t3.score_tables(archive, by_name), before["table_status"]["rows"],
                          "table", "identical", bool)  # fmt: skip
    tables["of"] = len(before["table_status"]["rows"])

    gold_root = archive / t3.OCR_GOLD
    golds, numeric = chart_scorer(gold_root)
    crops = {c["index"]: c for c in json.loads(
        (gold_root / "round2/evaluator/crop-source-references.json").read_text())}  # fmt: skip
    t4_judged = json.loads(t4.JUDGMENTS.read_text())
    t4_evidence = alone("t4-accuracy/evidence.json")
    t4_charts = {c["gold_index"]: c for c in t4_evidence["charts"]}
    judgments = unblind(judging)
    pending, charts, descriptions, formulas = [], [], [], []
    targets = json.loads(t4.TARGETS.read_text())
    for t in targets:
        paper = papers.get(str(t["paper"]))
        if paper is None or (t["kind"] == "picture" and not t["matched"]):
            continue
        if t["kind"] == "picture":
            index, box = t["gold_index"], crops[t["gold_index"]]["crop"]["mapping"]["native_bbox"]
            pictures = [i for i in paper["items"] if i["method"] == "picture-interpretation"
                        and i["page"] == golds[index]["physical_page"]]  # fmt: skip
            item = max(pictures, key=lambda i: t4.iou(i["bbox"], box), default=None)
            if item is None or t4.iou(item["bbox"], box) < 0.5:
                descriptions.append({"gold_index": index, "label": t["label"], "matched": False})
                continue
            ours = {f: paper["enrichments"][f"{item['item_id']}/{f}"]["content"]
                    for f in ("description", "figure_type", "chart_values")}  # fmt: skip
            row = {"gold_index": index, "label": t["label"], "matched": True,
                   "recorded_request": paper["recorded"].get(item["item_id"]),
                   "same_answer": same(ours["description"], t["luna"]["description"])}  # fmt: skip
            if golds[index].get("numeric_points"):
                charts.append({"gold_index": index, "points": golds[index]["numeric_points"],
                               "formal": numeric(ours["chart_values"], index, False),
                               "diagnosis": numeric(ours["chart_values"], index, True),
                               "formal_alone": t4_charts[index]["luna_formal"],
                               "diagnosis_alone": t4_charts[index]["luna_diagnosis"],
                               "recorded_request": row["recorded_request"]})  # fmt: skip
            row["alone"] = t4_judged[t["label"]]["luna"]
            row["verdict"] = row["alone"] if row["same_answer"] else judgments.get(t["label"], {}).get("workflow")
            if row["verdict"] is None:
                pending.append({"label": t["label"], "kind": "picture", "gold_index": index,
                                "recorded": {"description": t["luna"]["description"],
                                             "figure_type": t["luna"]["figure_type"]},
                                "workflow": {"description": ours["description"],
                                             "figure_type": ours["figure_type"]}})  # fmt: skip
            descriptions.append(row)
        else:
            e = paper["enrichments"].get(t["item"]["item_id"])
            if e is None:
                formulas.append({"label": t["label"], "found": False})
                continue
            row = {"label": t["label"], "paper": t["paper"], "found": True,
                   "recorded_request": paper["recorded"].get(t["item"]["item_id"]),
                   "same_answer": same(e["content"], t["luna"]["latex"]),
                   "status": [e["status"], e["status_reason"]],
                   "status_alone": [t["luna"]["status"], t["luna"]["status_reason"]],
                   "d3": {k: e["signals"].get("d3", {}).get(k) for k in ("score", "p", "t_d", "state")},
                   "alone": t4_judged[t["label"]]["luna"]}  # fmt: skip
            row["verdict"] = row["alone"] if row["same_answer"] else judgments.get(t["label"], {}).get("workflow")
            if row["verdict"] is None:
                item = next(i for i in paper["items"] if i["item_id"] == t["item"]["item_id"])
                pending.append({"label": t["label"], "kind": "formula", "item": item,
                                "recorded": {"latex": t["luna"]["latex"]},
                                "workflow": {"latex": e["content"]}})  # fmt: skip
            formulas.append(row)
    await write_sheets(store, judging, pending, golds)

    def passed(rows: list[dict], key: str) -> int:
        return sum(r.get(key) in PASSES for r in rows)

    code = score_code(archive, by_sha)
    judged = [judgments[r["label"]] for r in descriptions + formulas if r.get("label") in judgments]
    return {
        "summary": {
            "picture_ocr": {k: ocr[k] for k in ("items", "of", "images", "literal_pass", "alone")},
            "code": {k: v for k, v in code.items() if k != "rows"},
            "table_status": {k: tables[k] for k in ("tables", "of", "identical", "alone")},
            "charts": {"images": len(charts), "points": sum(c["points"] for c in charts),
                       **{k: sum(c[k] for c in charts) for k in ("formal", "diagnosis",
                                                                 "formal_alone", "diagnosis_alone")}},
            "descriptions": {"matched": sum(r["matched"] for r in descriptions),
                             "pass": passed(descriptions, "verdict"),
                             "pass_alone": passed(descriptions, "alone"),
                             "same_answer": sum(r.get("same_answer", False) for r in descriptions)},
            "formulas": {"found": sum(r["found"] for r in formulas),
                         "pass": passed(formulas, "verdict"), "pass_alone": passed(formulas, "alone"),
                         "same_answer": sum(r.get("same_answer", False) for r in formulas),
                         "disputed": sum(r.get("status", [None])[0] == "disputed" for r in formulas),
                         "disputed_and_wrong": sum(r.get("status", [None])[0] == "disputed"
                                                   and r.get("verdict") == "FAIL" for r in formulas)},
            "judge_control": {"judged": len(judged),
                              "agrees_with_t4": sum(j["recorded"] == j["recorded_t4"] for j in judged)},
            "pending_judgments": len(pending),
        },  # fmt: skip
        "picture_ocr": ocr, "code": code, "table_status": tables, "charts": charts,
        "descriptions": descriptions, "formulas": formulas,
    }  # fmt: skip


async def write_sheets(store, judging: Path, pending: list[dict], golds: dict) -> None:
    """The blind sheets of the pending items, the key to unblind them beside."""
    from kp_canonicalization.methods.formula import _crop

    judging.mkdir(parents=True, exist_ok=True)
    sheets, key = [], {}
    for p in pending:
        order = ["recorded", "workflow"]
        random.Random(f"{p['label']} 199").shuffle(order)
        key[p["label"]] = {"A": order[0], "B": order[1]}
        sheet = {"label": p["label"], "kind": p["kind"], "A": p[order[0]], "B": p[order[1]]}
        if p["kind"] == "picture":
            sheet |= {"gold_index": p["gold_index"],
                      "obligations": golds[p["gold_index"]]["description_obligations"]}  # fmt: skip
        else:
            inputs = [await store.get(s["ref"]) for s in p["item"]["input_refs"]]
            (judging / f"{p['label']}.png").write_bytes(_crop(p["item"], inputs))
            sheet["crop"] = f"{p['label']}.png"
        sheets.append(sheet)
    (judging / "sheets.json").write_text(json.dumps(sheets, indent=2, ensure_ascii=False) + "\n")
    (judging / "key.json").write_text(json.dumps(key, indent=2) + "\n")


def unblind(judging: Path) -> dict:
    """judgments.json with the verdicts of judging/verdicts.json added, unblinded by its key; each
    {"workflow", "recorded", "recorded_t4", "note"}."""
    judgments = json.loads(JUDGMENTS.read_text()) if JUDGMENTS.exists() else {}
    if (judging / "verdicts.json").exists():
        key = json.loads((judging / "key.json").read_text())
        t4_judged = json.loads(t4.JUDGMENTS.read_text())
        for label, verdict in json.loads((judging / "verdicts.json").read_text()).items():
            if label in key:
                judgments[label] = {key[label]["A"]: verdict["A"], key[label]["B"]: verdict["B"],
                                    "recorded_t4": t4_judged[label]["luna"], "note": verdict.get("note")}  # fmt: skip
        JUDGMENTS.write_text(json.dumps(judgments, indent=2, sort_keys=True) + "\n")
    return judgments


async def summary_check(argv: list[str]) -> int:
    t5b = load("t5b_accuracy", V80 / "t5b-accuracy/run.py")
    t5b.HERE = HERE  # its evidence goes here, not into #155's folder
    out, name, rest = Path(argv[0]).expanduser(), argv[1], argv[2:]
    return await t5b.main([str(out / "summaries"), name, *rest])


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    assert command == "summary", "usage: score.py summary OUT SET_NAME N INDEX..."
    sys.exit(asyncio.run(summary_check(args)))
