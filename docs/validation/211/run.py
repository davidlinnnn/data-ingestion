"""#211: picture-interpretation@1 alone on t4's gold pictures after the chart label-role fix,
scored with #199's methods (docs/validation/199/score.py, imported unchanged).

    set -a; . ~/.config/kp-dev/anthropic.env; set +a
    .venv/bin/python docs/validation/211/run.py OUT ARCHIVE

OUT (outside the repo) keeps the answers and the judging sheets; ARCHIVE is the untracked tree
with the #84 gold. Run 1 sends t4's 18 gold pictures, runs 2 and 3 its 5 chart pictures, each
through score.alone_answers: the method's request on t4-seam-b's item and inputs (the S3
stand-in of tests/s3/compose.yaml, port 9100) to Sonnet 5.5 through the workflow's VLM
transport, answers in OUT/run<n>/alone, kept while the request and the model stay the same, so
a rerun only rescores. No workflow and none of #199's ports.

  charts        each run: t4's comparator in the formal and the diagnosis view, and the
                diagnosis view with two label fields exchanged: x and category (score.swapped;
                x is a number now, so this is the same score by construction) and series and
                category, the exchange the schema still allows, which must score lower
  descriptions  run 1, judged blind by t4's rules as #199 did: an answer equal to Luna's keeps
                t4's verdict, any other goes to OUT/judging/sheets.json (letters.json beside
                it); a judge writes verdicts.json there and the next run merges it into
                judgments.json here; beside #199's workflow and alone verdicts. A verdict
                changed by hand carries "reversed": {"from", "why"} in judgments.json
  figure types  run 1 against the gold (a chart or not) and beside Luna's recorded answer,
                which #199's Sonnet answers equal on all 18; captions have no gold: not blank

Writes evidence.json and manifest.json (sha256 of the gold files read and of everything in OUT).
"""

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

import httpx

from kp_canonicalization.ports.inference import OpenAIChat
from kp_canonicalization.profile import load_profile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


score = load("score_199", HERE.parent / "199/score.py")
score.JUDGMENTS = HERE / "judgments.json"  # this ticket's verdicts; #199's file stays as it is
BEFORE = HERE.parent / "199/accuracy.json"
TARGETS = score.t4.TARGETS  # t4's own list; main points score.t4.TARGETS at each run's part of it

ANTHROPIC = "https://api.anthropic.com/v1"
MODEL = "claude-sonnet-5-5"
PRICE_PER_MTOK = (2.0, 10.0)  # Sonnet 5.5, USD per million input and output tokens
PROFILE = REPO / "src/kp_canonicalization/profiles/paper-pdf@1.yaml"
CHARTS = (6, 16, 17, 21, 22)
RUNS = 3
BAR = 83  # t4's bar: not below #84's Luna on the diagnosis view
PICTURES = 18  # t4's gold pictures; the bar for their descriptions is #199's workflow count
FIELDS = ("description", "figure_type")  # what #199 put on a description sheet
# read by t4's comparator (#84's frozen evaluator and contracts), under ARCHIVE
COMPARATOR = ("round3-luna/evaluate_v1.py", "round5-strict/evaluate.py",
              "round5-strict/evaluate_v2.py", "round2/evaluator/image-gold.json")  # fmt: skip
CONTRACTS = [f"docs/research/pdf-core-eval-interfaces-2026-10-18/C/evaluator-{name}-contract.json"
             for name in ("wikiskill-figure1", "memory-r1")]  # fmt: skip


def content(answer: dict | None) -> dict | None:
    return ((answer or {}).get("parsed") or {}).get("content")


def roles_swapped(values: list | None) -> list:
    """series and category exchanged where both are strings, as score.swapped does for x."""
    return [p | {"series": p["category"], "category": p["series"]}
            if isinstance(p.get("series"), str) and isinstance(p.get("category"), str) else p
            for p in values or []]  # fmt: skip


