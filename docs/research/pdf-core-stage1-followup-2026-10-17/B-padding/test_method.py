"""Source-independent controls for the explicit-span padding candidate; no inference."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from docling_core.types.doc import DoclingDocument, RefItem

import method as m


HERE = Path(__file__).resolve().parent


class PaddingControls(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads((HERE.parent / "B/synthetic-input.json").read_text())
        self.keys = [target["target_key"] for target in self.payload["targets"]]
        self.baseline = DoclingDocument.model_validate_json((HERE.parent / "B/baseline.json").read_text())
        self.baseline_before = self.baseline.model_dump_json()

    def tearDown(self):
        self.assertEqual(self.baseline.model_dump_json(), self.baseline_before)

    @staticmethod
    def data(payload):
        return payload["targets"][1]["panels"][0]["data"]

    def blank_padding(self):
        payload = deepcopy(self.payload)
        for row in self.data(payload)["grid"]:
            for col, value in enumerate(row):
                if value is None:
                    row[col] = ""
        return payload

    def test_exact_empty_padding_equals_null_and_is_immutable_idempotent(self):
        payload = self.blank_padding()
        before = deepcopy(payload)
        parsed, padding = m.parse(payload, self.keys)
        expected, no_padding = m.parse(self.payload, self.keys)
        self.assertEqual(parsed.model_dump(mode="json"), expected.model_dump(mode="json"))
        self.assertTrue(padding)
        self.assertFalse(no_padding)
        again, padding_again = m.parse(parsed.model_dump(mode="json"), self.keys)
        self.assertEqual(again, parsed)
        self.assertEqual(padding_again, [])
        self.assertEqual(payload, before)

    def test_map_matches_null_data_and_retains_original_transport(self):
        payload = self.blank_padding()
        before = deepcopy(payload)
        null_doc, null_bindings = m.map_response(self.baseline, self.payload, 1, self.keys)
        blank_doc, blank_bindings = m.map_response(self.baseline, payload, 1, self.keys)
        self.assertEqual(blank_doc.model_dump(mode="json"), null_doc.model_dump(mode="json"))
        for target, blank, null in zip(payload["targets"], blank_bindings, null_bindings, strict=True):
            self.assertEqual(blank["transport_provider"], target)
            self.assertEqual(blank["compact_provider"], null["compact_provider"])
        self.assertTrue(blank_bindings[1]["covered_padding"])
        self.assertEqual(payload, before)

    def test_uncovered_literals_and_known_blank_are_unchanged(self):
        parsed, _ = m.parse(self.blank_padding(), self.keys)
        expected = m.strict.parse(self.payload, self.keys)
        self.assertEqual(parsed.targets[0], expected.targets[0])
        self.assertEqual(parsed.targets[1].panels[0].data.grid[3],
                         ["Method X", "Setting one", "001.20", "0", "", "1.2 ± 0.3"])
        self.assertEqual(parsed.targets[1].panels[0].data.grid[4][1:],
                         ["Setting two", "—", "-0.0", "1e-3", "10 / 20"])

    def test_covered_nonempty_values_are_not_erased(self):
        for value in (" ", "\t", "0", "—", "-", "001.20", {"unknown": True}):
            with self.subTest(value=value):
                payload = self.blank_padding()
                self.data(payload)["grid"][1][0] = value
                before = deepcopy(payload)
                with self.assertRaises(ValueError):
                    m.map_response(self.baseline, payload, 1, self.keys)
                self.assertEqual(payload, before)

    def test_existing_structural_failures_still_reject(self):
        changes = {
            "ragged": lambda d: d["grid"][0].append("extra"),
            "overlap": lambda d: d["spans"].append(deepcopy(d["spans"][0])),
            "outside": lambda d: d["spans"][0].update(rows=999),
            "unit span": lambda d: d["spans"][0].update(rows=1, cols=1),
            "null anchor": lambda d: d["grid"][0].__setitem__(0, None),
            "unowned null": lambda d: d["grid"][3].__setitem__(2, None),
            "covered role": lambda d: d["roles"].append(dict(row=1, col=0, kind="column")),
            "missing scope": lambda d: d["row_groups"].pop(),
            "numeric coercion": lambda d: d["grid"][3].__setitem__(2, 1.2),
            "boolean span": lambda d: d["spans"][0].update(rows=True),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                payload = self.blank_padding()
                change(self.data(payload))
                before = deepcopy(payload)
                with self.assertRaises(ValueError):
                    m.parse(payload, self.keys)
                self.assertEqual(payload, before)

    def test_unknown_fields_still_reject_at_each_shape(self):
        for location in ("root", "target", "panel", "data", "span", "role", "group"):
            with self.subTest(location=location):
                payload = self.blank_padding()
                target = payload["targets"][1]
                panel = target["panels"][0]
                data = panel["data"]
                node = {"root": payload, "target": target, "panel": panel, "data": data,
                        "span": data["spans"][0], "role": data["roles"][0],
                        "group": data["row_groups"][0]}[location]
                node["unregistered"] = "must not be moved or dropped"
                with self.assertRaises(ValueError):
                    m.parse(payload, self.keys)

    def test_target_inventory_is_exact(self):
        for name in ("missing", "duplicate", "foreign"):
            with self.subTest(name=name):
                payload = self.blank_padding()
                if name == "missing":
                    payload["targets"].pop()
                elif name == "duplicate":
                    payload["targets"].append(deepcopy(payload["targets"][0]))
                else:
                    payload["targets"][0]["target_key"] = "foreign"
                with self.assertRaises(ValueError):
                    m.map_response(self.baseline, payload, 1, self.keys)

    def test_mapper_requires_all_page_targets_even_when_parse_keys_match(self):
        payload = self.blank_padding()
        payload["targets"].pop()
        subset = self.keys[:1]
        m.parse(payload, subset)
        with self.assertRaisesRegex(ValueError, "complete page target inventory"):
            m.map_response(self.baseline, payload, 1, subset)

    def test_multiple_panels_map_and_one_bad_panel_blocks_whole_page(self):
        payload = self.blank_padding()
        panels = payload["targets"][1]["panels"]
        panels.append(deepcopy(panels[0]))
        panels[1]["panel_label"] = "second panel"
        doc, bindings = m.map_response(self.baseline, payload, 1, self.keys)
        self.assertEqual(len(bindings[1]["panels"]), 2)
        left, right = [RefItem(cref=p["table_ref"]).resolve(doc) for p in bindings[1]["panels"]]
        self.assertEqual(left.data, right.data)
        self.assertEqual({item["panel"] for item in bindings[1]["covered_padding"]}, {0, 1})
        panels[1]["data"]["grid"][1][0] = "not padding"
        with self.assertRaises(ValueError):
            m.map_response(self.baseline, payload, 1, self.keys)

    def test_section_role_does_not_clear_other_nonempty_cells_or_infer_span(self):
        payload = deepcopy(self.payload)
        payload["targets"][0]["panels"][0]["data"] = dict(
            grid=[["Header", "Value"], ["Section", "retain side value"], ["", "0"]],
            spans=[dict(row=1, col=0, rows=2, cols=1)],
            roles=[dict(row=0, col=0, kind="column"), dict(row=0, col=1, kind="column"),
                   dict(row=1, col=0, kind="section")],
            row_groups=[dict(start=1, end=3, label_row=1, label_col=0)])
        before = deepcopy(payload)
        doc, bindings = m.map_response(self.baseline, payload, 1, self.keys)
        table = RefItem(cref=bindings[0]["panels"][0]["table_ref"]).resolve(doc)
        self.assertEqual(table.data.grid[1][1].text, "retain side value")
        self.assertEqual(table.data.grid[2][1].text, "0")
        self.assertIn("retain side value", m.strict.adapter.export_markdown(doc, bindings))
        self.assertEqual(bindings[0]["compact_provider"]["panels"][0]["data"]["spans"],
                         before["targets"][0]["panels"][0]["data"]["spans"])
        self.assertEqual(payload, before)


if __name__ == "__main__":
    unittest.main()
