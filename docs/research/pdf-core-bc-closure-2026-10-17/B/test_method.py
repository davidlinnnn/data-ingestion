"""Synthetic meaning/transport controls only; no source answers or model calls."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from docling_core.types.doc import DoclingDocument, RefItem, RichTableCell, TableData
import method as m

RESEARCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RESEARCH / "pdf-core-direct-cell-2026-10-17"))
spec = importlib.util.spec_from_file_location("bc_closure_prior_gate", RESEARCH / "pdf-core-direct-cell-2026-10-17/gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
sys.path.pop(0)


def fixture():
    return {"panel_label": "", "title": "", "dimension_names": ["Family", "Variant", "Method"],
        "columns": [
            {"key": "create", "path": [{"id": "skills", "text": "Skills"},
                {"id": "create", "text": "Create (Proposed / Accepted)"}]},
            {"key": "length", "path": [{"id": "skills", "text": "Skills"},
                {"id": "length", "text": "Avg. Length"}]}],
        "rows": [
            {"key": "alpha", "dimensions": {"Family": "Family X", "Variant": "small", "Method": "m_one"},
                "group": "all-model", "cells": [
                    {"id": "alpha-pair", "column": "create", "text": "001.20 / 0"},
                    {"id": "alpha-length", "column": "length", "text": ""}]},
            {"key": "beta", "dimensions": {"Family": "Family X", "Variant": "large", "Method": "m_two"},
                "group": "all-model", "cells": [
                    {"id": "beta-pair", "column": "create", "text": "10 / 20"},
                    {"id": "beta-length", "column": "length", "text": r"\frac{a+b}{c} | <s> & x_y"}]}],
        "groups": [{"id": "all-model", "label": "By Model (All-Benchmark Average)", "rows": ["alpha", "beta"]}]}


class SemanticControls(unittest.TestCase):
    def test_normalized_representation_does_not_require_printed_colspans(self):
        panel = fixture(); before = deepcopy(panel)
        data, supplement = m.normalized_panel(panel)
        table = TableData.model_validate(data)
        self.assertEqual(panel, before)
        self.assertEqual([c.text for c in table.grid[0]], ["Section", "Family", "Variant", "Method",
            "Skills / Create (Proposed / Accepted)", "Skills / Avg. Length"])
        self.assertEqual([c.text for c in table.grid[1]],
            ["By Model (All-Benchmark Average)", "Family X", "small", "m_one", "001.20 / 0", ""])
        self.assertTrue(all(c.row_span == c.col_span == 1 for c in table.table_cells))
        pair = next(x for x in supplement["cell_identities"] if x["source_cell_id"] == "alpha-pair")
        self.assertEqual(pair["text"], "001.20 / 0")
        self.assertEqual(pair["normalized_anchor"], [1, 4])
        self.assertEqual(supplement["semantic_provider"], panel)

    def test_public_mapping_true_markdown_reload_caption_and_nontarget(self):
        baseline, keys, payload, _ = gate.fixture()
        snapshot = baseline.model_dump_json()
        data, supplement = m.normalized_panel(fixture())
        payload["targets"][0]["panels"][0]["data"] = data
        out, bindings = m.adapter.map_response(baseline, payload, 1, keys)
        bindings[0]["semantic_supplement"] = supplement
        markdown = m.adapter.export_markdown(out, bindings)
        rendered, _ = gate.rendered_tables(markdown)
        self.assertEqual(rendered[0][2][-1], r"\frac{a+b}{c} | <s> & x_y")
        self.assertEqual(rendered[0][1][-2:], ["001.20 / 0", ""])
        self.assertEqual(baseline.model_dump_json(), snapshot)
        self.assertEqual(markdown.count("Synthetic source caption 1"), 1)
        self.assertEqual(markdown.count("Synthetic source caption 2"), 1)
        self.assertEqual(out.pages, baseline.pages)
        rich = lambda doc: next(t for t in doc.tables if any(isinstance(c, RichTableCell) for c in t.data.table_cells))
        self.assertEqual(gate.source_signature(rich(out), out), gate.source_signature(rich(baseline), baseline))
        loaded = DoclingDocument.model_validate_json(out.model_dump_json())
        self.assertEqual(m.adapter.export_markdown(loaded, json.loads(json.dumps(bindings))), markdown)
        self.assertEqual(bindings[0]["semantic_supplement"]["semantic_provider"]["groups"], fixture()["groups"])

    def test_header_identity_can_share_parent_but_not_conflicting_scope(self):
        panel = fixture()
        panel["columns"][1]["path"][0]["text"] = "Different scope"
        with self.assertRaisesRegex(ValueError, "scope"):
            m.normalized_panel(panel)

    def test_same_text_under_different_scope_ids_not_merged(self):
        panel = fixture()
        panel["columns"][1]["path"] = [{"id": "other-parent", "text": "Other"},
            {"id": "other-create", "text": "Create (Proposed / Accepted)"}]
        data, supplement = m.normalized_panel(panel)
        self.assertEqual(TableData.model_validate(data).grid[0][-1].text,
            "Other / Create (Proposed / Accepted)")
        self.assertEqual(supplement["semantic_provider"]["columns"][1]["path"][1]["id"], "other-create")

    def test_declared_group_and_column_binding_conflicts_reject(self):
        for change in (
            lambda p: p["rows"][0]["cells"].pop(),
            lambda p: p["rows"][0]["cells"][1].update(column="create"),
            lambda p: p["rows"][0].update(group="foreign"),
            lambda p: p["groups"][0]["rows"].reverse(),
            lambda p: p["rows"][0]["dimensions"].pop("Variant"),
            lambda p: p["rows"][0]["cells"][0].update(text=1.2),
            lambda p: p["rows"][0]["cells"][0].update(text={"unknown": True}),
            lambda p: p["rows"][0]["cells"][0].update(unregistered="x"),
        ):
            panel = fixture(); change(panel); before = deepcopy(panel)
            with self.assertRaises((ValueError, TypeError)):
                m.normalized_panel(panel)
            self.assertEqual(panel, before)

    def test_physical_pair_cannot_be_split_by_reusing_identity_with_changed_text(self):
        panel = fixture()
        panel["rows"][0]["cells"][1].update(id="alpha-pair", text="0")
        with self.assertRaisesRegex(ValueError, "split"):
            m.normalized_panel(panel)

    def test_declared_shared_cell_can_keep_common_identity_without_printed_merge(self):
        panel = fixture()
        panel["rows"][0]["cells"][1].update(id="alpha-pair", text="001.20 / 0")
        _, supplement = m.normalized_panel(panel)
        occurrences = [x for x in supplement["cell_identities"] if x["source_cell_id"] == "alpha-pair"]
        self.assertEqual(len(occurrences), 2)
        self.assertEqual({x["text"] for x in occurrences}, {"001.20 / 0"})


class MultipageControls(unittest.TestCase):
    def setUp(self):
        self.baseline, _, self.payload, _ = gate.fixture()
        self.table = self.baseline.tables[0]
        prov = self.table.prov[0].model_copy(deep=True); prov.page_no = 2
        self.table.prov.append(prov)
        self.snapshot = self.baseline.model_dump_json()
        self.digest = sha256(self.snapshot.encode()).hexdigest()
        rows = [["Method", "Score"], ["A", "1.20"], ["Method", "Score"], ["B", "2.50"]]
        self.data = {"num_rows": 4, "num_cols": 2, "table_cells": [
            gate.cell(text, r, c, header=r in (0, 2))
            for r, row in enumerate(rows) for c, text in enumerate(row)]}

    def tearDown(self):
        self.assertEqual(self.baseline.model_dump_json(), self.snapshot)

    def test_existing_inventory_explicitly_refuses_multisource_table(self):
        with self.assertRaisesRegex(ValueError, "multi-page"):
            m.adapter.inventory(self.baseline, 1)

    def test_already_logical_public_replace_preserves_all_other_fields_and_reload(self):
        out, binding = m.replace_already_logical_table(self.baseline, self.table.self_ref, self.digest, self.data)
        target = RefItem(cref=self.table.self_ref).resolve(out)
        self.assertEqual(target.model_dump(exclude={"data"}), self.table.model_dump(exclude={"data"}))
        self.assertEqual(out.model_dump(exclude={"tables"}), self.baseline.model_dump(exclude={"tables"}))
        self.assertEqual(out.tables[1:], self.baseline.tables[1:])
        self.assertEqual([p.page_no for p in target.prov], [1, 2])
        self.assertEqual(target.data.grid[0][0].text, target.data.grid[2][0].text)
        self.assertEqual(len([c for c in target.data.table_cells if c.text == "1.20"]), 1)
        self.assertEqual(binding["original_provenance"], [p.model_dump(mode="json") for p in self.table.prov])
        markdown = m.adapter.export_markdown(out)
        self.assertEqual(markdown.count("Synthetic source caption 1"), 1)
        loaded = DoclingDocument.model_validate_json(out.model_dump_json())
        self.assertEqual(m.adapter.export_markdown(loaded), markdown)
        self.assertTrue(all(c.bbox is None for c in loaded.tables[0].data.table_cells))

    def test_stale_source_invalid_grid_and_missing_logical_owner_refuse(self):
        for change in (lambda d: d.update(num_rows=1),
                       lambda d: d["table_cells"].append(deepcopy(d["table_cells"][0]))):
            data = deepcopy(self.data); change(data)
            with self.assertRaises(ValueError):
                m.replace_already_logical_table(self.baseline, self.table.self_ref, self.digest, data)
        with self.assertRaisesRegex(ValueError, "stale"):
            m.replace_already_logical_table(self.baseline, self.table.self_ref, "old", self.data)
        with self.assertRaisesRegex(ValueError, "already-logical"):
            m.replace_already_logical_table(self.baseline, self.baseline.tables[1].self_ref, self.digest, self.data)


if __name__ == "__main__":
    unittest.main()
