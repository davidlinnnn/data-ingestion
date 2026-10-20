"""Zero-inference controls for the new regression evaluator."""
import copy
import json
from pathlib import Path
import unittest

from evaluate import evaluate, score_stage, validate_reference

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "pdf-core-ocr-crop-ablation-2026-10-19"
TRACE = HERE.parent / "pdf-core-ocr-boundary-trace-2026-10-19"


class EvaluationControls(unittest.TestCase):
    def setUp(self):
        self.ref = json.loads((OLD / "reference.json").read_text())
        for item in self.ref["items"]:
            item["critical"] = item["role"] == "section_header"

    def test_retained_s0_is_red_for_raw_and_document_mix(self):
        cells = json.loads((TRACE / "live/trace/ocr-cells-before-merge-001.json").read_text())
        doc = json.loads((TRACE / "live/document.json").read_text())
        report = evaluate(cells, doc, self.ref)
        self.assertEqual(len(report["raw_cells"]["cross_column_mixed_elements"]), 3)
        self.assertEqual(len(report["document"]["cross_column_mixed_elements"]), 2)
        self.assertEqual(report["qualification"], "REVIEW_REQUIRED")

    def test_retained_zero_dilation_is_red_for_missing_heading(self):
        cells = json.loads((OLD / "B/ocr-cells.json").read_text())
        doc = json.loads((OLD / "B/document.json").read_text())
        report = evaluate(cells, doc, self.ref)
        self.assertIn("H01", report["document"]["whole_unit_omission_candidates"])
        self.assertIn("H01", report["document"]["critical_text_difference_candidates"])

    def test_valid_fullwidth_heading_is_not_crosscolumn_mix(self):
        ref = {"items": [
            {"id": "H", "role": "section_header", "column": "fullwidth", "bbox": [0, 0, 100, 10], "text": "A shared document title", "critical": True},
            {"id": "L", "role": "paragraph", "column": "left", "bbox": [0, 20, 40, 50], "text": "Left column records uniquely identify apples and oranges."},
            {"id": "R", "role": "paragraph", "column": "right", "bbox": [60, 20, 100, 50], "text": "Right column records uniquely identify rivers and mountains."}],
            "body_order": ["H", "L", "R"], "legitimate_cross_column_items": ["H"]}
        validate_reference(ref)
        scored = score_stage([{"text": item["text"]} for item in ref["items"]], ref)
        self.assertEqual(scored["cross_column_mixed_elements"], [])
        self.assertEqual(scored["whole_unit_omission_candidates"], [])

    def test_word_cells_do_not_create_false_coverage_omissions(self):
        cells = [{"text": word} for item in self.ref["items"] for word in item["text"].split()]
        scored = score_stage(cells, self.ref)
        self.assertEqual(scored["whole_unit_omission_candidates"], [])
        self.assertTrue(all(row["character_coverage"] == 1 for row in scored["source_units"]))

    def test_native_and_alias_references_and_furniture_are_retained(self):
        alias = json.loads((TRACE / "live/document.json").read_text())
        native = json.loads((OLD / "A/downstream.json").read_text())["document"]
        cells = json.loads((OLD / "A/ocr-cells.json").read_text())
        before = copy.deepcopy((cells, native))
        self.assertEqual(evaluate(cells, native, self.ref), evaluate(cells, alias, self.ref))
        self.assertEqual(before, (cells, native))
        rows = evaluate(cells, native, self.ref)["document"]["source_units"]
        self.assertEqual(next(row for row in rows if row["id"] == "PAGE")["character_coverage"], 1)

    def test_empty_document_or_empty_cells_are_invalid(self):
        valid = {"schema_name": "DoclingDocument", "texts": [{"text": "Something"}]}
        with self.assertRaisesRegex(AssertionError, "Empty OCR cells"):
            evaluate([], valid, self.ref)
        with self.assertRaisesRegex(AssertionError, "Empty document"):
            evaluate([{"text": "Something"}], {"schema_name": "DoclingDocument", "texts": []}, self.ref)

    def test_unscored_symbol_is_retained_outside_denominator(self):
        ref = copy.deepcopy(self.ref)
        ref["items"].append({"id": "SYMBOL", "role": "formula", "column": "left",
                             "bbox": [1, 1, 2, 2], "text": "→", "scored": False})
        ref["source_lines"] = [{"text": "→", "scored": False}]
        cells = [{"text": item["text"]} for item in self.ref["items"]]
        doc = {"schema_name": "DoclingDocument", "texts": cells}
        report = evaluate(cells, doc, ref)
        self.assertEqual([item["id"] for item in report["scope"]["unscored_source_units"]], ["SYMBOL"])
        self.assertNotIn("SYMBOL", [row["id"] for row in report["document"]["source_units"]])


if __name__ == "__main__":
    unittest.main()