async def main(argv: list[str]) -> int:
    out, archive = Path(argv[0]), Path(argv[1])
    targets = [t for t in json.loads(TARGETS.read_text())
               if t["kind"] == "picture" and t["matched"]]  # fmt: skip
    runs = []
    async with httpx.AsyncClient() as http:
        chat = OpenAIChat(http, ANTHROPIC, os.environ.get("ANTHROPIC_API_KEY", ""), MODEL, 5, 600)
        for n in range(1, RUNS + 1):
            folder = out / f"run{n}"
            folder.mkdir(parents=True, exist_ok=True)
            sent = [t for t in targets if n == 1 or t["gold_index"] in CHARTS]
            (folder / "targets.json").write_text(json.dumps(sent, indent=1) + "\n")
            score.t4.TARGETS = folder / "targets.json"  # alone_answers sends what it lists
            papers = {t["paper"] for t in sent}
            runs.append(await score.alone_answers(folder, papers, PROFILE, chat))

    golds, numeric = score.chart_scorer(archive / score.t3.OCR_GOLD)
    charts = []
    for n, run in enumerate(runs, 1):
        rows = []
        for t in targets:
            if t["gold_index"] in CHARTS:
                i = t["gold_index"]
                values = (content(run.get(t["label"])) or {}).get("chart_values")
                rows.append({"gold_index": i, "points": golds[i]["numeric_points"],
                             "formal": numeric(values, i, False),
                             "diagnosis": numeric(values, i, True),
                             "diagnosis_swapped": numeric(score.swapped(values), i, True),
                             "diagnosis_roles_swapped": numeric(roles_swapped(values), i, True)})
        keys = ("points", "formal", "diagnosis", "diagnosis_swapped", "diagnosis_roles_swapped")
        total = {k: sum(r[k] for r in rows) for k in keys}
        total["pass"] = (len(rows) == len(CHARTS) and total["points"] == 88
                         and BAR <= total["diagnosis"] <= total["points"]
                         and total["diagnosis_swapped"] <= total["diagnosis"]
                         and total["diagnosis_roles_swapped"] < total["diagnosis"])  # fmt: skip
        charts.append({"run": n, "rows": rows, "total": total})

    t4_judged = json.loads(score.t4.JUDGMENTS.read_text())
    before = {r["gold_index"]: r for r in json.loads(BEFORE.read_text())["descriptions"]}
    judging = out / "judging"
    judgments = score.unblind(judging)
    pending, descriptions = [], []
    for t in targets:
        ours = content(runs[0].get(t["label"]))
        answers = {"recorded": {f: t["luna"][f] for f in FIELDS},
                   "alone": {f: ours[f] for f in FIELDS} if ours else None,
                   "workflow": None}  # fmt: skip
        found, todo = score.verdicts(t["label"], answers, "description",
                                     t4_judged[t["label"]]["luna"], judgments)  # fmt: skip
        i = t["gold_index"]
        descriptions.append({"gold_index": i, "label": t["label"], "verdict": found["alone"],
                             "workflow_199": before[i]["verdict"], "alone_199": before[i]["alone"],
                             "recorded": t4_judged[t["label"]]["luna"],
                             "control": judgments.get(t["label"], {}).get("control"),
                             "reversed_from": judgments.get(t["label"], {}).get(
                                 "reversed", {}).get("from"),
                             "figure_type": (ours or {}).get("figure_type"),
                             "figure_type_recorded": t["luna"]["figure_type"],
                             "chart_gold": golds[i]["chart_expected"] != "not_chart",
                             "caption": bool((ours or {}).get("caption", "").strip())})  # fmt: skip
        if todo:
            pending.append({"label": t["label"], "kind": "picture", "gold_index": i,
                            "recorded": answers["recorded"], "answers": todo})  # fmt: skip
    await score.write_sheets(judging, pending, golds, archive)
    # self-check before a judge reads them: each item once, each image the gold crop
    sheets = json.loads((judging / "sheets.json").read_text())
    assert len({s["label"] for s in sheets}) == len(sheets) == len(pending)
    for s in sheets:
        image = (judging / s["image"]).read_bytes()
        assert score.sha(image) == golds[s["gold_index"]]["source_crop_sha256"]

    passed = sum(d["verdict"] in score.PASSES for d in descriptions)
    bar = sum(d["workflow_199"] in score.PASSES for d in descriptions)
    kept = {"figure_type_as_recorded": sum(d["figure_type"] == d["figure_type_recorded"]
                                           for d in descriptions),
            "chart_as_gold": sum((d["figure_type"] == "chart") == d["chart_gold"]
                                 for d in descriptions),
            "captions": sum(d["caption"] for d in descriptions)}  # fmt: skip
    usage = [a["usage"] for run in runs for a in run.values() if a.get("usage")]
    tokens = [sum(u["prompt_tokens"] for u in usage), sum(u["completion_tokens"] for u in usage)]
    method = load_profile(PROFILE).methods["picture-interpretation"]
    evidence = {
        "model": MODEL,
        "method": {"ref": "picture-interpretation@1", "module_digest": method.module_digest},
        "charts": charts,
        "descriptions": {
            "rows": descriptions, "pass": passed, "of": len(descriptions),
            # a verdict reversed by hand (judgments.json "reversed") counts as the judge gave it
            "pass_as_judged": sum((d["reversed_from"] or d["verdict"]) in score.PASSES
                                  for d in descriptions),
            "control_as_t4": sum(d["control"] in score.PASSES and d["recorded"] in score.PASSES
                                 or d["control"] == d["recorded"] for d in descriptions),
            "not_judged": sum(d["verdict"] is None for d in descriptions),
            "workflow_199": bar,
            "pass_bar": len(descriptions) == PICTURES and 0 < bar <= passed <= PICTURES,
            **kept, "pass_kept": all(n == PICTURES for n in kept.values())},
        "requests": {
            "answered": len(usage),
            "without_content": sum(content(a) is None for run in runs for a in run.values()),
            "tokens_in_out": tokens,
            "usd": round(sum(t * p for t, p in zip(tokens, PRICE_PER_MTOK, strict=True)) / 1e6, 2)},
    }  # fmt: skip
    (HERE / "evidence.json").write_text(json.dumps(evidence, indent=1) + "\n")
    gold_files = [*(archive / score.t3.OCR_GOLD / name for name in COMPARATOR),
                  *(archive / name for name in CONTRACTS),
                  *(archive / golds[t["gold_index"]]["input_asset"] for t in targets)]  # fmt: skip
    files = sorted(p for p in out.rglob("*") if p.is_file())
    manifest = {"gold": {str(p.relative_to(archive)): score.sha(p.read_bytes())
                         for p in gold_files},
                "out": {str(p.relative_to(out)): score.sha(p.read_bytes()) for p in files}}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    shown = {k: v for k, v in evidence["descriptions"].items() if k != "rows"}
    print(json.dumps({"charts": [c["total"] for c in charts], "descriptions": shown,
                      "requests": evidence["requests"], "to_judge": len(pending)}, indent=1))
    passing = (all(c["total"]["pass"] for c in charts) and evidence["descriptions"]["pass_bar"]
               and evidence["descriptions"]["pass_kept"])  # fmt: skip
    return 0 if passing else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
