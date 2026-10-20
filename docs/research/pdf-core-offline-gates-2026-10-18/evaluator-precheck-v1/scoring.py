"""Offline numeric scoring from explicit, snapshot-bound source review decisions."""
from decimal import Decimal
from hashlib import sha256
import json
import re


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def numbers(text):
    return [Decimal(v) for v in re.findall(r"[-+]?\d+(?:\.\d+)?", text)]


def reviewed(record):
    return bool(record and record.get("passed") is True and record.get("evidence"))


def score(worksheet, cells, review):
    """Cells come from reloaded Core/rendered output; matching is reviewer input.

    A matching decision is bound to the observed text AND semantic context.
    It never infers source correctness from provider IDs or delivery existence.
    """
    if len({c["locator"] for c in cells}) != len(cells):
        raise ValueError("duplicate delivered cell locator")
    by_locator = {c["locator"]: c for c in cells}
    expected_ids = {p["expected"]["id"] for p in worksheet["points"]}
    if set(review["matches"]) - expected_ids:
        raise ValueError("foreign source point in review")
    required = set(worksheet["manual_structure_review"]) - {"notes"}
    decisions_ok = all(reviewed(review["decisions"].get(k)) for k in required)
    occupied = set()
    values = {}
    errors = 0
    missing_markers_ok = True
    binding_ok = True
    denominator = 0
    for point in worksheet["points"]:
        expected = point["expected"]
        match = review["matches"].get(expected["id"])
        cell = by_locator.get(match.get("locator")) if match else None
        absent = bool(reviewed(match) and match.get("absent") is True and cell is None)
        valid = (reviewed(match) and cell is not None
                 and match.get("observed_sha256") == digest(cell))
        component = match.get("component", 0) if match else 0
        if not isinstance(component, int) or isinstance(component, bool) or component < 0:
            raise ValueError("invalid numeric component")
        if cell is not None:
            slot = (cell["locator"], component)
            if slot in occupied:
                raise ValueError("same delivered component consumed twice")
            occupied.add(slot)
        binding_ok &= bool(valid or absent)
        if expected["value_kind"] != "number":
            missing_markers_ok &= bool(valid and cell["text"].strip() == expected["raw_value"])
            continue
        denominator += 1
        actual = numbers(cell["text"]) if valid else []
        value = actual[component] if len(actual) > component else None
        if value is not None:
            values[expected["id"]] = value
        errors += value != Decimal(expected["decimal_value"])
    extras = sum((c["locator"], i) not in occupied
                 for c in cells for i, _ in enumerate(numbers(c["text"])))
    relations = []
    for comparison in worksheet["comparisons"]:
        e = comparison["expected"]
        left, right = values.get(e["left"]), values.get(e["right"])
        op = None if left is None or right is None else ">" if left > right else "<" if left < right else "="
        relations.append(op == e["operator"])
    limit = Decimal(str(worksheet["acceptance_reference"]["numeric_error_rate_max"]))
    passed = (decisions_ok and binding_ok and missing_markers_ok and denominator > 0
              and Decimal(errors + extras) / denominator <= limit and all(relations))
    return dict(passed=bool(passed), numeric_correct=denominator-errors,
                numeric_denominator=denominator, extra_numeric=extras,
                error_count=errors+extras, comparisons_passed=sum(relations),
                comparisons_denominator=len(relations), structure_review_complete=decisions_ok,
                snapshot_bindings_valid=binding_ok, missing_markers_preserved=missing_markers_ok)


def score_math(observations, decisions):
    """Check completeness of explicit source reviews, not symbolic equivalence."""
    if len(observations) != len(decisions):
        raise ValueError("math source-review denominator mismatch")
    results = [reviewed(d) and d.get("observed_sha256") == digest(o)
               for o, d in zip(observations, decisions, strict=True)]
    return dict(passed=all(results), correct=sum(results), denominator=len(results))
