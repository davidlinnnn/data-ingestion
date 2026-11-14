"""#199 accuracy: the enrichments the workflow registered, scored with the gold and the scorers of
t3-accuracy, t4-accuracy and t5b-accuracy, beside the scores of the methods run alone. run.py
calls accuracy() with the S3 stand-in up; no paper text leaves OUT.

  picture-ocr, table-status  t3's score_ocr and score_tables, unchanged, on the workflow's items,
           outcome records and OCR lines, each unit or table beside t3's row
  code     each #84 code unit: the workflow's code items that overlap the unit's region on its
           pages, joined in inventory order, against the unit's source text with #84's
           metrics.compare. t3 ran the method on the unit's fixed region instead
  pictures t4's gold pictures matched to a picture-interpretation item as t4 matched them (page,
           box overlap >= 0.5): chart values with t4's comparator in both views, and descriptions
  formulas t4's 46 sampled formulas, by item_id

The VLM methods ran alone (alone_answers): t4's targets, the very request bodies t4-seam-b's
runs sent, to the workflow's VLM model through its transport, outside the workflow; answers in
OUT/alone. Each scored VLM item has three answers: recorded (t4's gpt-6-luna answer, with t4's
verdict), alone and workflow. An answer equal to the recorded one (whitespace aside) keeps t4's
verdict, none is FAIL, any other is judged blind. Every item says whether the workflow sent the
alone request body (same_request) and whether it is one the recordings hold (recorded): the
same request with another answer is the model's run-to-run variation.

Blind judging: OUT/judging/sheets.json holds each item with an answer to judge, its distinct
answers and the recorded one (the control) as A, B, C in a seeded order (key.json beside it),
with the gold obligations or the formula crop; the judge writes OUT/judging/verdicts.json,
{label: {"A", "B", ..., "note"}}, by t4-accuracy's rules. accuracy() unblinds it into
judgments.json here, each verdict under the sha256 of its answer, so a new answer is judged anew.

    set -a; . ~/.config/kp-dev/anthropic.env; set +a
    .venv/bin/python docs/validation/199/score.py summary OUT SET_NAME N INDEX...

runs t5b-accuracy's planted-error check on OUT/summaries (written by run.py), unchanged but for
its planter when PLANTER is set; it writes evidence-SET_NAME.json here.
"""

import asyncio
import hashlib
import importlib.util
import json
import os
import random
import re
import statistics
import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config

HERE = Path(__file__).resolve().parent
# t4-seam-b's runs, on the shared S3 stand-in of tests/s3/compose.yaml
SEAMB_S3 = {"endpoint_url": "http://127.0.0.1:9100", "aws_access_key_id": "kpdev",
            "aws_secret_access_key": "kpdev-secret"}  # fmt: skip
V80 = HERE.parent / "80"
REPO = HERE.parents[2]
FIXTURES = REPO / "tests/fixtures/vlm"
JUDGMENTS = HERE / "judgments.json"
PASSES = ("PASS", "PASS_MEANING_SLICE")
# t5b-accuracy plants its errors with gpt-6-luna, whose DEV key expired (2026-11-15): Sonnet 5.5,
# the judge's model, plants instead. None runs t5b-accuracy unchanged.
PLANTER = "claude-sonnet-5-5"


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
        if not receipt["method"].startswith(("document-summary", "d3-check")):
            last[receipt["item_id"]] = receipt
    return {"result": result, "items": items, "records": records, "provider": provider,
            "enrichments": {e["item_id"]: e for e in result["enrichments"]},
            "recorded": {item_id: recorded(r) for item_id, r in last.items()},
            "digests": {item_id: r["params_digest"] for item_id, r in last.items()}}  # fmt: skip


def alone(name: str) -> dict:
    return json.loads((V80 / name).read_text())


