"""score.py's verdict resolution, from hand-worked answers.

    .venv/bin/python -m pytest docs/validation/199/test_score.py
"""

import score


def test_each_answer_gets_t4s_verdict_this_runs_verdict_fail_or_waits_for_judging():
    recorded = {"latex": "a + b"}
    judged = {"p01-x": {"verdicts": {score.answer_sha("a-b"): "FAIL"}}}
    # the recorded text, whitespace aside, keeps t4's verdict; no answer is FAIL
    found, todo = score.verdicts("p01-x", {"recorded": recorded, "alone": {"latex": "a+b"},
                                           "workflow": None}, "latex", "PASS", judged)  # fmt: skip
    assert (found, todo) == ({"alone": "PASS", "workflow": "FAIL"}, [])
    # an answer judged in this run keeps that verdict, whatever its whitespace
    found, todo = score.verdicts("p01-x", {"recorded": recorded, "alone": {"latex": "a - b"},
                                           "workflow": {"latex": ""}}, "latex", "PASS", judged)  # fmt: skip
    assert (found, todo) == ({"alone": "FAIL", "workflow": "FAIL"}, [])
    # a new answer waits, once even when both roles gave it
    found, todo = score.verdicts("p01-x", {"recorded": recorded, "alone": {"latex": "2a"},
                                           "workflow": {"latex": "2 a"}}, "latex", "PASS", judged)  # fmt: skip
    assert found == {"alone": None, "workflow": None}
    assert todo == [(score.answer_sha("2a"), {"latex": "2a"})]
