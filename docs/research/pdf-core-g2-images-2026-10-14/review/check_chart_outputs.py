"""Offline numeric/binding checks for the four frozen chart outputs; no inference."""
import copy
import hashlib
import json
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = HERE.parent
CASES_PATH = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
CASES = {case["id"]: case for case in json.loads(CASES_PATH.read_text())["cases"]}


def number(value, pie=False):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value if math.isfinite(value) else None
    if pie and isinstance(value, str):
        match = re.fullmatch(r"(?:about\s+)?([0-9]+(?:\.[0-9]+)?)%", value)
        return float(match[1]) if match else None
    return None


def check(case_id, output):
    oracle = CASES[case_id]["details"]["oracle"]
    truth = oracle["data"]
    rows = output.get("data", [])
    if case_id == "G1-C03":
        expected = list(zip(truth["categories"], truth["values"]))
        key = lambda row: row.get("category")
    elif case_id == "G1-C04":
        expected = [((series, x), y) for series, values in truth["series"].items()
                    for x, y in zip(truth["x"], values)]
        key = lambda row: (row.get("series"), number(row.get("x")))
    elif case_id == "G1-C05":
        expected = list(zip(truth["x"], truth["values"]))
        key = lambda row: number(row.get("x"))
    else:
        expected = list(zip(truth["categories"], truth["percent"]))
        key = lambda row: row.get("category")
    points = []
    values = {}
    for association, target in expected:
        matches = [row for row in rows if key(row) == association]
        row = matches[0] if len(matches) == 1 else {}
        value = number(row.get("value"), pie=case_id == "G1-C06")
        if value is None:
            error, limit = None, None
            numeric_ok = False
        elif case_id == "G1-C03":
            error, limit = abs(value - target), 0
            numeric_ok = error == 0
        elif case_id == "G1-C04":
            error = abs(value - target) / (truth["y_domain"][1] - truth["y_domain"][0])
            limit = oracle["max_position_error_as_axis_length"]
            numeric_ok = error <= limit + 1e-12
        elif case_id == "G1-C05":
            span = math.log10(truth["y_domain"][1]) - math.log10(truth["y_domain"][0])
            error = abs(math.log10(value) - math.log10(target)) / span if value > 0 else None
            limit = oracle["max_position_error_as_axis_length"]
            numeric_ok = error is not None and error <= limit + 1e-12
        else:
            error, limit = abs(value - target), oracle["max_error_percentage_points_per_sector"]
            numeric_ok = error <= limit + 1e-12
        expected_status = "printed" if truth["printed"] else "estimated"
        unit_ok = output.get("unit") is None if case_id == "G1-C05" else output.get("unit") == "%"
        if case_id == "G1-C06":
            unit_ok = unit_ok or isinstance(row.get("value"), str) and row["value"].endswith("%")
        points.append({"association": association, "expected": target,
                       "provider_value": row.get("value"), "review_numeric_value": value,
                       "binding_matches_once": len(matches) == 1, "numeric_ok": numeric_ok,
                       "normalized_axis_error_or_percentage_point_error": error, "allowed_error": limit,
                       "status_ok": row.get("value_status") == expected_status, "unit_ok": unit_ok})
        values[association] = value
    y_axis = output.get("axes", {}).get("y", {})
    axis_ok = True
    if case_id in ["G1-C03", "G1-C04"]:
        axis_ok = y_axis.get("label") == "Score (%)" and y_axis.get("scale") == "linear"
    elif case_id == "G1-C05":
        axis_ok = y_axis.get("label") == "Value (log10)" and "log" in (y_axis.get("scale") or "").lower()
    if case_id in ["G1-C04", "G1-C05"]:
        axis_ok = axis_ok and output.get("axes", {}).get("x", {}).get("label") == "Step"
    comparable = all(value is not None for value in values.values())
    critical = []
    if comparable and case_id == "G1-C03":
        critical = [values["B"] > values["A"]]
    elif comparable and case_id == "G1-C04":
        critical = [values[("Orange", 1)] > values[("Blue", 1)],
                    abs(values[("Blue", 2)] - values[("Orange", 2)]) <= 1e-12,
                    values[("Blue", 3)] > values[("Orange", 3)]]
    elif comparable and case_id == "G1-C05":
        critical = [axis_ok and all(point["numeric_ok"] for point in points),
                    all(point["binding_matches_once"] for point in points)]
    elif comparable:
        critical = [values["B"] > values["A"], all(point["numeric_ok"] for point in points)]
    added_points = max(0, len(rows) - len(expected))
    numeric_errors = sum(not point["numeric_ok"] for point in points) + added_points
    passed = (numeric_errors == 0 and len(rows) == len(expected) and axis_ok and all(critical)
              and all(p["binding_matches_once"] and p["status_ok"] and p["unit_ok"] for p in points))
    return {"case_id": case_id, "fixed_numeric_denominator": len(expected),
            "observed_rows": len(rows), "added_numeric_rows": added_points,
            "numeric_errors": numeric_errors, "axis_labels_and_scale_ok": axis_ok,
            "critical_comparison_checks": critical,
            "source_critical_comparisons": oracle["critical_comparisons"],
            "critical_semantics_note": "Step2 tie is checked directly. Manual review also checks tie wording and factor10 meaning; numeric tolerances do not replace semantic checks.",
            "points": points, "passed": passed}


