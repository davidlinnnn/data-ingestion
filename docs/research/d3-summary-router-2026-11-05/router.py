"""#166 router metrics: the frozen dev selection, then the one test evaluation.

    .venv/bin/python docs/research/d3-summary-router-2026-11-05/router.py select OUT
    .venv/bin/python docs/research/d3-summary-router-2026-11-05/router.py evaluate OUT

A sentence is flagged when its d3 score (the selected question's P(supported) or P(yes)) is at
most a threshold. A verify unit (one first verify call of the run: a Section's sentences, or one
overview sentence) goes to the LLM when any of its sentences is flagged, and is skipped
otherwise. The rules are freeze.md §5; select writes selection.json and test-launch.json here,
evaluate writes metrics.json here (no paper text) and OUT/flagged-delivered.json (with text) for
the blind check of the delivered sentences d3 would mark.
"""

import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score as s153  # noqa: E402  (#153's scoring, verbatim)

ALT_MISS = 0.05  # A1 option 2: d3 lets at most 5% of the plants through


def route_threshold(plants: list[tuple[float, bool]]) -> float | None:
    """A1 option 1: the lowest t that flags every plant the LLM catches."""
    caught = [score for score, llm_caught in plants if llm_caught]
    return max(caught) if caught else None


def route_threshold_alt(scores: list[float], miss: float = ALT_MISS) -> float:
    """A1 option 2: the lowest t with at most floor(miss * n) plants scoring above it."""
    return sorted(scores, reverse=True)[int(miss * len(scores))]


def routed(items: list[str], scores: dict[str, float], t: float) -> bool:
    return any(scores[i] <= t for i in items)


def fit_tokens(steps: dict, units: list[dict]) -> dict:
    """Per-call token model from the 20 papers' step totals (least squares, no intercept):
    verify prompt = a*calls + b*chars, verify completion = c*calls + d*sentences judged,
    repair prompt = e*calls + f*chars, repair completion = g*calls."""
    rows = {}
    for u in units:
        r = rows.setdefault(str(u["paper"]), np.zeros(6))
        r += [1 + len(u["reverify_chars"]), u["verify_chars"] + sum(u["reverify_chars"]),
              len(u["sentences"]) + len(u["reverify_chars"]),
              len(u["repair_chars"]), sum(u["repair_chars"]), 0]  # fmt: skip
    papers = sorted(rows)
    none = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}
    steps = {p: {"repair": none, **steps[p]} for p in papers}  # a paper without repairs has none
    x = np.array([rows[p] for p in papers])
    for p, r in zip(papers, x, strict=True):
        assert r[0] == steps[p]["verify"]["calls"] and r[3] == steps[p]["repair"]["calls"], p
    fits = {}
    for name, step, kind, columns in [("verify_prompt", "verify", "prompt_tokens", [0, 1]),
                                      ("verify_completion", "verify", "completion_tokens", [0, 2]),
                                      ("repair_prompt", "repair", "prompt_tokens", [3, 4]),
                                      ("repair_completion", "repair", "completion_tokens", [3])]:  # fmt: skip
        y = np.array([steps[p][step][kind] for p in papers], dtype=float)
        coef = np.linalg.lstsq(x[:, columns], y, rcond=None)[0]
        fitted = x[:, columns] @ coef
        error = np.abs(fitted - y)[y > 0] / y[y > 0]
        fits[name] = {"coef": coef.tolist(), "max_relative_error": float(np.max(error))}
    return fits


def unit_tokens(u: dict, fits: dict) -> dict:
    """The tokens of a unit's first verify call, and of the repairs and re-verifies after it."""
    vp, vc = fits["verify_prompt"]["coef"], fits["verify_completion"]["coef"]
    rp, rc = fits["repair_prompt"]["coef"], fits["repair_completion"]["coef"]
    first = vp[0] + vp[1] * u["verify_chars"] + vc[0] + vc[1] * len(u["sentences"])
    after = sum(rp[0] + rp[1] * c + rc[0] for c in u["repair_chars"])
    after += sum(vp[0] + vp[1] * c + vc[0] + vc[1] for c in u["reverify_chars"])
    return {"first_verify": first, "after": after}


