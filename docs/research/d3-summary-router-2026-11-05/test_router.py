"""router.py's own logic (score.py is #153's, tested there).

    .venv/bin/python -m pytest docs/research/d3-summary-router-2026-11-05/test_router.py
"""

import numpy as np
import router


def test_route_threshold_flags_every_plant_the_llm_catches():
    plants = [(0.1, True), (0.7, True), (0.9, False), (0.4, True)]
    t = router.route_threshold(plants)
    assert t == 0.7
    assert all(s <= t for s, caught in plants if caught)


def test_route_threshold_alt_lets_at_most_five_percent_through():
    scores = [i / 45 for i in range(45)]
    t = router.route_threshold_alt(scores)
    assert sum(s > t for s in scores) == 2  # floor(0.05 * 45)
    assert router.route_threshold_alt([0.5] * 10) == 0.5  # ties are flagged (score <= t)


def unit(uid, kind, items, flagged=(), finals=None, repair=(), reverify=()):
    finals = finals or items
    return {"id": uid, "paper": 1, "kind": kind, "verify_chars": 1000,
            "sentences": [{"item": i, "llm_flagged": i in flagged, "final": f}
                          for i, f in zip(items, finals, strict=True)],
            "repair_chars": list(repair), "reverify_chars": list(reverify)}  # fmt: skip


FITS = {"verify_prompt": {"coef": [100, 0.25]}, "verify_completion": {"coef": [10, 50]},
        "repair_prompt": {"coef": [80, 0.25]}, "repair_completion": {"coef": [40]}}  # fmt: skip


def test_at_routes_units_and_counts_catches():
    units = [unit("1:s0", "section", ["a", "b"], flagged=["b"], repair=[400], reverify=[200]),
             unit("1:s1", "section", ["c"]), unit("1:o0", "overview", ["d"])]  # fmt: skip
    cases = [
        {"case": "x", "role": "original", "item": "a", "llm_caught": False, "unit": "1:s0"},
        {"case": "x", "role": "planted", "item": "p", "llm_caught": True, "mates": ["b"],
         "unit": "1:s0"},
        {"case": "y", "role": "original", "item": "c", "llm_caught": True, "unit": "1:s1"},
        {"case": "y", "role": "planted", "item": "q", "llm_caught": True, "mates": [],
         "unit": "1:s1"},
    ]  # fmt: skip
    scores = {"a": 0.9, "b": 0.3, "c": 0.8, "d": 0.95, "p": 0.6, "q": 0.2}
    m = router.at(0.5, units, cases, scores, FITS)
    assert m["d3_recall"]["k"] == 1  # q only; p scores above t
    assert m["overall_catch"]["k"] == 1
    assert m["overall_catch_unit"]["k"] == 2  # p's batch-mate b sends its Section to the LLM
    assert m["units_skipped"]["k"] == 2 and m["units_skipped"]["n"] == 3  # s1 and o0
    assert m["units_skipped_by_kind"]["overview"]["k"] == 1
    assert m["false_drop"]["k"] == 0  # c's unit is skipped, so the LLM never drops it
    assert m["llm_alone_false_drop"]["k"] == 1
    assert m["llm_flagged_still_routed"]["k"] == 1  # b is flagged by d3 too
    first_s1 = 100 + 0.25 * 1000 + 10 + 50 * 1
    first_o0 = first_s1
    assert m["tokens_saved"]["first_verify"] == first_s1 + first_o0
    after_s0 = (80 + 0.25 * 400 + 40) + (100 + 0.25 * 200 + 10 + 50)
    assert m["tokens_modelled"]["after"] == after_s0 and m["tokens_saved"]["after"] == 0


def test_fit_tokens_recovers_an_exact_linear_model():
    rng = np.random.default_rng(0)
    units, steps = [], {}
    for p in range(1, 6):
        us = [{"paper": p, "sentences": [{}] * int(rng.integers(1, 5)),
               "verify_chars": int(rng.integers(500, 9000)),
               "repair_chars": [int(rng.integers(500, 9000))] * int(rng.integers(0, 2)),
               "reverify_chars": []} for _ in range(int(rng.integers(3, 9)))]  # fmt: skip
        for u in us:
            u["reverify_chars"] = [c // 2 for c in u["repair_chars"]]
        units += us
        calls = sum(1 + len(u["reverify_chars"]) for u in us)
        chars = sum(u["verify_chars"] + sum(u["reverify_chars"]) for u in us)
        judged = sum(len(u["sentences"]) + len(u["reverify_chars"]) for u in us)
        repairs = sum(len(u["repair_chars"]) for u in us)
        rchars = sum(sum(u["repair_chars"]) for u in us)
        steps[str(p)] = {
            "verify": {"calls": calls, "prompt_tokens": 300 * calls + 0.3 * chars,
                       "completion_tokens": 20 * calls + 60 * judged},
            "repair": {"calls": repairs, "prompt_tokens": 250 * repairs + 0.3 * rchars + 1,
                       "completion_tokens": 90 * repairs + 1},
        }  # fmt: skip
    fits = router.fit_tokens(steps, units)
    assert np.allclose(fits["verify_prompt"]["coef"], [300, 0.3])
    assert np.allclose(fits["verify_completion"]["coef"], [20, 60])
    assert fits["verify_prompt"]["max_relative_error"] < 1e-9
