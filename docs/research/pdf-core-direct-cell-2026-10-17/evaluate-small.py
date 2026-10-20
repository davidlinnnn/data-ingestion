"""Post-run T01/T02 evaluator; never imported by the frozen producer."""
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument, RefItem

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ORACLE = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
OLD = ROOT / "docs/research/pdf-core-g2-api-2026-10-14/review/evaluate.py"
spec = importlib.util.spec_from_file_location("frozen_skill_evaluator", OLD)
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)


def view(name):
    doc = DoclingDocument.model_validate_json((HERE/name/"document.json").read_text())
    binding = json.loads((HERE/name/"bindings.json").read_text())[0]
    result = deepcopy(binding["provider"])
    result["panels"] = []
    for source, refs in zip(binding["provider"]["panels"], binding["panels"], strict=True):
        table = RefItem(cref=refs["table_ref"]).resolve(doc)
        grid = table.data.grid
        assert all(c.column_header for c in grid[0])
        assert all(row[0].row_header for row in grid[1:])
        result["panels"].append({"panel_label": source["panel_label"], "title": source["title"],
            "columns": [c.text for c in grid[0]],
            "rows": [{"setting": row[0].text,
                "values": [{"column": grid[0][i].text, "value": c.text} for i, c in enumerate(row) if i]}
                for row in grid[1:]]})
    return result


def ordinary(result, oracle):
    expected_rows = {r["row_id"]: r["context"]["method"] for r in oracle["rows"]}
    actual = defaultdict(list)
    panel = result["panels"][0]
    for row in panel["rows"]:
        for value in row["values"]:
            actual[row["setting"], value["column"].removesuffix("↑")].append(value["value"])
    points = []
    accepted = {}
    expected_keys = set()
    for p in oracle["expected_datapoints"]:
        key = (expected_rows[p["row_id"]], p["column_key"])
        expected_keys.add(key)
        values = actual.get(key, [])
        correct = len(values) == 1 and previous.decimal(values[0]) == Decimal(p["decimal_value"])
        accepted[p["id"]] = (correct, previous.decimal(values[0]) if len(values) == 1 else None)
        points.append({"id": p["id"], "binding": list(key), "expected": p["raw_value"],
            "observed": values, "correct": correct, "printed_exact": values == [p["raw_value"]]})
    critical = []
    for c in oracle["critical_comparisons"]:
        a, b = accepted[c["left"]], accepted[c["right"]]
        good = a[0] and b[0] and (a[1] > b[1] if c["operator"] == ">" else a[1] == b[1])
        critical.append({**c, "passed": good})
    extras = sum(len(v) for k, v in actual.items() if k not in expected_keys)
    return {"fixed_numeric_denominator": len(points),
        "source_numeric_bindings_correct": sum(p["correct"] for p in points),
        "printed_numeric_strings_exact": sum(p["printed_exact"] for p in points),
        "extra_numeric_observations": extras, "all_critical_numeric_bindings_preserved": all(c["passed"] for c in critical),
        "critical_comparisons": critical, "header_exact": panel["columns"] == [h["raw_text"] for h in oracle["headers"]],
        "datapoints": points}


def main():
    observations = json.loads((HERE/"live-observations.json").read_text())
    assert len(observations) == 4 and all("seconds" in o for o in observations)
    cases = {c["id"]: c for c in json.loads(ORACLE.read_text())["cases"]}
    t01, t02 = view("memory-r1-p8"), view("skillopt-p8")
    q1 = ordinary(t01, cases["G1-T01"]["details"])
    q2 = previous.evaluate_table(t02, cases["G1-T02"]["details"])
    # Evaluator sensitivity: changing a value or its row context cannot still pass.
    changed = deepcopy(t01)
    changed["panels"][0]["rows"][0]["values"][0]["value"] = "999"
    assert ordinary(changed, cases["G1-T01"]["details"])["source_numeric_bindings_correct"] == 5
    changed = deepcopy(t02)
    changed["panels"][1]["rows"][3]["setting"] = "5"
    assert previous.evaluate_table(changed, cases["G1-T02"]["details"])["source_numeric_bindings_correct"] < 84
    result = {"evaluation_only_after_all_four_calls": True,
        "oracle_sha256": hashlib.sha256(ORACLE.read_bytes()).hexdigest(),
        "reconstructed_from_saved_typed_cells": True, "new_API_calls": 0,
        "G1-T01": q1, "G1-T02": q2,
        "manual_source_review": {
            "G1-T01": "All headers/arrows, method labels and6values match the full-page image. No unit/model added from neighboring figures.",
            "G1-T02": "All6panel labels/titles, literal Setting headers and84values match source; Table3 remains separate. Visible caption retains4:1:5 and training-subset conditions. All unit spans correct."}}
    (HERE/"quality-small.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"T01": {k:q1[k] for k in ("source_numeric_bindings_correct", "header_exact", "all_critical_numeric_bindings_preserved")},
        "T02": {k:q2[k] for k in ("source_numeric_bindings_correct", "panel_header_issues", "all_critical_numeric_bindings_preserved")}}))


if __name__ == "__main__":
    main()