def seamb_store(bucket: str):
    from kp_canonicalization.ports.object_store import S3ObjectStore

    client = boto3.client("s3", region_name="us-east-1", config=Config(s3={"addressing_style": "path"}),
                          **SEAMB_S3)  # fmt: skip
    return S3ObjectStore(client, bucket)


async def seamb_inputs(t: dict) -> list[bytes]:
    store = seamb_store(t4.runs()[t["paper"]][0])
    return [await store.get(source["ref"]) for source in t["item"]["input_refs"]]


async def alone_answers(out: Path, papers: set[int], profile: Path, chat) -> dict[str, dict]:
    """OUT/alone/<label>.json for t4's targets in the papers given, each sent once and kept: the
    method's request on t4's item and inputs through chat, the workflow's VLM transport, with
    up to 3 tries on ServiceUnavailable; parsed with the method's parse."""
    from kp_canonicalization.identity import canonical_json
    from kp_canonicalization.methods import InvalidOutput
    from kp_canonicalization.ports.inference import ServiceUnavailable
    from kp_canonicalization.profile import load_profile

    methods = load_profile(profile).methods
    folder = out / "alone"
    folder.mkdir(parents=True, exist_ok=True)
    targets = [t for t in json.loads(t4.TARGETS.read_text())
               if t["paper"] in papers and t.get("matched", True)]  # fmt: skip
    limit = asyncio.Semaphore(4)

    async def one(t: dict) -> None:
        path = folder / f"{t['label']}.json"
        if path.exists():
            return
        item, inputs = t["item"], await seamb_inputs(t)
        package = methods[item["method"]].package
        request = package.request(item, inputs)
        found: dict = {"label": t["label"], "params_digest": sha(canonical_json(request))}
        async with limit:
            for attempt in range(3):
                begin = time.perf_counter()
                try:
                    answer = await chat.complete(request)
                    break
                except ServiceUnavailable as exc:
                    found["error"] = exc.reason
                    await asyncio.sleep(5 * (attempt + 1))
            else:
                path.write_text(json.dumps(found | {"parsed": {"outcome": "unavailable"}}, indent=1) + "\n")
                return
        found |= {"model": answer.model, "elapsed_s": round(time.perf_counter() - begin, 1),
                  "finish_reason": json.loads(answer.body)["choices"][0].get("finish_reason"),
                  "usage": answer.usage, "content": answer.content}  # fmt: skip
        try:
            output = package.parse(item, inputs, answer.content or "")
            found["parsed"] = {"outcome": output.outcome, "content": output.content}
        except InvalidOutput as exc:
            found["parsed"] = {"outcome": "invalid", "reason": exc.reason}
        path.write_text(json.dumps(found, indent=1, ensure_ascii=False) + "\n")
        print("alone", t["label"], found["elapsed_s"], found["parsed"]["outcome"], flush=True)

    await asyncio.gather(*(one(t) for t in targets))
    return {p.stem: json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))}


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
            "cer_median": statistics.median(cers) if cers else None,
            "cer_median_alone": statistics.median(r["alone"]["cer"] for r in rows) if rows else None,
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


def answer_sha(text: str) -> str:
    return sha(re.sub(r"\s+", "", text).encode())


def verdicts(label: str, answers: dict[str, dict | None], text: str, t4_verdict: str,
             judgments: dict) -> tuple[dict[str, str | None], list[tuple[str, dict]]]:  # fmt: skip
    """Per role ("alone", "workflow") its verdict: FAIL without an answer, t4's verdict for the
    recorded answer's text, else this run's verdict on that answer (None: not judged yet); and
    the distinct answers still to judge, as (sha256, answer)."""
    judged = judgments.get(label, {}).get("verdicts", {})
    found, pending = {}, {}
    for role in ("alone", "workflow"):
        answer = answers[role]
        if answer is None or not answer.get(text):
            found[role] = "FAIL"
        elif same(answer[text], answers["recorded"][text]):
            found[role] = t4_verdict
        else:
            found[role] = judged.get(answer_sha(answer[text]))
            if found[role] is None:
                pending.setdefault(answer_sha(answer[text]), answer)
    return found, list(pending.items())


