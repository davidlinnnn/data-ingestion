"""#174 post hoc (report §2.4, not registered): rules T and M on held-out, from the explore run.

    .venv/bin/python docs/research/d3-summary-router-v2-2026-11-08/explore.py OUT

Merges the test run (G) and the explore run (C, S, Q, E). For each rule: the held-out numbers
at the threshold dev chose for that rule (selection.json), and from the held-out curve the most
units skipped with at most 5% (and 10%) of the confirmed natural errors skipped. Also the
natural errors G skipped at its t_route, and how many of them each rule routes. Writes
explore.json here.
"""

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from router import (MISS, RULES, evaluate_rule, fold_resends, load, natural_units,  # noqa: E402
                    route_threshold, rule_score, scores, V1R, write)  # fmt: skip


def main(out: Path) -> None:
    selection = json.loads((HERE / "selection.json").read_text())
    units, cases = load(out, "heldout", "units"), load(out, "heldout", "cases")
    confirmed = set(load(out, "heldout", "confirmed"))
    g, rest = scores(out, "test"), scores(out, "explore")
    assert set(g) == set(rest)
    q = {i: g[i] | rest[i] for i in g}
    fits = V1R.fit_tokens(fold_resends(load(out, "heldout", "steps"), units)[0], units)
    natural = natural_units(units, confirmed)
    unit_min = {r: {u["id"]: min(rule_score(r, q[s["item"]]) for s in u["sentences"]) for u in units}
                for r in RULES}  # fmt: skip
    t_g = selection["t_route"]
    missed_by_g = [u for u in natural if unit_min["G"][u] > t_g]
    result = {"natural_errors": len(natural), "g_skipped_natural": len(missed_by_g), "rules": {}}
    for r in RULES:
        t_dev = selection["dev"][r]["t"]
        m = evaluate_rule(r, t_dev, q, units, cases, fits, confirmed)
        best = {}
        for miss in (MISS, 0.10):
            t = route_threshold(unit_min[r], natural, math.floor(miss * len(natural)))
            best[str(miss)] = {"t": t, "units_skipped": sum(v > t for v in unit_min[r].values()) / len(units)}
        result["rules"][r] = {
            "at_dev_threshold": {k: m[k] for k in ("t", "units_skipped", "natural_still_routed",
                                                    "auroc_natural", "auroc_planted",
                                                    "planted_overall_catch", "tokens_saved")},
            "best_on_heldout": best,
            "routes_of_g_skipped": sum(unit_min[r][u] <= t_dev for u in missed_by_g),
        }  # fmt: skip
    write(HERE / "explore.json", result)
    for r, v in result["rules"].items():
        d = v["at_dev_threshold"]
        print(r, round(d["units_skipped"]["value"], 3), d["natural_still_routed"]["k"], "/",
              d["natural_still_routed"]["n"], round(d["auroc_natural"], 3), v["best_on_heldout"],
              "g-skipped routed:", v["routes_of_g_skipped"])  # fmt: skip


if __name__ == "__main__":
    main(Path(sys.argv[1]).expanduser())
