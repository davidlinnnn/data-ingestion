"""Post-all-calls diagnostic evaluation; never repair or construct an accepted document."""
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from adapter import parse_response


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cell_at(data, row, column):
    matches = [c for c in data["table_cells"]
               if c["start_row_offset_idx"] <= row < c["end_row_offset_idx"]
               and c["start_col_offset_idx"] <= column < c["end_col_offset_idx"]]
    return matches[0] if len(matches) == 1 else None


def text_at(data, row, column):
    cell = cell_at(data, row, column)
    return None if cell is None else cell["text"]


def slots(data):
    seen, duplicates = set(), set()
    for cell in data["table_cells"]:
        occupied = {(r, c) for r in range(cell["start_row_offset_idx"], cell["end_row_offset_idx"])
                    for c in range(cell["start_col_offset_idx"], cell["end_col_offset_idx"])}
        duplicates |= occupied & seen
        seen |= occupied
    expected = {(r, c) for r in range(data["num_rows"]) for c in range(data["num_cols"])}
    return {"declared_slots": len(expected), "covered_slots": len(seen & expected),
            "gap_slots": len(expected - seen), "duplicate_slots": len(duplicates),
            "out_of_bounds_slots": len(seen - expected)}


def main():
    observations = json.loads((HERE / "live-observations.json").read_text())
    assert len(observations) == 4 and all(o["http_status"] == 200 for o in observations)
    assert all(o["finish_reason"] == "stop" for o in observations), "evaluate only after all four fixed calls"
    registration = json.loads((HERE / "live-registration.json").read_text())
    assert sha(HERE / "adapter.py") == registration["adapter_sha256"], "frozen adapter must remain unchanged"
    job = next(j for j in registration["jobs"] if j["name"] == "paper09-p17")
    dest = HERE / job["name"]
    raw_path = dest / "output.json"
    payload = json.loads(raw_path.read_text())
    response = json.loads((dest / "response.json").read_text())
    assert payload == json.loads(response["choices"][0]["message"]["content"]), "raw output must equal the single recorded provider response"
    expected_keys = [t["target_key"] for t in job["targets"]]
    actual_keys = [t["target_key"] for t in payload["targets"]]
    errors = []
    try:
        parse_response(payload, expected_keys)
    except ValueError as error:
        errors = error.errors(include_url=False, include_context=False, include_input=False)
    assert errors, "current page must remain rejected by the unchanged adapter"
    assert not (dest / "document.json").exists() and not (dest / "document.md").exists()
    gold_path = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
    cases = json.loads(gold_path.read_text())
    gold = next(c["details"] for c in cases["cases"] if c["id"] == "G1-T04")
    target = next(t for t in payload["targets"] if t["target_key"] == "p17:#/tables/0")
    data = target["panels"][0]["data"]
    assert (data["num_rows"], data["num_cols"]) == (33, 13)
    rows = {row["row_id"]: row for row in gold["rows"]}
    header_keys = [h["key"] for h in gold["headers"]]
    details, by_id = [], {}
    context_records = []
    for index, row in enumerate(gold["rows"]):
        raw_context = dict(zip(gold["structure"]["row_dimension_columns"],
                               [text_at(data, index + 3, c) for c in range(3)], strict=True))
        context_records.append({"row_id": row["row_id"], "expected": row["context"], "actual": raw_context,
                                "exact_context": raw_context == row["context"]})
    contexts = {r["row_id"]: r for r in context_records}
    header_records = []
    for index, header in enumerate(gold["headers"]):
        actual = [text_at(data, r, index + 3) for r in range(3)]
        flags = [bool(cell_at(data, r, index + 3).get("column_header", False)) for r in range(3)]
        header_records.append({"key": header["key"], "expected": header["path"], "actual": actual,
                               "exact_path_and_role": actual == header["path"] and all(flags)})
    headers = {h["key"]: h for h in header_records}
    for point in gold["expected_datapoints"]:
        row_index = list(rows).index(point["row_id"]) + 3
        column = header_keys.index(point["column_key"]) + 3
        actual = text_at(data, row_index, column)
        literal_correct = actual == point["raw_value"]
        record = {"id": point["id"], "source_row": point["row_id"], "column_key": point["column_key"],
                  "expected": point["raw_value"], "actual": actual, "literal_at_source_position_correct": literal_correct,
                  "exact_context": contexts[point["row_id"]]["exact_context"],
                  "header_path_correct": headers[point["column_key"]]["exact_path_and_role"]}
        record["strict_literal_context_binding_correct"] = literal_correct and record["exact_context"] and record["header_path_correct"]
        details.append(record)
        by_id[point["id"]] = record
    comparisons = []
    for comparison in gold["critical_comparisons"]:
        left, right = by_id[comparison["left"]], by_id[comparison["right"]]
        try:
            arithmetic = Decimal(left["actual"]) > Decimal(right["actual"])
        except (InvalidOperation, TypeError):
            arithmetic = False
        comparisons.append({**comparison, "actual_left": left["actual"], "actual_right": right["actual"],
                            "positional_arithmetic_holds": arithmetic,
                            "strict_source_binding_holds": arithmetic and left["strict_literal_context_binding_correct"]
                             and right["strict_literal_context_binding_correct"]})
    literal_correct = sum(p["literal_at_source_position_correct"] for p in details)
    missing = sum(p["actual"] is None for p in details)
    strict_correct = sum(p["strict_literal_context_binding_correct"] for p in details)
    full_span = gold["structure"]["header_spans"][0]
    model_header = cell_at(data, 0, 0)
    model_header_match = (model_header["text"] == full_span["text"]
                          and model_header["start_col_offset_idx"] == full_span["column_start"]
                          and model_header["end_col_offset_idx"] - model_header["start_col_offset_idx"] == full_span["column_span"])
    result = {"case": "G1-T04", "evaluation_scope": "post-call raw diagnostics only; no repaired or accepted typed/Markdown artifact",
        "all_four_calls_completed_before_oracle_read": True,
        "inputs_sha256": {"output.json": sha(raw_path), "oracle": sha(gold_path), "live-registration.json": sha(HERE / "live-registration.json"),
                          "adapter.py": sha(HERE / "adapter.py"), "evaluator.py": sha(Path(__file__))},
        "schema": {"accepted": False, "exact_validation_errors": errors, "expected_target_keys": expected_keys,
                   "actual_target_keys": actual_keys, "missing_target_keys": sorted(set(expected_keys) - set(actual_keys)),
                   "first_failure_masks_later_keyset_failure": set(expected_keys) != set(actual_keys),
                   "main_table_grid": slots(data), "main_table_physical_cells": len(data["table_cells"])},
        "raw_numeric_diagnostic": {"denominator": 300, "literal_at_source_position_correct": literal_correct,
             "missing": missing, "present_wrong_literal": 300 - literal_correct - missing,
             "minimum_error_rate_from_missing_alone": missing / 300,
             "strict_literal_context_binding_correct": strict_correct,
             "label_adjudication_limit": "strict context count is separate; even treating 40-min as minor OCR leaves 250 missing / 300 and failure"},
        "raw_critical_diagnostic": {"denominator": 5,
             "positional_arithmetic_holds": sum(c["positional_arithmetic_holds"] for c in comparisons),
             "strict_source_binding_holds": sum(c["strict_source_binding_holds"] for c in comparisons), "comparisons": comparisons},
        "structure": {"metric_header_paths_and_roles_correct": sum(h["exact_path_and_role"] for h in header_records),
             "metric_header_paths_denominator": 10, "model_header_span_matches_source": model_header_match,
             "actual_model_header_cell": model_header, "expected_model_header_span": full_span,
             "caption_literal_exact": target["caption"] == gold["caption"]["text"],
             "complete_data_rows": sum(all(text_at(data, r, c) is not None for c in range(13)) for r in range(3, 33)),
             "missing_method_cells": sum(text_at(data, r, 2) is None for r in range(3, 33)),
             "contexts": context_records, "header_paths": header_records},
        "collateral_table7": {"g1_numeric_denominator_increase": 0, "source_separate_table_visually_confirmed": True,
             "output_wrongly_inside_table6_as_panel_index": 1,
             "output_panel_metadata": {k: v for k, v in target["panels"][1].items() if k != "data"},
             "own_target_key_missing": "p17:#/tables/1" not in actual_keys,
             "source_caption_and_F1_BLEU1_percent_conditions_missing": True,
             "diagnostic_grid": slots(target["panels"][1]["data"]),
             "raw_numeric_accuracy": "not independently adjudicated; extra table does not enlarge T04 denominator"},
        "end_to_end": {"status": "rejected", "accepted_typed_numeric_delivery": 0,
             "accepted_markdown_numeric_delivery": 0, "accepted_critical_comparison_delivery": 0,
             "notation": "0 delivered because the entire page was rejected, not an assertion that all emitted raw numbers were wrong"},
        "source_visual_review": {"full_page": job["image"], "full_page_sha256": job["image_sha256"],
             "frozen_table6_crop": str(ROOT / gold["rendered_evidence"][1]["path"]),
             "checked": ["visible 30×10 values vs only first5 emitted rows", "Model spans both family/variant stubs",
                         "rotated GPT4o-mini/4o vs raw40-min/40", "Table7 separate caption/body, not a Table6 panel"]},
        "decision": "fail: raw omission83.33% exceeds5%; four critical comparisons missing; native-target merge invalid; no repair or retry"}
    assert literal_correct == 50 and missing == 250 and len(details) == 300
    assert result["schema"]["main_table_grid"]["gap_slots"] == 275
    assert sum(c["positional_arithmetic_holds"] for c in comparisons) == 1
    (HERE / "evaluation-t04.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (HERE / "evaluation-t04-points.json").write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("case", "raw_numeric_diagnostic", "raw_critical_diagnostic", "end_to_end", "decision")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