def swapped(values: list | None) -> list:
    """x and category exchanged where both are strings: a label-only view that explains a
    difference (t4's diagnosis view maps gpt-6-luna's label layout, Sonnet 5.5 can put the two
    labels the other way round); it replaces neither of t4's views."""
    return [p | {"x": p["category"], "category": p["x"]}
            if isinstance(p.get("x"), str) and isinstance(p.get("category"), str) else p
            for p in values or []]  # fmt: skip


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


async def accuracy(store, ran: dict[str, dict], archive: Path, judging: Path,
                   answered: dict[str, dict]) -> dict:  # fmt: skip
    """ran: {index: {"request_id", "sha256", ...}} of the papers run, answered: alone_answers();
    the scores and the sheets of the answers still to judge."""
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
    for t in json.loads(t4.TARGETS.read_text()):
        paper = papers.get(str(t["paper"]))
        if paper is None or (t["kind"] == "picture" and not t["matched"]):
            continue
        by_alone = answered.get(t["label"], {})
        content = by_alone.get("parsed", {}).get("content")
        if t["kind"] == "picture":
            index, box = t["gold_index"], crops[t["gold_index"]]["crop"]["mapping"]["native_bbox"]
            pictures = [i for i in paper["items"] if i["method"] == "picture-interpretation"
                        and i["page"] == golds[index]["physical_page"]]  # fmt: skip
            item = max(pictures, key=lambda i: t4.iou(i["bbox"], box), default=None)
            if item is not None and t4.iou(item["bbox"], box) < 0.5:
                item = None
            fields = ("description", "figure_type", "chart_values")
            ours = ({f: paper["enrichments"][f"{item['item_id']}/{f}"]["content"] for f in fields}
                    if item else {f: None for f in fields})  # fmt: skip
            answers = {"recorded": {f: t["luna"][f] for f in fields[:2]},
                       "alone": {f: content[f] for f in fields[:2]} if content else None,
                       "workflow": {f: ours[f] for f in fields[:2]} if item else None}  # fmt: skip
            found, todo = verdicts(t["label"], answers, "description", t4_judged[t["label"]]["luna"],
                                   judgments)  # fmt: skip
            row = {"gold_index": index, "label": t["label"], "matched": item is not None,
                   "verdict": found["workflow"], "alone": found["alone"],
                   "recorded": t4_judged[t["label"]]["luna"]}  # fmt: skip
            if item:
                row |= {"same_request": paper["digests"].get(item["item_id"]) == by_alone.get("params_digest"),
                        "recorded_request": paper["recorded"].get(item["item_id"]),
                        "same_answer": same(ours["description"], (content or {}).get("description")),
                        "status": {f: paper["enrichments"][f"{item['item_id']}/{f}"]["status_reason"]
                                   for f in ("description", "chart_values")}}  # fmt: skip
            if golds[index].get("numeric_points"):
                values_alone = (content or {}).get("chart_values")
                charts.append({"gold_index": index, "points": golds[index]["numeric_points"],
                               "formal": numeric(ours["chart_values"], index, False),
                               "diagnosis": numeric(ours["chart_values"], index, True),
                               "formal_alone": numeric(values_alone, index, False),
                               "diagnosis_alone": numeric(values_alone, index, True),
                               "formal_recorded": t4_charts[index]["luna_formal"],
                               "diagnosis_recorded": t4_charts[index]["luna_diagnosis"],
                               "diagnosis_swapped": numeric(swapped(ours["chart_values"]), index, True),
                               "diagnosis_swapped_alone": numeric(swapped(values_alone), index, True),
                               "same_request": row.get("same_request")})  # fmt: skip
            if todo:
                pending.append({"label": t["label"], "kind": "picture", "gold_index": index,
                                "recorded": answers["recorded"], "answers": todo})  # fmt: skip
            descriptions.append(row)
        else:
            e = paper["enrichments"].get(t["item"]["item_id"])
            answers = {"recorded": {"latex": t["luna"]["latex"]},
                       "alone": {"latex": content} if content else None,
                       "workflow": {"latex": e["content"]} if e else None}  # fmt: skip
            found, todo = verdicts(t["label"], answers, "latex", t4_judged[t["label"]]["luna"], judgments)
            row = {"label": t["label"], "paper": t["paper"], "found": e is not None,
                   "verdict": found["workflow"], "alone": found["alone"],
                   "recorded": t4_judged[t["label"]]["luna"]}  # fmt: skip
            if e is not None:
                row |= {"same_request": paper["digests"].get(e["item_id"]) == by_alone.get("params_digest"),
                        "recorded_request": paper["recorded"].get(e["item_id"]),
                        "same_answer": same(e["content"], content),
                        "status": [e["status"], e["status_reason"]],
                        "status_recorded": [t["luna"]["status"], t["luna"]["status_reason"]],
                        "d3": {k: e["signals"].get("d3", {}).get(k) for k in ("score", "p", "t_d", "state")}}  # fmt: skip
            if todo:
                pending.append({"label": t["label"], "kind": "formula", "t": t,
                                "recorded": answers["recorded"], "answers": todo})  # fmt: skip
            formulas.append(row)
    await write_sheets(judging, pending, golds, archive)

    def passed(rows: list[dict], key: str) -> int:
        return sum(r.get(key) in PASSES for r in rows)

    def counts(rows: list[dict]) -> dict:
        return {"pass": passed(rows, "verdict"), "pass_alone": passed(rows, "alone"),
                "pass_recorded": passed(rows, "recorded"),
                "not_judged": sum(r["verdict"] is None or r["alone"] is None for r in rows),
                "same_answer": sum(r.get("same_answer", False) for r in rows),
                "same_request": sum(r.get("same_request", False) for r in rows)}  # fmt: skip

    code = score_code(archive, by_sha)
    control = [j for j in judgments.values() if j.get("control")]
    return {
        "summary": {
            "picture_ocr": {k: ocr[k] for k in ("items", "of", "images", "literal_pass", "alone")},
            "code": {k: v for k, v in code.items() if k != "rows"},
            "table_status": {k: tables[k] for k in ("tables", "of", "identical", "alone")},
            "charts": {"images": len(charts), "points": sum(c["points"] for c in charts),
                       **{k: sum(c[k] for c in charts) for k in (
                           "formal", "diagnosis", "formal_alone", "diagnosis_alone",
                           "formal_recorded", "diagnosis_recorded", "diagnosis_swapped",
                           "diagnosis_swapped_alone")}},  # fmt: skip
            "descriptions": {"matched": sum(r["matched"] for r in descriptions), **counts(descriptions)},
            "formulas": {"found": sum(r["found"] for r in formulas), **counts(formulas),
                         "disputed": sum(r.get("status", [None])[0] == "disputed" for r in formulas),
                         "disputed_and_wrong": sum(r.get("status", [None])[0] == "disputed"
                                                   and r["verdict"] == "FAIL" for r in formulas)},
            "judge_control": {"judged": len(control),
                              "agrees_with_t4": sum(j["control"] == j["recorded_t4"] for j in control)},
            "pending_judgments": len(pending),
        },  # fmt: skip
        "picture_ocr": ocr, "code": code, "table_status": tables, "charts": charts,
        "descriptions": descriptions, "formulas": formulas,
    }  # fmt: skip