def at(t: float, units: list[dict], cases: list[dict], scores: dict, fits: dict) -> dict:
    """Every router number at threshold t, over the given units and labelled cases."""
    plants = [c for c in cases if c["role"] == "planted"]
    own = [scores[c["item"]] <= t for c in plants]
    unit = [o or routed(c["mates"], scores, t) for o, c in zip(own, plants, strict=True)]
    caught = [c["llm_caught"] for c in plants]
    finals = {u["id"]: [s["final"] for s in u["sentences"] if s["final"]] for u in units}
    unit_of = {f: uid for uid, fs in finals.items() for f in fs}
    originals = [c for c in cases if c["role"] == "original"]
    dropped = [c["llm_caught"] and routed(finals[unit_of[c["item"]]], scores, t)
               for c in originals]  # fmt: skip
    go = {u["id"]: routed([s["item"] for s in u["sentences"]], scores, t) for u in units}
    natural = [go[u["id"]] for u in units for s in u["sentences"] if s["llm_flagged"]]
    tokens = {u["id"]: unit_tokens(u, fits) for u in units}
    saved = {k: sum(tokens[u][k] for u in go if not go[u]) for k in ("first_verify", "after")}
    total = {k: sum(v[k] for v in tokens.values()) for k in ("first_verify", "after")}
    return {
        "t": t,
        "d3_recall": s153.rate(sum(own), len(plants)),
        "overall_catch": s153.rate(sum(o and c for o, c in zip(own, caught)), len(plants)),
        "overall_catch_unit": s153.rate(sum(u and c for u, c in zip(unit, caught)), len(plants)),
        "llm_catch_on_flagged": s153.rate(sum(o and c for o, c in zip(own, caught)), sum(own)),
        "llm_alone_catch": s153.rate(sum(caught), len(plants)),
        "false_drop": s153.rate(sum(dropped), len(originals)),
        "llm_alone_false_drop": s153.rate(sum(c["llm_caught"] for c in originals), len(originals)),
        "units_skipped": s153.rate(sum(not g for g in go.values()), len(go)),
        "units_skipped_by_kind": {
            kind: s153.rate(sum(not go[u["id"]] for u in units if u["kind"] == kind),
                            sum(u["kind"] == kind for u in units))
            for kind in ("section", "overview")},  # fmt: skip
        "llm_flagged_still_routed": s153.rate(sum(natural), len(natural)),
        "tokens_saved": saved,
        "tokens_modelled": total,
    }


def load(out: Path, split: str) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted((out / "runs" / split / "items").glob("*"))]


def inputs(out: Path, split: str):
    items = [i for i in json.loads((out / "items.json").read_text()) if i["split"] == split]
    results = {r["id"]: r for r in load(out, split)}
    missing = [i["id"] for i in items if i["id"] not in results]
    assert not missing, f"{len(missing)} {split} items have no result"
    units = [u for u in json.loads((out / "units.json").read_text()) if u["split"] == split]
    cases = [c for c in json.loads((out / "cases.json").read_text()) if c["split"] == split]
    steps = json.loads((out / "steps.json").read_text())
    every = json.loads((out / "units.json").read_text())
    return items, results, units, cases, fit_tokens(steps, every)


def labelled(cases: list[dict], scores: dict) -> tuple[list[str], list[float], list[str]]:
    """Labels, scores and bootstrap groups (the case's unit, shared by original and plant)."""
    chosen = [c for c in cases if c["role"] in ("original", "planted")]
    labels = ["correct" if c["role"] == "original" else "meaning_changed" for c in chosen]
    return labels, [scores[c["item"]] for c in chosen], [c["unit"] for c in chosen]


def seconds(results: dict) -> dict:
    values = [r["seconds"] for r in results.values()]
    tokens = [r["usage"].get("input_tokens") for r in results.values() if r.get("usage")]
    tokens = [t for t in tokens if t is not None]
    pct = lambda v: {q: float(np.percentile(v, q)) for q in (50, 95, 100)} if v else None  # noqa: E731
    return {"n": len(values), "seconds": pct(values), "input_tokens": pct(tokens)}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def select(out: Path) -> None:
    items, results, units, cases, fits = inputs(out, "dev")
    by_q = {q: {i: r["scores"][q] for i, r in results.items()} for q in ("Q1", "Q2")}
    aurocs = {q: s153.auc(*labelled(cases, by_q[q])[:2]) for q in by_q}
    question = s153.select_question(aurocs["Q1"], aurocs["Q2"])
    scores = by_q[question]
    plants = [(scores[c["item"]], c["llm_caught"]) for c in cases if c["role"] == "planted"]
    t_route, t_alt = route_threshold(plants), route_threshold_alt([s for s, _ in plants])
    labels, raw, _ = labelled(cases, scores)
    platt = s153.fit_platt(raw, labels)
    t_d = s153.disputed_threshold([s153.calibrate(platt, r) for r in raw], labels)
    controls = [c for c in cases if c["role"] == "control"]
    originals = {c["case"]: c for c in cases if c["role"] == "original"}
    pairs = [(scores[originals[c["case"]]["item"]], scores[c["item"]]) for c in controls]
    selection = {
        "model": "vllm-sr/d3-flash@67e03e1bc157961c582ee7c6a35d9b15fada3dec",
        "question": question, "dev_auroc": aurocs,
        "t_route": t_route, "t_route_alt": t_alt, "alt_miss": ALT_MISS,
        "platt": platt, "t_d": t_d,
        "control": {"n": len(pairs),
                    "auroc_original_vs_wrong_section": s153.auc(
                        ["correct"] * len(pairs) + ["meaning_changed"] * len(pairs),
                        [o for o, _ in pairs] + [w for _, w in pairs]),
                    "median_original": float(np.median([o for o, _ in pairs])),
                    "median_wrong_section": float(np.median([w for _, w in pairs]))},
        "dev": {"t_route": at(t_route, units, cases, scores, fits),
                "t_route_alt": at(t_alt, units, cases, scores, fits)},
        "token_model": fits,
        "latency_dev_two_questions": seconds(results),
    }  # fmt: skip
    write(HERE / "selection.json", selection)
    write(HERE / "test-launch.json", {
        "selection_sha256": sha(HERE / "selection.json"),
        "test_items": sum(i["split"] == "test" for i in json.loads((out / "items.json").read_text())),
        "question": question, "written": datetime.now(UTC).isoformat(timespec="seconds")})  # fmt: skip
    print(json.dumps({k: selection[k] for k in ("question", "dev_auroc", "t_route", "t_route_alt",
                                                 "t_d", "control")}, indent=1))  # fmt: skip


