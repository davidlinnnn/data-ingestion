"""No-inference controls for full-page coverage/mixing/order diagnostics."""
import copy
import unittest
from score import reference, score, score_stage


class ScoreControls(unittest.TestCase):
    def setUp(self):
        self.ref = reference()
        by_id = {x["id"]: x for x in self.ref["items"]}
        self.cells = [{"text": by_id[key]["text"]} for key in self.ref["body_order"]]

    def test_exact_source_has_no_flags(self):
        result = score_stage(self.cells, self.ref)
        for key in ("cross_column_mixed_elements", "whole_paragraph_omissions_candidates",
                    "whole_paragraph_duplicates_candidates", "body_order_inversions_candidates"):
            self.assertEqual(result[key], [], key)
        self.assertTrue(all(x["character_coverage"] == 1 for x in
                            result["paragraphs_and_furniture"] if x["id"] in self.ref["body_order"]))

    def test_cross_column_text_is_detected_without_geometry(self):
        altered = copy.deepcopy(self.cells)
        altered[0]["text"] += " " + altered[6]["text"]
        result = score_stage(altered, self.ref)
        self.assertEqual(result["cross_column_mixed_elements"][0]["index"], 0)

    def test_missing_full_paragraph(self):
        result = score_stage(self.cells[1:], self.ref)
        self.assertIn("P01", result["whole_paragraph_omissions_candidates"])

    def test_duplicate_full_paragraph(self):
        result = score_stage(self.cells + [self.cells[0]], self.ref)
        self.assertIn("P01", result["whole_paragraph_duplicates_candidates"])

    def test_wrong_order(self):
        altered = copy.deepcopy(self.cells)
        altered[0], altered[1] = altered[1], altered[0]
        result = score_stage(altered, self.ref)
        self.assertIn(["P01", "P02"], result["body_order_inversions_candidates"])

    def test_document_reference_order_and_no_mutation(self):
        doc = {"schema_name": "DoclingDocument", "body": {"children": [
            {"$ref": "#/texts/1"}, {"$ref": "#/texts/0"}]}, "texts": [
            {"text": self.cells[0]["text"], "children": [], "self_ref": "#/texts/0"},
            {"text": self.cells[1]["text"], "children": [], "self_ref": "#/texts/1"}]}
        before = copy.deepcopy((self.cells, doc))
        result = score(self.cells, doc)
        self.assertIn(["P01", "P02"], result["document"]["body_order_inversions_candidates"])
        self.assertEqual(before, (self.cells, doc))

    def test_minor_glyph_change_is_reported(self):
        altered = copy.deepcopy(self.cells)
        altered[0]["text"] = altered[0]["text"].replace("LLMs", "LLMsX", 1)
        result = score_stage(altered, self.ref)
        row = next(x for x in result["paragraphs_and_furniture"] if x["id"] == "P01")
        self.assertTrue(row["text_differences"])
        self.assertEqual(result["whole_paragraph_omissions_candidates"], [])


if __name__ == "__main__":
    unittest.main()