async def write_sheets(judging: Path, pending: list[dict], golds: dict, archive: Path) -> None:
    """The blind sheets of the pending items, each with its image (the gold crop of a picture,
    the formula crop t4 judged), and the key to unblind them beside: per letter the sha256 of
    its answer, or "recorded"."""
    from kp_canonicalization.methods.formula import _crop

    judging.mkdir(parents=True, exist_ok=True)
    sheets, key = [], {}
    for p in pending:
        shown = [("recorded", p["recorded"]), *p["answers"]]
        random.Random(f"{p['label']} 199").shuffle(shown)
        letters = "ABCDEFGH"[: len(shown)]
        key[p["label"]] = {letter: name for letter, (name, _) in zip(letters, shown, strict=True)}
        sheet = {"label": p["label"], "kind": p["kind"],
                 **{letter: answer for letter, (_, answer) in zip(letters, shown, strict=True)}}  # fmt: skip
        image = judging / f"{p['label']}.png"
        if p["kind"] == "picture":
            gold = golds[p["gold_index"]]
            image.write_bytes((archive / gold["input_asset"]).read_bytes())
            sheet |= {"gold_index": p["gold_index"], "obligations": gold["description_obligations"]}
        else:
            image.write_bytes(_crop(p["t"]["item"], await seamb_inputs(p["t"])))
        sheet["image"] = image.name
        sheets.append(sheet)
    (judging / "sheets.json").write_text(json.dumps(sheets, indent=2, ensure_ascii=False) + "\n")
    (judging / "key.json").write_text(json.dumps(key, indent=2) + "\n")


