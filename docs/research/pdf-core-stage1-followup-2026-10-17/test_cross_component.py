"""Synthetic transfer only; this does not assess model reconstruction accuracy."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
from hashlib import sha256
from tempfile import TemporaryDirectory

from docling_core.types.doc import DoclingDocument, RefItem

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TableTransfer(unittest.TestCase):
    def test_math_and_code_strings_survive_typed_and_actual_markdown(self):
        method = load("ab_padding", HERE / "B-padding/method.py")
        helper = method.strict.load("ab_html", HERE.parent / "pdf-core-table-crops-2026-10-17/evaluate-t05.py")
        payload = json.loads((HERE / "B/synthetic-input.json").read_text())
        baseline = DoclingDocument.model_validate_json((HERE / "B/baseline.json").read_text())
        literals = [r"\frac{a+b}{c}", r"$x_{i+1}=x_i+\alpha$", r"\sum_{j=1}^{n} w_j",
                    "max_steps = 3  # <s> & literal", "'007' != '7'", "name_with_underscore()"]
        for row, text in zip(payload["targets"][0]["panels"][0]["data"]["grid"][1:], literals):
            row[1] = text
        before, original = baseline.model_dump_json(), deepcopy(payload)
        doc, bindings = method.map_response(baseline, payload, 1, [target["target_key"] for target in payload["targets"]])
        table = RefItem(cref=bindings[0]["panels"][0]["table_ref"]).resolve(doc)
        self.assertEqual([row[1].text for row in table.data.grid[1:1+len(literals)]], literals)
        markdown = method.strict.adapter.export_markdown(doc, bindings)
        parser = helper.RenderedTables()
        from markdown_it import MarkdownIt
        parser.feed(MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown))
        self.assertEqual([row[1] for row in parser.tables[0][1:1+len(literals)]],
                         [helper.previous.norm(text) for text in literals])
        loaded = DoclingDocument.model_validate_json(doc.model_dump_json())
        self.assertEqual(method.strict.adapter.export_markdown(loaded, bindings), markdown)
        self.assertEqual(baseline.model_dump_json(), before)
        self.assertEqual(payload, original)


class CompareOnlyCheck(unittest.TestCase):
    def test_changed_evidence_is_rejected_without_refreshing_expected_hash(self):
        checker = load("abc_compare_only", HERE / "check.py")
        with TemporaryDirectory() as directory:
            file = Path(directory) / "evidence.json"
            file.write_text('{"value": "original"}')
            expected = {file.name: sha256(file.read_bytes()).hexdigest()}
            self.assertEqual(checker.compare_hashes(directory, expected), 1)
            before = deepcopy(expected)
            file.write_text('{"value": "changed"}')
            with self.assertRaises(ValueError):
                checker.compare_hashes(directory, expected)
            self.assertEqual(expected, before)
            self.assertEqual(file.read_text(), '{"value": "changed"}')


if __name__ == "__main__":
    unittest.main()
