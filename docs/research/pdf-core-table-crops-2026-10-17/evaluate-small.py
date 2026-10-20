"""Post-run raw and delivered T01/T02 evaluation; never a producer repair."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from decimal import Decimal

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "pdf-core-direct-cell-2026-10-17"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def raw_view(target):
    result = deepcopy(target)
    result["panels"] = []
    for panel in target["panels"]:
        data = panel["data"]
        nr, nc = data["num_rows"], data["num_cols"]
        assert 1 <= nr <= 256 and 1 <= nc <= 64
        grid = [[None for _ in range(nc)] for _ in range(nr)]
        for c in data["table_cells"]:
            r0, r1, c0, c1 = (c[k] for k in ("start_row_offset_idx", "end_row_offset_idx",
                                            "start_col_offset_idx", "end_col_offset_idx"))
            assert 0 <= r0 < r1 <= nr and 0 <= c0 < c1 <= nc
            for r in range(r0, r1):
                for col in range(c0, c1):
                    assert grid[r][col] is None, "overlapping source cells"
                    grid[r][col] = c["text"]
        assert all(v is not None for row in grid for v in row), "missing source cells"
        result["panels"].append({"panel_label": panel["panel_label"], "title": panel["title"],
            "columns": grid[0], "rows": [{"setting": row[0], "values": [
                {"column": grid[0][i], "value": v} for i, v in enumerate(row) if i]} for row in grid[1:]]})
    return result


def ambiguous_ordinary(target, oracle):
    cells = target["panels"][0]["data"]["table_cells"]
    def at(row, col):
        return [c for c in cells if c["start_row_offset_idx"] <= row < c["end_row_offset_idx"]
                and c["start_col_offset_idx"] <= col < c["end_col_offset_idx"]]
    rows = {r["row_id"]: r["context"]["method"] for r in oracle["rows"]}
    points = []
    for point in oracle["expected_datapoints"]:
        header = [c for c in cells if c.get("column_header") and c["text"] == point["column_key"] + "↑"]
        method = [c for c in cells if c.get("row_header") and c["text"] == rows[point["row_id"]]]
        observed, unique = [], False
        if len(header) == len(method) == 1:
            h, m = header[0], method[0]
            observed = at(m["start_row_offset_idx"], h["start_col_offset_idx"])
            unique = len(at(h["start_row_offset_idx"], h["start_col_offset_idx"])) == 1 and len(observed) == 1
        points.append({"id": point["id"], "expected": point["raw_value"],
            "observed_cell_texts": [c["text"] for c in observed],
            "correct_binding": unique and observed[0]["text"] == point["raw_value"],
            "printed_string_present_anywhere": any(c["text"] == point["raw_value"] for c in cells)})
    by_id = {p["id"]: p for p in points}
    comparisons = []
    for comparison in oracle["critical_comparisons"]:
        a, b = by_id[comparison["left"]], by_id[comparison["right"]]
        good = a["correct_binding"] and b["correct_binding"]
        if good:
            left, right = Decimal(a["expected"]), Decimal(b["expected"])
            good = left > right if comparison["operator"] == ">" else left == right
        comparisons.append({**comparison, "passed": good})
    return {"fixed_numeric_denominator": len(points),
        "source_numeric_bindings_correct": sum(p["correct_binding"] for p in points),
        "printed_strings_present_anywhere": sum(p["printed_string_present_anywhere"] for p in points),
        "all_critical_numeric_bindings_preserved": all(c["passed"] for c in comparisons),
        "critical_comparisons": comparisons, "datapoints": points,
        "header_exact": False,
        "note": "B1 and J share declared column2; do not infer new columns from cell-list order. All strings may exist while bindings remain ambiguous."}


def main():
    assert json.loads((HERE / "all-calls-complete.json").read_text())["requests"] == 6
    old = load("frozen_small_eval", OLD / "evaluate-small.py")
    runner = load("frozen_crop_runner", HERE / "run.py")
    runner.verify_frozen()
    cases = {c["id"]: c for c in json.loads(old.ORACLE.read_text())["cases"]}
    result = {"evaluation_after_all_six_calls": True, "new_API_calls": 0,
              "diagnostic_raw_does_not_create_accepted_document": True, "cases": {}, "target_validation": []}
    reg = json.loads((HERE / "registration.json").read_text())
    for job in reg["jobs"]:
        response = json.loads((Path(job["directory"]) / "response.json").read_text())
        content = response["choices"][0]["message"]["content"]
        entry = {"name": job["name"]}
        try:
            runner.parse_target(content, job["target_key"])
            entry["status"] = "valid"
        except ValueError as error:
            entry["status"] = "rejected"
            entry["errors"] = (error.errors(include_url=False, include_context=False, include_input=False)
                               if hasattr(error, "errors") else [str(error)])
        result["target_validation"].append(entry)
    for case_id, page_name, evaluator in (("G1-T01", "memory-r1-p8", old.ordinary),
                                         ("G1-T02", "skillopt-p8", old.previous.evaluate_table)):
        raw = json.loads((HERE / page_name / "table0/content.txt").read_text())
        target = raw["targets"][0]
        view = None if case_id == "G1-T01" else raw_view(target)
        score = (ambiguous_ordinary(target, cases[case_id]["details"]) if view is None
                 else evaluator(view, cases[case_id]["details"]))
        assert score["fixed_numeric_denominator"] == (6 if case_id == "G1-T01" else 84)
        if view is not None:
            changed = deepcopy(view)
            changed["panels"][0]["rows"][0]["values"][0]["value"] = "999"
            assert evaluator(changed, cases[case_id]["details"])["source_numeric_bindings_correct"] < score["source_numeric_bindings_correct"]
        else:
            assert score["source_numeric_bindings_correct"] == 2 and score["printed_strings_present_anywhere"] == 6
        result["cases"][case_id] = {"raw_numeric_evaluation": score,
            "accepted_document_exists": (HERE / page_name / "document.json").exists(),
            "raw_schema_pass_is_separate_from_numeric_score": True}
        if case_id == "G1-T02":
            comparisons = score["critical_comparisons"]
            result["cases"][case_id]["product_acceptance_interpretation"] = {
                "numeric_error_rate": score["error_rate_including_unmatched_extras"],
                "numeric_tolerance_satisfied": score["error_rate_including_unmatched_extras"] <= .05,
                "critical_operator_relations_correct": sum(c["observed_relation_holds"] for c in comparisons),
                "critical_operator_relations_denominator": len(comparisons),
                "extra_exact_endpoint_diagnostic": sum(c["source_values_and_bindings_preserved"] for c in comparisons),
                "note": "Frozen helper requires exact critical endpoints as well as correct relations; the additional exactness condition is not an approved product gate. Keep numeric errors in the84 denominator; caption/conditions and whole-page delivery remain separate."}
            assert result["cases"][case_id]["product_acceptance_interpretation"]["critical_operator_relations_correct"] == 8
    (HERE / "quality-small.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: {"raw_correct": v["raw_numeric_evaluation"]["source_numeric_bindings_correct"],
                         "accepted_document_exists": v["accepted_document_exists"]} for k, v in result["cases"].items()}))


if __name__ == "__main__":
    main()