def unblind(judging: Path) -> dict:
    """judgments.json with the verdicts of judging/verdicts.json added, unblinded by its key;
    each {"verdicts": {answer sha256: verdict}, "control": the verdict on the recorded answer,
    "recorded_t4": t4's verdict on it, "note"}."""
    judgments = json.loads(JUDGMENTS.read_text()) if JUDGMENTS.exists() else {}
    if (judging / "verdicts.json").exists():
        key = json.loads((judging / "key.json").read_text())
        t4_judged = json.loads(t4.JUDGMENTS.read_text())
        for label, verdict in json.loads((judging / "verdicts.json").read_text()).items():
            if label not in key:
                continue
            entry = judgments.setdefault(label, {"verdicts": {}})
            for letter, name in key[label].items():
                if name == "recorded":
                    entry["control"] = verdict[letter]
                else:
                    entry["verdicts"][name] = verdict[letter]
            entry |= {"recorded_t4": t4_judged[label]["luna"], "note": verdict.get("note")}
        JUDGMENTS.write_text(json.dumps(judgments, indent=2, sort_keys=True) + "\n")
        # merged: the next sheets get a new key, which these letters do not follow
        merged = len(list(judging.glob("verdicts-*.json")))
        (judging / "verdicts.json").rename(judging / f"verdicts-{merged + 1}.json")
    return judgments


async def summary_check(argv: list[str]) -> int:
    t5b = load("t5b_accuracy", V80 / "t5b-accuracy/run.py")
    t5b.HERE = HERE  # its evidence goes here, not into #155's folder
    out, name, rest = Path(argv[0]).expanduser(), argv[1], argv[2:]
    if PLANTER:
        chat = t5b.OpenAIChat

        def planter(http, base_url, api_key, model, connect_s, total_s):
            if model == "gpt-6-luna":
                base_url, api_key, model = "https://api.anthropic.com/v1", os.environ["ANTHROPIC_API_KEY"], PLANTER
            return chat(http, base_url, api_key, model, connect_s, total_s)

        t5b.OpenAIChat = planter
    code = await t5b.main([str(out / "summaries"), name, *rest])
    evidence = HERE / f"evidence-{name}.json"
    if PLANTER and evidence.exists():
        evidence.write_text(json.dumps(json.loads(evidence.read_text()) | {"planter": PLANTER}, indent=2) + "\n")
    return code


if __name__ == "__main__":
    command, *args = sys.argv[1:]
    assert command == "summary", "usage: score.py summary OUT SET_NAME N INDEX..."
    sys.exit(asyncio.run(summary_check(args)))
