"""#174 router: the dev choices of format, rule and threshold, then the one held-out evaluation.

    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/router.py subset OUT
    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/router.py format OUT
    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/router.py select OUT
    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/router.py launch OUT
    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/router.py evaluate OUT

The rules are freeze.md §4–§6. A sentence's score is high when d3 finds it supported: G is
P(yes) of the general question; T is 1 - max P(yes) of the targeted questions (C, S, Q, E ask
whether the sentence adds an error of that kind); M is min(G, T). A unit goes to the LLM when
any of its sentences scores at most t (#166's A2). Natural errors are the review's confirmed
candidates (OUT/SPLIT/confirmed.json); the threshold rule counts those the LLM verify flagged.
#166's router.py supplies every router number at a threshold (at) and the token model.
"""

import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from inputs import v1  # noqa: E402

V1R = v1("router")
s153 = V1R.s153
RULES = {"G": ["G"], "T": list("CSQE"), "M": list("GCSQE")}  # simplest first: ties go to it
MISS, GATE, TIE, FORMAT_MARGIN = 0.05, 0.30, 0.01, 0.01


def rule_score(rule: str, q: dict[str, float]) -> float:
    targeted = 1 - max(q[x] for x in "CSQE") if rule != "G" else None
    return {"G": lambda: q["G"], "T": lambda: targeted, "M": lambda: min(q["G"], targeted)}[rule]()


def route_threshold(unit_min: dict[str, float], natural_units: list[str], allowed: int) -> float:
    """The lowest t at which at most `allowed` natural errors sit in a skipped unit: a unit is
    routed when its lowest score is at most t, so raising t only routes more units."""
    for t in sorted(set(unit_min.values())):
        if sum(unit_min[u] > t for u in natural_units) <= allowed:
            return t
    raise AssertionError("unreachable: the highest unit score routes every unit")


def load(out: Path, split: str, name: str):
    return json.loads((out / split / f"{name}.json").read_text())


def scores(out: Path, run: str) -> dict[str, dict[str, float]]:
    merged: dict[str, dict[str, float]] = {}
    for p in sorted((out / "runs" / run / "groups").glob("*.json")):
        for item, q in json.loads(p.read_text())["scores"].items():
            assert item not in merged, item
            merged[item] = q
    return merged


def labelled(cases: list[dict], confirmed: set[str]) -> tuple[list[str], list[str], list[str]]:
    """Items, labels (correct / meaning_changed) and bootstrap groups (units)."""
    # t5b labels every original correct by default; a review that confirms one as an error wins
    originals = [c for c in cases if c["role"] == "original" and c["item"] not in confirmed]
    errors = [(c["item"], c["unit"]) for c in cases if c["role"] == "planted"]
    rows = [(c["item"], "correct", c["unit"]) for c in originals]
    rows += [(i, "meaning_changed", u) for i, u in errors]
    rows += [(i, "meaning_changed", f"natural:{i}") for i in sorted(confirmed)]
    return [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]


def natural_units(units: list[dict], confirmed: set[str]) -> list[str]:
    """The unit of every confirmed natural error the LLM verify flagged (one entry per error)."""
    return [u["id"] for u in units for s in u["sentences"] if s["llm_flagged"] and s["item"] in confirmed]


def evaluate_rule(rule: str, t: float, q: dict, units: list[dict], cases: list[dict], fits: dict,
                  confirmed: set[str]) -> dict:  # fmt: skip
    score = {i: rule_score(rule, v) for i, v in q.items()}
    unit_min = {u["id"]: min(score[s["item"]] for s in u["sentences"]) for u in units}
    natural = natural_units(units, confirmed)
    items, labels, _ = labelled(cases, confirmed)
    plant_items = {c["item"] for c in cases if c["role"] == "planted"}
    m = V1R.at(t, units, cases, score, fits)
    return {
        "t": t,
        "units_skipped": m["units_skipped"], "units_skipped_by_kind": m["units_skipped_by_kind"],
        "natural_still_routed": s153.rate(sum(unit_min[u] <= t for u in natural), len(natural)),
        "auroc_natural": s153.auc(*zip(*[(lab, score[i]) for i, lab in zip(items, labels, strict=True)
                                         if i not in plant_items])),
        "auroc_planted": s153.auc(*zip(*[(lab, score[i]) for i, lab in zip(items, labels, strict=True)
                                         if i not in confirmed])),
        "planted_d3_recall": m["d3_recall"], "planted_overall_catch": m["overall_catch"],
        "planted_llm_alone_catch": m["llm_alone_catch"],
        "false_drop": m["false_drop"], "llm_alone_false_drop": m["llm_alone_false_drop"],
        "tokens_saved": m["tokens_saved"], "tokens_modelled": m["tokens_modelled"],
    }  # fmt: skip


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def subset(out: Path) -> None:
    key = json.loads((out / "dev" / "review" / "key.json").read_text())
    items = {k["item"] for k in key.values() if k["role"] == "candidate"}
    items |= {c["item"] for c in load(out, "dev", "cases")}
    write(out / "dev" / "format-subset.json", sorted(items))
    print(json.dumps({"format_subset": len(items)}))