def main():
    outputs = {case_id: json.loads((BASE / "api" / case_id.lower() / "output.json").read_text())
               for case_id in ["G1-C03", "G1-C04", "G1-C05", "G1-C06"]}
    results = [check(case_id, output) for case_id, output in outputs.items()]
    assert sum(r["fixed_numeric_denominator"] for r in results) == 13
    assert all(r["passed"] for r in results)
    controls = []

    def mutation(name, case_id, mutate):
        changed = copy.deepcopy(outputs[case_id])
        mutate(changed)
        verdict = check(case_id, changed)
        assert not verdict["passed"], name
        controls.append({"control": name, "case_id": case_id, "expected": "reject",
                         "rejected": True, "numeric_errors": verdict["numeric_errors"],
                         "status_errors": sum(not p["status_ok"] for p in verdict["points"])})

    mutation("wrong_printed_value", "G1-C03", lambda o: o["data"][0].update(value=11))
    mutation("swapped_Blue_Orange", "G1-C04", lambda o: [r.update(series="Orange" if r["series"] == "Blue" else "Blue") for r in o["data"]])
    mutation("log_midpoint_as_linear", "G1-C05", lambda o: o["data"][1].update(value=50.5))
    mutation("estimated_labeled_printed", "G1-C04", lambda o: o["data"][0].update(value_status="printed"))
    mutation("pie_A_B_swapped", "G1-C06", lambda o: [r.update(category="B" if r["category"] == "A" else "A") for r in o["data"]])
    mutation("unequal_step2_tie_within_tolerance", "G1-C04", lambda o: [o["data"][i].update(value=v) for i, v in [(1, 52), (4, 48)]])
    mutation("invented_log_percentage_unit", "G1-C05", lambda o: o.update(unit="%"))
    for case_id, allowed, outside in [("G1-C04", 2, 2.01), ("G1-C05", 10 * 10 ** .04, 10 * 10 ** .0401), ("G1-C06", "about 27%", "about 27.01%")]:
        changed = copy.deepcopy(outputs[case_id])
        index = 1 if case_id == "G1-C05" else 0
        changed["data"][index]["value"] = allowed
        assert check(case_id, changed)["passed"], (case_id, "inclusive boundary")
        changed["data"][index]["value"] = outside
        assert not check(case_id, changed)["passed"], (case_id, "outside boundary")
    report = {"format": "g2-offline-chart-check-v1", "scope": "Current saved output schema; numeric/binding/status/unit checks plus manual source-semantic review. Not Canonical acceptance.",
              "frozen_cases_path": str(CASES_PATH.relative_to(REPO)),
              "frozen_cases_sha256": hashlib.sha256(CASES_PATH.read_bytes()).hexdigest(),
              "results": results, "fixed_numeric_observations": 13,
              "negative_controls": controls, "inclusive_tolerance_boundary_controls": "3 passed/3 outside rejected",
              "provider_mutations": False}
    (HERE / "chart-checks.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"chart_cases_passed": len(results), "numeric_errors": sum(r["numeric_errors"] for r in results),
                      "fixed_numeric_observations": 13, "negative_controls_rejected": len(controls)}))


if __name__ == "__main__":
    main()
