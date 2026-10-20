"""Post-all-calls diagnostics for T04; never repair a producer grid or accept a page."""
from decimal import Decimal, InvalidOperation
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREVIOUS = HERE.parent / "pdf-core-direct-cell-2026-10-17"
sys.path.insert(0, str(PREVIOUS))
spec = importlib.util.spec_from_file_location("previous_t04_diagnostics", PREVIOUS / "evaluate-t04.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


def norm(text):
    return " ".join(text.split()).casefold()


def number(text):
    try:
        return Decimal(text).is_finite()
    except (InvalidOperation, TypeError):
        return False


def cells_at(data, row, col):
    return [c for c in data["table_cells"] if all(k in c for k in (
        "start_row_offset_idx", "end_row_offset_idx", "start_col_offset_idx", "end_col_offset_idx"))
        and c["start_row_offset_idx"] <= row < c["end_row_offset_idx"]
        and c["start_col_offset_idx"] <= col < c["end_col_offset_idx"]]


def grid_diagnostics(data):
    complete = [c for c in data["table_cells"] if all(k in c for k in (
        "start_row_offset_idx", "end_row_offset_idx", "start_col_offset_idx", "end_col_offset_idx"))]
    result = old.slots({**data, "table_cells": complete})
    result["cells_missing_offsets"] = [i for i, c in enumerate(data["table_cells"]) if c not in complete]
    result["coverage_counts_exclude_cells_missing_offsets"] = bool(result["cells_missing_offsets"])
    result["span_offset_mismatches"] = [i for i, c in enumerate(data["table_cells"])
        if c in complete and (c.get("row_span", 1) != c["end_row_offset_idx"]-c["start_row_offset_idx"]
            or c.get("col_span", 1) != c["end_col_offset_idx"]-c["start_col_offset_idx"])]
    return result


def diagnostic_headers(data, gold):
    found = []
    for c in data["table_cells"]:
        if c.get("column_header") and c["text"] in {h["path"][-1] for h in gold["headers"]}:
            col, row = c["start_col_offset_idx"], c["start_row_offset_idx"]
            ancestry = []
            for r in range(row+1):
                matches = cells_at(data, r, col)
                if len(matches) == 1 and matches[0].get("column_header"):
                    text = matches[0]["text"]
                    if not ancestry or ancestry[-1] != text:
                        ancestry.append(text)
            # Evaluation-only minor spelling adjudication, never a producer repair.
            adjudicated = ["Adversial" if x == "Adversarial" else x for x in ancestry]
            keys = [h["key"] for h in gold["headers"] if adjudicated == h["path"]]
            found.append({"column": col, "path": ancestry, "adjudicated_path": adjudicated,
                          "key": keys[0] if len(keys) == 1 else None,
                          "literal_path_exact": any(ancestry == h["path"] for h in gold["headers"])})
    return found


def evaluate_table6(data, gold):
    headers = diagnostic_headers(data, gold)
    columns = {h["key"]: h["column"] for h in headers if h["key"] is not None}
    contexts, by_row = [], {}
    for expected in gold["rows"]:
        context = expected["context"]
        methods = [c for c in data["table_cells"] if c.get("row_header") and norm(c["text"]) == norm(context["method"])]
        candidates = []
        for method in methods:
            row = method["start_row_offset_idx"]
            dimension_cells = {}
            for dimension in ("model_family", "model_variant"):
                dimension_cells[dimension] = [c for c in data["table_cells"] if c.get("row_header")
                    and norm(c["text"]) == norm(context[dimension])
                    and c["start_row_offset_idx"] <= row < c["end_row_offset_idx"]]
            if all(len(v) == 1 for v in dimension_cells.values()):
                candidates.append({"row": row, "method": method, **{k: v[0] for k, v in dimension_cells.items()}})
        selected = candidates[0] if len(candidates) == 1 else None
        if selected:
            by_row[expected["row_id"]] = selected
        contexts.append({"row_id": expected["row_id"], "expected": context,
            "unique_named_label_and_row_extent_match": selected is not None,
            "actual": selected,
            "distinct_model_family_variant_method_columns": selected is not None and len({selected[k]["start_col_offset_idx"]
                for k in ("model_family", "model_variant", "method")}) == 3})
    points, observed_indices = [], set()
    by_id = {}
    numeric_rows = sorted({c["start_row_offset_idx"] for c in data["table_cells"] if number(c["text"])})
    numeric_cols = sorted({c["start_col_offset_idx"] for c in data["table_cells"] if number(c["text"])})
    gold_rows = [r["row_id"] for r in gold["rows"]]
    gold_cols = [h["key"] for h in gold["headers"]]
    for expected in gold["expected_datapoints"]:
        selected = by_row.get(expected["row_id"])
        col = columns.get(expected["column_key"])
        matches = [] if selected is None or col is None else [c for c in cells_at(data, selected["row"], col) if number(c["text"])]
        cell = matches[0] if len(matches) == 1 else None
        if cell:
            observed_indices.add(next(i for i, c in enumerate(data["table_cells"]) if c is cell))
        ri, ci = gold_rows.index(expected["row_id"]), gold_cols.index(expected["column_key"])
        positional = old.text_at(data, numeric_rows[ri], numeric_cols[ci]) if ri < len(numeric_rows) and ci < len(numeric_cols) else None
        point = {"id": expected["id"], "row_id": expected["row_id"], "column_key": expected["column_key"],
            "expected": expected["raw_value"], "raw_value_at_source_numeric_order": positional,
            "raw_positional_literal_correct": positional == expected["raw_value"],
            "raw_value_at_named_label_row_extent": cell["text"] if cell else None,
            "raw_named_label_numeric_diagnostic_correct": cell is not None and cell["text"] == expected["raw_value"],
            "caveat": "Named labels and row extents remain readable, but overlapping row dimensions are not a valid grid binding."}
        points.append(point)
        by_id[point["id"]] = point
    extras = [dict(index=i, **c) for i, c in enumerate(data["table_cells"]) if number(c["text"]) and i not in observed_indices]
    comparisons = []
    for rule in gold["critical_comparisons"]:
        left, right = by_id[rule["left"]], by_id[rule["right"]]
        try:
            holds = Decimal(left["raw_value_at_named_label_row_extent"]) > Decimal(right["raw_value_at_named_label_row_extent"])
        except (InvalidOperation, TypeError):
            holds = False
        comparisons.append({**rule, "raw_arithmetic_holds": holds,
            "left": left["raw_value_at_named_label_row_extent"], "right": right["raw_value_at_named_label_row_extent"],
            "accepted_structural_binding": False})
    correct = sum(p["raw_named_label_numeric_diagnostic_correct"] for p in points)
    missing = sum(p["raw_value_at_named_label_row_extent"] is None for p in points)
    return {"denominator": 300, "raw_positional_literal_correct": sum(p["raw_positional_literal_correct"] for p in points),
        "raw_named_label_numeric_diagnostic_correct": correct, "missing": missing,
        "present_wrong_literals": 300-correct-missing, "extra_numeric_cells": extras,
        "raw_numeric_error_rate_including_extras": (300-correct+len(extras))/300,
        "numeric_cells_emitted": sum(number(c["text"]) for c in data["table_cells"]),
        "header_paths": headers, "literal_header_paths_exact": sum(h["literal_path_exact"] for h in headers),
        "header_paths_after_minor_spelling_adjudication": len(columns),
        "row_contexts": contexts, "row_contexts_identifiable_from_text_and_extents": len(by_row),
        "critical_comparisons": comparisons, "raw_critical_arithmetic_holds": sum(x["raw_arithmetic_holds"] for x in comparisons),
        "points": points}


def collateral(data):
    # Post-call transcription verified at288dpi against the original PDF, separate from G1-T04.
    source = [
        ("DeepSeek-R1-32B", "LoCoMo", "8.58 6.48 4.79 4.35 12.96 12.52 10.72 8.20 21.40 20.23"),
        ("DeepSeek-R1-32B", "MemGPT", "8.28 6.25 5.45 4.97 10.97 9.09 11.34 9.03 30.77 29.23"),
        ("DeepSeek-R1-32B", "A-MEM", "15.02 10.64 14.64 11.01 14.81 12.82 15.37 12.30 27.92 27.19"),
        ("Claude 3.0 Haiku", "LoCoMo", "4.56 3.33 0.82 0.59 2.86 3.22 3.56 3.24 3.46 3.42"),
        ("Claude 3.0 Haiku", "MemGPT", "7.65 6.36 1.65 1.26 7.41 6.64 8.60 7.29 7.66 7.37"),
        ("Claude 3.0 Haiku", "A-MEM", "19.28 14.69 16.65 12.23 11.85 9.61 34.72 30.05 35.99 34.87"),
        ("Claude 3.5 Haiku", "LoCoMo", "11.34 8.21 3.29 2.69 3.79 3.58 14.01 12.57 7.37 7.12"),
        ("Claude 3.5 Haiku", "MemGPT", "8.27 6.55 3.99 2.76 4.71 4.48 16.52 14.89 5.64 5.45"),
        ("Claude 3.5 Haiku", "A-MEM", "29.70 23.19 31.54 27.53 11.42 9.47 42.60 37.41 13.65 12.71"),
    ]
    groups = sorted([c for c in data["table_cells"] if c.get("row_section")], key=lambda c: c["start_row_offset_idx"])
    records = []
    for group, method, values in source:
        g = next(c for c in groups if c["text"] == group)
        end = min([c["start_row_offset_idx"] for c in groups if c["start_row_offset_idx"] > g["start_row_offset_idx"]] or [data["num_rows"]])
        row = next(c["start_row_offset_idx"] for c in data["table_cells"] if c.get("row_header") and norm(c["text"]) == norm(method)
                   and g["end_row_offset_idx"] <= c["start_row_offset_idx"] < end)
        for col, value in enumerate(values.split(), 1):
            found = [c for c in cells_at(data, row, col) if number(c["text"])]
            actual = found[0]["text"] if len(found) == 1 else None
            records.append({"group": group, "method": method, "metric_position": col,
                            "expected": value, "actual": actual, "exact": actual == value})
    return {"source": "original PDF rendered at288dpi and manually verified after all calls; native crop input unchanged", "separate_denominator": 90,
        "does_not_increase_G1_T04_denominator": True, "numeric_literals_at_named_group_method_and_metric_position_correct": sum(x["exact"] for x in records),
        "numeric_cells_emitted": sum(number(c["text"]) for c in data["table_cells"]),
        "records": records, "groups": [c["text"] for c in groups],
        "header_binding_limit": "Single Hop header lacks an end column and has end row 9; other category/metric headers overlap on row1. Numeric transcription is diagnostic, not valid hierarchical delivery."}


def main():
    complete = json.loads((HERE / "all-calls-complete.json").read_text())
    assert complete["requests"] == 6
    observations = json.loads((HERE / "live-observations.json").read_text())
    assert len(observations) == 6 and all(x["http_status"] == 200 and x["finish_reason"] == "stop" for x in observations)
    reg = json.loads((HERE / "registration.json").read_text())
    page = next(p for p in reg["pages"] if p["name"] == "paper09-p17")
    payloads, errors, grids = [], [], []
    for n in (0, 1):
        dest = HERE / page["name"] / ("table"+str(n))
        response = json.loads((dest / "response.json").read_text())
        assert old.sha(dest / "response.json") == complete["response_hashes"][page["name"]+"-table"+str(n)]
        content = (dest / "content.txt").read_text()
        assert content == response["choices"][0]["message"]["content"]
        payload = json.loads(content)
        payloads.append(payload)
        try:
            old.parse_response(payload, ["p17:#/tables/"+str(n)])
        except ValueError as error:
            errors.append(error.errors(include_url=False, include_context=False, include_input=False))
        else:
            raise AssertionError("Observed invalid target unexpectedly passed")
        grids.append(grid_diagnostics(payload["targets"][0]["panels"][0]["data"]))
    assert not any((HERE / page["name"] / name).exists() for name in ("document.json", "document.md", "bindings.json"))
    oracle = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
    gold = next(c["details"] for c in json.loads(oracle.read_text())["cases"] if c["id"] == "G1-T04")
    data = payloads[0]["targets"][0]["panels"][0]["data"]
    numeric = evaluate_table6(data, gold)
    assert len(numeric["points"]) == 300
    changed = json.loads(json.dumps(data))
    next(c for c in changed["table_cells"] if number(c["text"]))["text"] = "999"
    assert evaluate_table6(changed, gold)["raw_named_label_numeric_diagnostic_correct"] == numeric["raw_named_label_numeric_diagnostic_correct"]-1
    changed = json.loads(json.dumps(data))
    next(c for c in changed["table_cells"] if c["text"] == "4o-mini")["text"] = "unknown variant"
    assert evaluate_table6(changed, gold)["missing"] == numeric["missing"]+50
    baseline = json.loads(Path(page["baseline"]).read_text())
    source_caps = [[baseline["texts"][int(r["$ref"].rsplit("/", 1)[1])]["text"] for r in t["captions"]] for t in baseline["tables"]]
    result = {"case": "G1-T04", "all_six_calls_completed_before_oracle_read": True,
        "schema_accepted": [False, False], "schema_errors": errors, "raw_grid_diagnostics": grids,
        "table6": numeric, "table7_collateral": collateral(payloads[1]["targets"][0]["panels"][0]["data"]),
        "row_dimension_issue": "Model family uses column0; model variant and method both occupy column1 for all30 data rows. Declared32 rows but cells reach exclusive row33. Model header covers one column/two rows, source covers two columns/three rows.",
        "source_caption_ownership": {"baseline_linked_captions": source_caps,
            "producer_captions_empty_as_requested": all(p["targets"][0]["caption"] == "" for p in payloads),
            "outer_caption_conditions_in_baseline": True, "main_markdown_preservation_testable": False},
        "minor_text_adjudication": "Adversarial vs source Adversial is reported as two nonliteral header paths but accepted for raw semantic identification; row model labels match without OCR substitutions.",
        "collateral_review_amendment": "Initial144dpi manual draft misread13 source values;288dpi original-PDF review corrected only evaluator reference data. No candidate output, input or frozen oracle was changed.",
        "accepted_delivery": {"typed": 0, "markdown": 0, "critical": 0,
            "reason": "Whole page rejected before mapping; these zeros describe delivery, not raw numeric accuracy."},
        "decision": "reject current producer: numerical transcription improved, but row-dimension collisions, invalid shape and malformed collateral header prevent honest typed/Markdown delivery",
        "self_checks": ["single numeric mutation detected", "missing variant removes50 named-label diagnostics"],
        "source_visual_review": {"PDF": page["source"], "PDF_sha256": page["source_sha256"],
            "render_scale": 4, "evaluation_only_table7_image": "paper09-p17/evaluation-source-table7-288dpi.png",
            "evaluation_only_table7_image_sha256": old.sha(HERE/page["name"]/"evaluation-source-table7-288dpi.png"),
            "candidate_input_modified": False},
        "sha256": {str(p.relative_to(ROOT)): old.sha(p) for p in [oracle, Path(__file__), HERE/"registration.json", HERE/"all-calls-complete.json",
            HERE/page["name"]/"table0/content.txt", HERE/page["name"]/"table1/content.txt"]}}
    old_points = numeric.pop("points")
    (HERE/"evaluation-t04.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    (HERE/"evaluation-t04-points.json").write_text(json.dumps(old_points, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"raw_numeric": numeric["raw_named_label_numeric_diagnostic_correct"], "missing": numeric["missing"],
        "extra_numeric_cells": len(numeric["extra_numeric_cells"]), "raw_critical": numeric["raw_critical_arithmetic_holds"],
        "table7_raw": result["table7_collateral"]["numeric_literals_at_named_group_method_and_metric_position_correct"],
        "grids": grids, "decision": result["decision"]}, indent=2))


if __name__ == "__main__":
    main()