def evaluate(out: Path) -> None:
    selection = json.loads((HERE / "selection.json").read_text())
    question, platt = selection["question"], selection["platt"]
    items, results, units, cases, fits = inputs(out, "test")
    scores = {i: r["scores"][question] for i, r in results.items()}
    labels, raw, groups = labelled(cases, scores)
    rows = [{"failed": False, "label": lab, "score": s, "group": g}
            for lab, s, g in zip(labels, raw, groups, strict=True)]  # fmt: skip
    calibrated = [s153.calibrate(platt, r) for r in raw]
    flagged = [p <= selection["t_d"] for p in calibrated]
    errors = [lab == "meaning_changed" for lab in labels]
    delivered = [(u["id"], s["final"]) for u in units for s in u["sentences"] if s["final"]]
    marked = [(uid, f) for uid, f in delivered if s153.calibrate(platt, scores[f]) <= selection["t_d"]]
    state = {i["id"]: i["state"] for i in items}
    write(out / "flagged-delivered.json",
          [{"unit": uid, "item": f, "score": scores[f], **state[f]} for uid, f in marked])  # fmt: skip
    grid = sorted({scores[s["item"]] for u in units for s in u["sentences"]}
                  | {scores[c["item"]] for c in cases if c["role"] == "planted"})  # fmt: skip
    curve = []
    for t in grid:
        m = at(t, units, cases, scores, fits)
        curve.append({"t": t, "units_skipped": m["units_skipped"]["value"],
                      "d3_recall": m["d3_recall"]["value"],
                      "overall_catch": m["overall_catch"]["value"]})  # fmt: skip
    steps = json.loads((out / "steps.json").read_text())
    test_papers = sorted({str(u["paper"]) for u in units})
    write(HERE / "metrics.json", {
        "question": question,
        "auroc": s153.auc(labels, raw), "auroc_bootstrap_by_unit": s153.bootstrap_auc(rows),
        "ece": {"raw": s153.ece(raw, labels), "calibrated": s153.ece(calibrated, labels)},
        "t_route": at(selection["t_route"], units, cases, scores, fits),
        "t_route_alt": at(selection["t_route_alt"], units, cases, scores, fits),
        "t_d": {"t": selection["t_d"],
                "labelled_flagged": sum(flagged),
                "precision": s153.rate(sum(f and e for f, e in zip(flagged, errors)), sum(flagged)),
                "recall": s153.rate(sum(f and e for f, e in zip(flagged, errors)), sum(errors)),
                "correct_flagged": s153.rate(sum(f and not e for f, e in zip(flagged, errors)),
                                             len(errors) - sum(errors)),
                "delivered_sentences": len(delivered), "delivered_marked": len(marked)},
        "llm_tokens_test_papers": {step: {k: sum(steps[p].get(step, {}).get(k, 0)
                                                 for p in test_papers)
                                          for k in ("calls", "prompt_tokens", "completion_tokens")}
                                   for step in ("map", "verify", "repair", "reduce")},
        "requests_per_document": len([s for u in json.loads((out / "units.json").read_text())
                                      for s in u["sentences"]]) / 20,
        "latency_test_one_question": seconds(results),
        "curve": curve,
    })  # fmt: skip
    print(json.dumps({"auroc": s153.auc(labels, raw), "marked": len(marked)}))


if __name__ == "__main__":
    {"select": select, "evaluate": evaluate}[sys.argv[1]](Path(sys.argv[2]).expanduser())