def format_choice(out: Path) -> None:
    confirmed = set(load(out, "dev", "confirmed"))
    items, labels, _ = labelled(load(out, "dev", "cases"), confirmed)
    auroc = {}
    for fmt in ("json", "text"):
        q = scores(out, f"fmt-{fmt}")
        assert set(items) <= set(q), fmt
        auroc[fmt] = s153.auc(labels, [q[i]["G"] for i in items])
    chosen = "text" if auroc["text"] >= auroc["json"] + FORMAT_MARGIN else "json"
    write(HERE / "format.json", {"format": chosen, "auroc_G": auroc, "margin": FORMAT_MARGIN,
                                 "labelled": {lab: labels.count(lab) for lab in set(labels)}})  # fmt: skip
    print(json.dumps({"format": chosen, "auroc_G": auroc}))


def select(out: Path) -> None:
    units, cases = load(out, "dev", "units"), load(out, "dev", "cases")
    confirmed = set(load(out, "dev", "confirmed"))
    q = scores(out, "dev")
    fits = V1R.fit_tokens(load(out, "dev", "steps"), units)
    natural = natural_units(units, confirmed)
    allowed = math.floor(MISS * len(natural))
    per_rule = {}
    for rule in RULES:
        score = {i: rule_score(rule, v) for i, v in q.items()}
        unit_min = {u["id"]: min(score[s["item"]] for s in u["sentences"]) for u in units}
        t = route_threshold(unit_min, natural, allowed)
        per_rule[rule] = evaluate_rule(rule, t, q, units, cases, fits, confirmed)
    best = max(per_rule[r]["units_skipped"]["value"] for r in RULES)
    rule = next(r for r in RULES if per_rule[r]["units_skipped"]["value"] >= best - TIE)
    skipped = per_rule[rule]["units_skipped"]["value"]
    selection = {
        "model": "vllm-sr/d3-flash@67e03e1bc157961c582ee7c6a35d9b15fada3dec",
        "format": json.loads((HERE / "format.json").read_text())["format"],
        "rule": rule, "questions": RULES[rule], "t_route": per_rule[rule]["t"],
        "natural_errors": len(natural), "allowed_misses": allowed,
        "gate": {"bar": GATE, "units_skipped": skipped, "passed": skipped >= GATE},
        "dev": per_rule, "token_model": fits,
    }  # fmt: skip
    write(HERE / "selection.json", selection)
    print(json.dumps({k: selection[k] for k in ("format", "rule", "t_route", "natural_errors",
                                                 "allowed_misses", "gate")}))  # fmt: skip


def launch(out: Path) -> None:
    assert json.loads((HERE / "selection.json").read_text())["gate"]["passed"], "the gate failed"
    write(HERE / "test-launch.json", {
        "selection_sha256": sha(HERE / "selection.json"),
        "heldout_requests_sha256": sha(out / "heldout" / "requests.json"),
        "written": datetime.now(UTC).isoformat(timespec="seconds")})  # fmt: skip


def evaluate(out: Path) -> None:
    selection = json.loads((HERE / "selection.json").read_text())
    rule, t = selection["rule"], selection["t_route"]
    units, cases = load(out, "heldout", "units"), load(out, "heldout", "cases")
    confirmed = set(load(out, "heldout", "confirmed"))
    q = scores(out, "test")
    fits = V1R.fit_tokens(load(out, "heldout", "steps"), units)
    result = evaluate_rule(rule, t, q, units, cases, fits, confirmed)
    score = {i: rule_score(rule, v) for i, v in q.items()}
    items, labels, groups = labelled(cases, confirmed)
    result["auroc_all_bootstrap_by_unit"] = s153.bootstrap_auc(
        [{"failed": False, "label": lab, "score": score[i], "group": g}
         for i, lab, g in zip(items, labels, groups, strict=True)])  # fmt: skip
    unit_min = {u["id"]: min(score[s["item"]] for s in u["sentences"]) for u in units}
    natural = natural_units(units, confirmed)
    result["curve"] = [{"t": c, "units_skipped": sum(m > c for m in unit_min.values()) / len(unit_min),
                        "natural_still_routed": sum(unit_min[u] <= c for u in natural) / len(natural)}
                       for c in sorted(set(unit_min.values()))]  # fmt: skip
    write(HERE / "metrics.json", {"rule": rule, "format": selection["format"], **result})
    print(json.dumps({k: result[k] for k in ("units_skipped", "natural_still_routed",
                                             "planted_overall_catch", "auroc_natural")}))  # fmt: skip


if __name__ == "__main__":
    {"subset": subset, "format": format_choice, "select": select, "launch": launch,
     "evaluate": evaluate}[sys.argv[1]](Path(sys.argv[2]).expanduser())  # fmt: skip
