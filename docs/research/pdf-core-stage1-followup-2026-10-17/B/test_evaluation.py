"""Offline evaluator regressions; mutate copies and map only in memory."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from docling_core.types.doc import DoclingDocument, RefItem, TableData

import controls
import evaluate as e
import protocol as p


class EvaluationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c["id"]: c["details"] for c in json.loads(
            (e.ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json").read_text())["cases"]}
        cls.registration = json.loads((e.HERE / "live-registration.json").read_text())
        cls.small = p.load("test_small", e.RESEARCH / "pdf-core-direct-cell-2026-10-17/evaluate-small.py")
        cls.crop = p.load("test_crop", e.RESEARCH / "pdf-core-table-crops-2026-10-17/evaluate-small.py")
        cls.t05 = p.load("test_t05", e.RESEARCH / "pdf-core-table-crops-2026-10-17/evaluate-t05.py")

    def t01_payload(self):
        return json.loads((e.LIVE / "memory-r1-p8-table0/output.json").read_text())

    def t05_payload(self):
        historical = json.loads((e.RESEARCH /
            "pdf-core-table-crops-2026-10-17/wikiskill-p13/table0/output.json").read_text())
        for panel in historical["targets"][0]["panels"]:
            panel["data"] = TableData.model_validate(panel["data"]).model_dump(mode="json")
        return controls.compact(historical)

    def map_page(self, payload, page_name):
        page = next(pg for pg in self.registration["pages"] if pg["name"] == page_name)
        baseline = DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
        before = baseline.model_dump_json()
        doc, bindings = p.map_response(baseline, payload, page["page_no"], page["target_keys"])
        self.assertEqual(baseline.model_dump_json(), before)
        reloaded = DoclingDocument.model_validate_json(doc.model_dump_json())
        self.assertEqual(p.adapter.export_markdown(reloaded, bindings),
                         p.adapter.export_markdown(doc, bindings))
        return reloaded, bindings

    def small_views(self, payload, page_name="memory-r1-p8"):
        doc, bindings = self.map_page(payload, page_name)
        binding = bindings[0]
        typed = self.crop.raw_view(binding["provider"])
        rendered = e.rendered_view(doc, binding, p.adapter.export_markdown(doc, bindings), self.t05)
        return typed, rendered

    def small_score(self, view, case_id="G1-T01"):
        return e.small_case_score(view, self.cases[case_id], self.small, case_id)

    def t05_inputs(self, payload):
        doc, bindings = self.map_page(payload, "wikiskill-p13")
        binding = bindings[0]
        table = RefItem(cref=binding["panels"][0]["table_ref"]).resolve(doc)
        return (table.data.model_dump(mode="json"), p.adapter.export_markdown(doc, bindings),
                binding["compact_provider"]["panels"][0]["data"])

    def t05_scores(self, payload):
        data, markdown, compact = self.t05_inputs(payload)
        typed, rendered = e.t05_views(data, markdown, self.t05, self.cases["G1-T05"], compact=compact)
        self.assertIsNotNone(rendered)
        return typed, rendered

    def test_t01_original_is_six_of_six_in_both_views(self):
        for view in self.small_views(self.t01_payload()):
            with self.subTest(view=view["panels"][0]["title"]):
                score = self.small_score(view)
                self.assertEqual(score["source_numeric_bindings_correct"], 6)
                self.assertEqual(score["extra_numeric_observations"], 0)
                self.assertTrue(score["content_pass"])

    def test_t01_invented_second_panel_counts_extra_and_fails_in_both_views(self):
        payload = self.t01_payload()
        extra = deepcopy(payload["targets"][0]["panels"][0])
        extra.update(panel_label="Invented panel", title="fabricated")
        extra["data"]["grid"][1][1] = "999"
        payload["targets"][0]["panels"].append(extra)
        for view in self.small_views(payload):
            self.assertEqual(len(view["panels"]), 2)
            self.assertEqual(view["panels"][1]["rows"][0]["values"][0]["value"], "999")
            score = self.small_score(view)
            self.assertGreater(score["extra_numeric_observations"], 0)
            self.assertFalse(score["content_pass"])

    def test_t01_split_rows_across_panels_keeps_all_six_bindings(self):
        payload = self.t01_payload()
        original = payload["targets"][0]["panels"][0]
        panels = []
        for index, row in enumerate(original["data"]["grid"][1:]):
            panel = deepcopy(original)
            panel["panel_label"] = f"Panel {index + 1}"
            panel["data"]["grid"] = [deepcopy(original["data"]["grid"][0]), deepcopy(row)]
            panel["data"]["roles"] = [role for role in panel["data"]["roles"] if role["row"] <= 1]
            panels.append(panel)
        payload["targets"][0]["panels"] = panels
        for view in self.small_views(payload):
            score = self.small_score(view)
            self.assertEqual(score["source_numeric_bindings_correct"], 6)
            self.assertEqual(score["extra_numeric_observations"], 0)
            self.assertTrue(score["content_pass"])

    def test_t01_rendered_value_is_checked_independently(self):
        typed, rendered = self.small_views(self.t01_payload())
        rendered["panels"][0]["rows"][0]["values"][0]["value"] = "999"
        self.assertEqual(self.small_score(typed)["source_numeric_bindings_correct"], 6)
        changed = self.small_score(rendered)
        self.assertEqual(changed["source_numeric_bindings_correct"], 5)
        self.assertFalse(changed["content_pass"])

    def test_t02_six_panels_pass_and_duplicate_panel_fails_shared_gate(self):
        payload = json.loads((e.LIVE / "skillopt-p8-table0/output.json").read_text())
        payload["targets"].extend(json.loads((e.LIVE / "skillopt-p8-table1/output.json").read_text())["targets"])
        self.assertEqual(len(payload["targets"][0]["panels"]), 6)
        for duplicate in (False, True):
            candidate = deepcopy(payload)
            if duplicate:
                candidate["targets"][0]["panels"].append(deepcopy(candidate["targets"][0]["panels"][0]))
            for view in self.small_views(candidate, "skillopt-p8"):
                with self.subTest(duplicate=duplicate):
                    self.assertEqual(len(view["panels"]), 7 if duplicate else 6)
                    score = self.small_score(view, "G1-T02")
                    self.assertEqual(score["fixed_numeric_denominator"], 84)
                    self.assertEqual(score["content_pass"], not duplicate)
                    if duplicate:
                        self.assertLess(score["source_numeric_bindings_correct"], 84)
                        self.assertGreater(score["errors_including_extras"], 0)
                        self.assertTrue(score["duplicate_panels"])
                    else:
                        self.assertEqual(score["source_numeric_bindings_correct"], 84)
                        self.assertEqual(score["errors_including_extras"], 0)
                        self.assertEqual(score["comparisons_correct"], 8)

    def test_t05_historical_public_defaults_preserve_all_eighty_and_twenty_pairs(self):
        for score in self.t05_scores(self.t05_payload()):
            self.assertEqual(score["correct_expected_bindings"], 80)
            self.assertEqual(score["numeric_errors_including_extras"], 0)
            self.assertEqual(score["critical_comparisons_passed"], 7)
            self.assertEqual(score["paired_structure_passed"], 20)
            self.assertTrue(score["row_group_scope_pass"])
            self.assertTrue(score["content_pass"])

    def test_t05_shortened_declared_scope_cannot_inherit_previous_group(self):
        payload = self.t05_payload()
        compact = payload["targets"][0]["panels"][0]["data"]
        self.assertEqual(compact["row_groups"][0]["end"], 8)
        compact["row_groups"][0]["end"] = 7
        p.parse(payload, ["p13:#/tables/0"])
        for score in self.t05_scores(payload):
            self.assertLess(score["correct_expected_bindings"], 80)
            self.assertFalse(score["row_group_scope_pass"])
            self.assertFalse(score["content_pass"])

    def test_t05_one_numeric_error_keeps_pair_structure_and_passes_tolerance(self):
        payload = self.t05_payload()
        compact = payload["targets"][0]["panels"][0]["data"]
        self.assertEqual(compact["grid"][3][1], "3.1 / 1.6")
        compact["grid"][3][1] = "3.2 / 1.6"
        for score in self.t05_scores(payload):
            self.assertEqual(score["correct_expected_bindings"], 79)
            self.assertEqual(score["numeric_errors_including_extras"], 1)
            self.assertEqual(score["critical_comparisons_passed"], 7)
            self.assertEqual(score["paired_structure_passed"], 20)
            self.assertTrue(score["row_group_scope_pass"])
            self.assertTrue(score["content_pass"])

    def test_t05_separate_physical_cells_fail_despite_exact_numeric_bindings(self):
        payload = self.t05_payload()
        compact = payload["targets"][0]["panels"][0]["data"]
        rows = compact["grid"]
        compact["grid"] = [["Category", "Skills", None, None, None, None, "Wiki Patterns", None, None],
            [None, "Create (Proposed)", "Create (Accepted)", "Edit (Proposed)", "Edit (Accepted)",
             "Avg. Length", "Create", "Edit", "Avg. Length"]]
        for row in rows[2:]:
            compact["grid"].append([row[0]] + [None] * 8 if row[1] is None else
                [row[0]] + [v.strip() for cell in row[1:3] for v in cell.split("/")] + row[3:])
        compact["spans"] = [dict(row=0, col=0, rows=2, cols=1),
            dict(row=0, col=1, rows=1, cols=5), dict(row=0, col=6, rows=1, cols=3)] + [
            dict(row=group["start"], col=0, rows=1, cols=9) for group in compact["row_groups"]]
        compact["roles"] = [dict(row=r, col=c, kind="column") for r, cols in ((0, (0, 1, 6)),
            (1, range(1, 9))) for c in cols] + [dict(row=r, col=0,
            kind="section" if r in (2, 8) else "row") for r in range(2, 14)]
        for score in self.t05_scores(payload):
            self.assertEqual(score["correct_expected_bindings"], 80)
            self.assertEqual(score["critical_comparisons_passed"], 7)
            self.assertEqual(score["paired_structure_passed"], 0)
            self.assertFalse(score["content_pass"])

    def test_t05_reversed_pair_roles_fail_despite_exact_numeric_bindings(self):
        payload = self.t05_payload()
        compact = payload["targets"][0]["panels"][0]["data"]
        for col in (1, 2):
            compact["grid"][1][col] = compact["grid"][1][col].replace(
                "Proposed / Accepted", "Accepted / Proposed")
            for row in (3, 4, 5, 6, 7, 9, 10, 11, 12, 13):
                compact["grid"][row][col] = " / ".join(reversed(compact["grid"][row][col].split(" / ")))
        for score in self.t05_scores(payload):
            self.assertEqual(score["correct_expected_bindings"], 80)
            self.assertEqual(score["critical_comparisons_passed"], 7)
            self.assertEqual(score["paired_structure_passed"], 0)
            self.assertFalse(score["content_pass"])

    def test_t05_missing_explicit_scope_is_rejected(self):
        data, markdown, compact = self.t05_inputs(self.t05_payload())
        with self.assertRaises((TypeError, ValueError)):
            e.t05_views(data, markdown, self.t05, self.cases["G1-T05"])
        for absent in (None, {}, {k: v for k, v in compact.items() if k != "row_groups"}):
            with self.subTest(compact=absent):
                with self.assertRaises((TypeError, ValueError)):
                    e.t05_views(data, markdown, self.t05, self.cases["G1-T05"], compact=absent)

    def test_t05_rendered_numeric_error_does_not_change_typed_score(self):
        data, markdown, compact = self.t05_inputs(self.t05_payload())
        self.assertIn("3.1 / 1.6", markdown)
        typed, rendered = e.t05_views(data, markdown.replace("3.1 / 1.6", "0 / 1.6", 1),
            self.t05, self.cases["G1-T05"], compact=compact)
        self.assertEqual(typed["correct_expected_bindings"], 80)
        self.assertTrue(typed["content_pass"])
        self.assertEqual(rendered["correct_expected_bindings"], 79)
        self.assertEqual(rendered["paired_structure_passed"], 20)
        self.assertEqual(rendered["critical_comparisons_passed"], 6)
        self.assertFalse(rendered["content_pass"])

    def test_t05_wrong_rendered_group_condition_cannot_inherit_compact_label(self):
        data, markdown, compact = self.t05_inputs(self.t05_payload())
        label = "By Model (All-Dataset Average)"
        self.assertIn(label, markdown)
        typed, rendered = e.t05_views(data, markdown.replace(label, "By Model (All-Model Average)"),
            self.t05, self.cases["G1-T05"], compact=compact)
        self.assertEqual(typed["correct_expected_bindings"], 80)
        self.assertTrue(typed["content_pass"])
        self.assertFalse(rendered["row_group_labels_match"])
        self.assertFalse(rendered["row_group_scope_pass"])
        self.assertFalse(rendered["content_pass"])


if __name__ == "__main__":
    unittest.main()
