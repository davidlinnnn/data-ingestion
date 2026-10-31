"""Enrichment Status rule v1 (v2 §7) as a table: outcome record -> (status, status_reason)."""

import pytest

from kp_processing.status_rules import v1


def record(outcome="success", reason=None, contradictions=()):
    return {"outcome": outcome, "reason": reason, "contradictions": list(contradictions),
            "signals": {"indent_quantized": False}}  # fmt: skip


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (record(), ("unverified", None)),
        (record("no_text"), ("unverified", "NO_TEXT")),
        (record("failed", "RENDER_FAILED"), ("failed", "RENDER_FAILED")),
        (record("failed", "SERVICE_UNAVAILABLE"), ("failed", "SERVICE_UNAVAILABLE")),
        (record(contradictions=["FORMULA_NUMBER_MISMATCH"]),
         ("disputed", "FORMULA_NUMBER_MISMATCH")),
        (record(contradictions=["UNSUPPORTED_SENTENCE", "FORMULA_OPERATOR_MISMATCH"]),
         ("disputed", "UNSUPPORTED_SENTENCE")),
        # No output beats a contradiction: there is nothing left to dispute.
        (record("failed", "SCHEMA_INVALID", ["FORMULA_NUMBER_MISMATCH"]),
         ("failed", "SCHEMA_INVALID")),
    ],
)  # fmt: skip
def test_v1_assigns_status_from_the_outcome_record(outcome, expected):
    assert v1.assign(outcome) == expected


def test_v1_never_produces_verified_and_weak_signals_do_not_change_status():
    quiet = record()
    loud = {**record(), "signals": {"indent_quantized": True, "agreement": 1.0}}

    assert v1.assign(quiet) == v1.assign(loud) == ("unverified", None)
