"""Small offline contracts, independent of paper answers and manual bboxes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

from markdown_it import MarkdownIt
from docling_core.types.doc import (BoundingBox, DoclingDocument, DocItemLabel,
                                    ProvenanceItem, Size, TableData, TableCell)
import method as m


def prov(page=1, top=10, span=(0, 0)):
    return ProvenanceItem(page_no=page, bbox=BoundingBox(l=10, t=top, r=190, b=top+10,
                                                       coord_origin="TOPLEFT"), charspan=span)


def document():
    doc = DoclingDocument(name="generic-control")
    for page in (1, 2):
        doc.add_page(page_no=page, size=Size(width=200, height=200))
    return doc


def raw(doc):
    return doc.model_dump(mode="json", by_alias=True)


def block(value, kind="paragraph", indices=(0,), segments=None):
    return {"fragment_indices": list(indices), "kind": kind,
            "segments": segments or [{"kind": {"formula": "math", "code": "code"}.get(kind, "text"), "text": value}]}


def run_ordered(doc, target, blocks, order=None):
    source = raw(doc)
    bound = m.scope(source, [target.self_ref])
    response = {"scope_sha256": m.digest(bound), "targets": {target.self_ref: blocks},
                "order": order or [f"target:{target.self_ref}:{i}" for i in range(len(blocks))]
                              + ["anchor:" + ref for ref in bound["anchors"]]}
    return source, bound, response, m.apply_ordered(source, bound, response)


def interleaved():
    doc = document()
    owner = doc.add_text(label=DocItemLabel.TEXT, text="bodytitle", prov=prov(span=(0, 4)))
    owner.prov.append(prov(top=70, span=(4, 9)))
    middle = doc.add_text(label=DocItemLabel.TEXT, text="middle", prov=prov(top=40, span=(0, 6)))
    order = [f"target:{owner.self_ref}:0", "anchor:"+middle.self_ref, f"target:{owner.self_ref}:1"]
    return run_ordered(doc, owner, [block("BODY"), block("TITLE", "heading", (1,))], order)


class CoreMethodTests(unittest.TestCase):
    def assert_reload(self, result):
        restored = DoclingDocument.model_validate_json(json.dumps(result["document"]))
        self.assertEqual(m.serialize(restored).text, result["markdown"])
        self.assertTrue(restored.validate_tree(restored.body, raise_on_error=True))

    def test_original_interleaving_counterexample(self):
        source, scope, response, result = interleaved()
        md = result["markdown"]
        self.assertLess(md.index("BODY"), md.index("middle"))
        self.assertLess(md.index("middle"), md.index("TITLE"))
        self.assertEqual(md.count("middle"), 1)
        self.assertEqual(result["binding"]["scope"]["provenance"], scope["provenance"])
        restored = DoclingDocument.model_validate(result["document"])
        anchor = m.resolve(restored, result["binding"]["anchor_derived_refs"]["#/texts/1"])
        self.assertEqual(anchor.prov[0].model_dump(mode="json"), source["texts"][1]["prov"][0])
        self.assert_reload(result)

    def test_cross_page_owner_remains_one_block(self):
        doc = document()
        target = doc.add_text(label=DocItemLabel.TEXT, text="first second", prov=prov(span=(0, 5)))
        target.prov.append(prov(page=2, span=(6, 12)))
        *_, result = run_ordered(doc, target, [block("first second", indices=(0, 1))])
        self.assertEqual(result["markdown"].count("first second"), 1)
        derived = DoclingDocument.model_validate(result["document"]).texts[0]
        self.assertEqual([p.page_no for p in derived.prov], [1, 2])
        self.assert_reload(result)

    def test_literal_code_indent_and_html_characters(self):
        doc = document()
        target = doc.add_code(text="native", prov=prov())
        value = 'if items[i] <= limit:\n    emit("<s>&007")'
        *_, result = run_ordered(doc, target, [block(value, "code")])
        self.assertIn(value, result["markdown"])
        rendered = MarkdownIt().render(result["markdown"])
        self.assertIn("&lt;s&gt;&amp;007", rendered)
        self.assert_reload(result)

    def test_prose_inline_math_and_code(self):
        doc = document()
        target = doc.add_text(label=DocItemLabel.TEXT, text="native", prov=prov())
        segments = [{"kind":"text", "text":"Let <s> & "}, {"kind":"math", "text":r"x^{2}+1"},
                    {"kind":"text", "text":"; call "}, {"kind":"code", "text":"items[i]"}]
        *_, result = run_ordered(doc, target, [block("", segments=segments)])
        self.assertIn(r"x^{2}+1", result["markdown"])
        self.assertIn("$", result["markdown"])
        self.assertIn("items[i]", result["markdown"])
        self.assertIn("&lt;s&gt;", MarkdownIt().render(result["markdown"]))
        self.assert_reload(result)

    def test_empty_native_display_formula(self):
        doc = document()
        target = doc.add_formula(text="", prov=prov())
        *_, result = run_ordered(doc, target, [block(r"\frac{1}{x}", "formula")])
        self.assertIn(r"\frac{1}{x}", result["markdown"])
        self.assertIn("$$", result["markdown"])
        self.assert_reload(result)

    def test_ordinary_negative(self):
        doc = document()
        target = doc.add_text(label=DocItemLabel.TEXT, text="ordinary prose", prov=prov(span=(0, 14)))
        *_, result = run_ordered(doc, target, [block(target.text)])
        self.assertEqual(result["markdown"], m.serialize(doc).text)
        self.assert_reload(result)

    def test_plain_caption_keeps_table_and_one_caption(self):
        doc = document()
        table = doc.add_table(data=TableData(num_rows=1, num_cols=1, table_cells=[
            TableCell(text="tool_call(x)", start_row_offset_idx=0, end_row_offset_idx=1,
                      start_col_offset_idx=0, end_col_offset_idx=1)]), prov=prov())
        caption = doc.add_text(label=DocItemLabel.CAPTION, text="native caption", parent=table, prov=prov(top=30))
        table.captions = [caption.get_ref()]
        source = raw(doc)
        result = m.apply_caption(source, caption.self_ref, block("Table CAPTION"))
        self.assertEqual(result["markdown"].count("CAPTION"), 1)
        self.assertIn("tool_call(x)", result["markdown"])
        restored = DoclingDocument.model_validate(result["document"])
        self.assertEqual(restored.tables[0].data.model_dump(), table.data.model_dump())
        self.assert_reload(result)

    def test_picture_child_retains_image_caption_and_provenance(self):
        doc = document()
        picture = doc.add_picture(prov=prov())
        child = doc.add_formula(text="", parent=picture, prov=prov())
        caption = doc.add_text(label=DocItemLabel.CAPTION, text="PICTURE CAPTION", parent=picture, prov=prov(top=30))
        picture.captions = [caption.get_ref()]
        source = raw(doc)
        result = m.expose_formula_picture(source, picture.self_ref, [block("x^2+1", "formula")])
        self.assertEqual(result["markdown"].count("x^2+1"), 1)
        self.assertEqual(result["markdown"].count("PICTURE CAPTION"), 1)
        restored = DoclingDocument.model_validate(result["document"])
        self.assertEqual(restored.pictures[0].prov, picture.prov)
        self.assertEqual(restored.pictures[0].image, picture.image)
        self.assertEqual(result["binding"]["formulas"][0]["source_provenance"], source["texts"][0]["prov"])
        self.assert_reload(result)

    def test_table_text_is_owned_by_table_not_a_job(self):
        doc = document()
        table = doc.add_table(data=TableData(num_rows=1, num_cols=1, table_cells=[
            TableCell(text="tool_call(x)", start_row_offset_idx=0, end_row_offset_idx=1,
                      start_col_offset_idx=0, end_col_offset_idx=1)]), prov=prov())
        rows, markdown = m.native_inventory(raw(doc))
        cell = next(row for row in rows if row["native_label"] == "table_cell")
        self.assertEqual(cell["responsibility"], "table")
        self.assertFalse(cell["eligible"])
        self.assertTrue(cell["delivered"])
        self.assertIn("tool_call(x)", markdown)

    def test_invalid_response_boundaries(self):
        source, scope, response, _ = interleaved()
        mutations = {}
        value = deepcopy(response); value["scope_sha256"] = "0"*64; mutations["foreign"] = value
        value = deepcopy(response); value["targets"] = {}; mutations["missing_target"] = value
        value = deepcopy(response); value["targets"]["#/texts/999"] = value["targets"].pop("#/texts/0"); mutations["unknown_target"] = value
        value = deepcopy(response); value["order"].append(value["order"][0]); mutations["duplicate_token"] = value
        value = deepcopy(response); value["order"].pop(); mutations["missing_fragment_token"] = value
        value = deepcopy(response); value["targets"]["#/texts/0"][1]["fragment_indices"] = [0]; mutations["overlapping_fragments"] = value
        value = deepcopy(response); value["targets"]["#/texts/0"][1]["fragment_indices"] = []; mutations["missing_source_fragment"] = value
        value = deepcopy(response); value["targets"]["#/texts/0"][1]["fragment_indices"] = [999]; mutations["foreign_fragment"] = value
        value = deepcopy(response); value["targets"]["#/texts/0"][0]["segments"][0]["text"] = ""; mutations["empty_output"] = value
        value = deepcopy(response); value["targets"]["#/texts/0"][0]["segments"][0]["kind"] = "unknown"; mutations["unknown_output"] = value
        value = deepcopy(response); value["unexpected"] = True; mutations["unknown_field"] = value
        for name, value in mutations.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                m.apply_ordered(source, scope, value)
        changed = deepcopy(source); changed["texts"][1]["text"] += " stale"
        with self.assertRaises(ValueError):
            m.apply_ordered(changed, scope, response)
        with self.assertRaises(ValueError):
            m.scope(source, ["#/texts/0", "#/texts/0"])

    def test_non_target_anchor_order_cannot_change(self):
        doc = document()
        target = doc.add_text(label=DocItemLabel.TEXT, text="target", prov=prov())
        left = doc.add_text(label=DocItemLabel.TEXT, text="LEFT", prov=prov(top=50))
        right = doc.add_text(label=DocItemLabel.TEXT, text="RIGHT", prov=prov(top=70))
        source, scope, response, _ = run_ordered(doc, target, [block("replacement")])
        response["order"][1:] = response["order"][1:][::-1]
        with self.assertRaises(ValueError):
            m.apply_ordered(source, scope, response)

    def test_picture_with_prose_child_cannot_be_formula_envelope(self):
        doc = document()
        picture = doc.add_picture(prov=prov())
        doc.add_text(label=DocItemLabel.TEXT, text="figure prose", parent=picture, prov=prov())
        with self.assertRaises(ValueError):
            m.expose_formula_picture(raw(doc), picture.self_ref, [block("x", "formula")])

    def test_caption_inline_is_explicitly_unsupported(self):
        doc = document()
        picture = doc.add_picture(prov=prov())
        caption = doc.add_text(label=DocItemLabel.CAPTION, text="native caption", parent=picture, prov=prov())
        picture.captions = [caption.get_ref()]
        with self.assertRaisesRegex(ValueError, "stock caption serializer"):
            m.apply_caption(raw(doc), caption.self_ref, block("", segments=[
                {"kind":"text", "text":"Let "}, {"kind":"math", "text":"x^2"}]))

    def test_caption_and_picture_child_cannot_enter_body_path(self):
        doc = document()
        picture = doc.add_picture(prov=prov())
        child = doc.add_formula(text="", parent=picture, prov=prov())
        caption = doc.add_text(label=DocItemLabel.CAPTION, text="caption", prov=prov(top=30))
        picture.captions = [caption.get_ref()]
        for reference in (child.self_ref, caption.self_ref):
            with self.subTest(reference=reference), self.assertRaisesRegex(ValueError, "render owner"):
                m.scope(raw(doc), [reference])

    def test_source_geometry_is_checked(self):
        source, scope, response, _ = interleaved()
        source["texts"][0]["prov"][0]["bbox"]["r"] = 500
        with self.assertRaisesRegex(ValueError, "geometry"):
            m.scope(source, ["#/texts/0"])

    def test_native_list_marker_is_retained(self):
        doc = document()
        group = doc.add_list_group()
        target = doc.add_list_item(text="ordered prose", marker="7.", enumerated=True,
                                   parent=group, prov=prov())
        *_, result = run_ordered(doc, target, [block("ordered prose")])
        self.assertEqual(result["markdown"], m.serialize(doc).text)
        restored = DoclingDocument.model_validate(result["document"])
        self.assertEqual(restored.texts[0].marker, "7.")
        self.assertTrue(restored.texts[0].enumerated)
        self.assert_reload(result)

    def test_saved_inventory_and_replays_match_inputs(self):
        inventory_path = Path(__file__).parent / "inventory.json"
        inventory = json.loads(inventory_path.read_text())
        self.assertEqual(inventory["method_sha256"], hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest())
        report = json.loads((Path(__file__).parent/"replay-results.json").read_text())
        self.assertEqual(report["inventory_sha256"], hashlib.sha256(inventory_path.read_bytes()).hexdigest())
        for source in inventory["sources"]:
            with self.subTest(source=source["source"]):
                path = m.REPO / source["document_path"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source["document_sha256"])
                folder = Path(__file__).parent/"mock-replay"/source["source"]
                restored = DoclingDocument.model_validate_json((folder/"document.json").read_text())
                self.assertEqual(m.serialize(restored).text.encode("utf-8"), (folder/"document.md").read_bytes())
                self.assertTrue(restored.validate_tree(restored.body, raise_on_error=True))
        for filename, key in (("group-replay-results.json", "groups"), ("picture-replay-results.json", "formula_pictures")):
            report = json.loads((Path(__file__).parent/filename).read_text())
            self.assertEqual(report["inventory_sha256"], hashlib.sha256(inventory_path.read_bytes()).hexdigest())
            for row in report[key]:
                folder = Path(__file__).parent/row["output"]
                result = json.loads((folder/"result.json").read_text())
                self.assert_reload(result)
                self.assertEqual(result["markdown"].encode("utf-8"), (folder/"document.md").read_bytes())


def record():
    source, scope, response, result = interleaved()
    folder = Path(__file__).parent / "controls" / "interleaved-fragments"
    folder.mkdir(parents=True, exist_ok=True)
    for name, value in {"input.json": source, "scope.json": scope, "response.json": response,
                        "result.json": result, "document.json": result["document"]}.items():
        with (folder/name).open("x") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2); stream.write("\n")
    with (folder/"document.md").open("x") as stream:
        stream.write(result["markdown"])


if __name__ == "__main__":
    if "--record" in sys.argv:
        record()
    else:
        unittest.main()
