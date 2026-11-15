import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from router import fold_resends, route_threshold, rule_score  # noqa: E402


def test_rule_scores():
    q = {"G": 0.9, "C": 0.1, "S": 0.4, "Q": 0.2, "E": 0.05}
    assert rule_score("G", q) == 0.9
    assert abs(rule_score("T", q) - 0.6) < 1e-12  # 1 - max targeted
    assert abs(rule_score("M", q) - 0.6) < 1e-12


def test_threshold_allows_misses():
    unit_min = {"a": 0.2, "b": 0.5, "c": 0.8, "d": 0.95}
    natural = ["a", "b", "c"]  # one error each in a, b, c
    assert route_threshold(unit_min, natural, 0) == 0.8  # every natural error routed
    assert route_threshold(unit_min, natural, 1) == 0.5  # c may be skipped
    assert route_threshold(unit_min, natural, 3) == 0.2  # lowest score: the most skipped


def test_threshold_counts_each_error():
    unit_min = {"a": 0.3, "b": 0.9}
    assert route_threshold(unit_min, ["b", "b"], 1) == 0.9  # two errors in b: skipping b loses both


def test_fold_resends_keeps_tokens():
    steps = {"1": {"repair": {"calls": 3, "prompt_tokens": 90}}, "2": {"verify": {"calls": 1}}}
    units = [{"paper": 1, "repair_chars": [10, 20]}, {"paper": 2, "repair_chars": []}]
    folded, resends = fold_resends(steps, units)
    assert resends == {"1": 1} and folded["1"]["repair"] == {"calls": 2, "prompt_tokens": 90}
    assert steps["1"]["repair"]["calls"] == 3  # the input is not changed
