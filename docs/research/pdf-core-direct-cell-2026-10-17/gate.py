"""Source-independent A gate; no candidate PDF, oracle, model or network access."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
from importlib.metadata import version
import json
from pathlib import Path
import sys
import time

from docling_core.types.doc import (
    BoundingBox, DocItemLabel, DoclingDocument, PageItem, ProvenanceItem,
    RefItem, RichTableCell, Size, TableCell, TableData,
)
from markdown_it import MarkdownIt

import adapter

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "pdf-core-table-delivery-2026-10-17"
sys.path.insert(0, str(OLD))
spec = importlib.util.spec_from_file_location("delivery_graph_controls", OLD / "verify.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)  # The oracle-reading main is deliberately not invoked.
sys.path.pop(0)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def cell(text, row, col, *, height=1, width=1, header=False, row_header=False, section=False):
    return dict(text=text, start_row_offset_idx=row, end_row_offset_idx=row + height,
                start_col_offset_idx=col, end_col_offset_idx=col + width,
                row_span=height, col_span=width, column_header=header,
                row_header=row_header, row_section=section)


def source_signature(node, doc):
    """Public node deletion renumbers refs; compare the preserved referenced source."""
    def normalize(value):
        if isinstance(value, dict):
            if set(value) in ({"$ref"}, {"cref"}):
                ref = value.get("$ref", value.get("cref"))
                return {"resolved_source": normalize(old.signature(RefItem(cref=ref).resolve(doc)))}
            return {key: normalize(child) for key, child in value.items()}
        if isinstance(value, list):
            return [normalize(child) for child in value]
        return value
    return normalize(old.signature(node))


def rendered_tables(markdown):
    """Read actual CommonMark inline semantics, rather than splitting raw pipes."""
    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    tables, table, row, value = [], None, None, None
    for token in parser.parse(markdown):
        if token.type == "table_open":
            table = []
        elif token.type == "tr_open":
            row = []
        elif token.type in ("th_open", "td_open"):
            value = []
        elif token.type == "inline" and value is not None:
            assert not any(t.type in ("html_inline", "image") for t in token.children or []), "unexpected active cell HTML/image"
            value.extend(t.content for t in token.children or [] if t.type in ("text", "code_inline"))
        elif token.type in ("th_close", "td_close"):
            row.append("".join(value))
            value = None
        elif token.type == "tr_close":
            table.append(row)
        elif token.type == "table_close":
            tables.append(table)
    return tables, parser.render(markdown)


def fixture():
    doc = DoclingDocument(name="synthetic complete-cell source")
    for page in (1, 2):
        doc.pages[page] = PageItem(page_no=page, size=Size(width=600, height=800))
    doc.add_text(label=DocItemLabel.TEXT, text="Body before target tables")
    for index in range(2):
        table = doc.add_table(data=TableData(num_rows=1, num_cols=1, table_cells=[TableCell(**cell("Old native content", 0, 0))]),
            prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=20, t=20 + index * 300, r=580, b=280 + index * 300), charspan=(0, 0)))
        caption = doc.add_text(label=DocItemLabel.CAPTION, text=f"Synthetic source caption {index + 1}", parent=table)
        table.captions.append(caption.get_ref())
        doc.add_text(label=DocItemLabel.TEXT, text=f"Body after target {index + 1}")
    rich = doc.add_table(data=TableData(num_rows=1, num_cols=1),
        prov=ProvenanceItem(page_no=2, bbox=BoundingBox(l=20, t=20, r=580, b=200), charspan=(0, 0)))
    child = doc.add_text(label=DocItemLabel.TEXT, text="Untouched rich text", parent=rich)
    doc.add_table_cell(rich, RichTableCell(**cell("", 0, 0), ref=child.get_ref()))
    doc.add_text(label=DocItemLabel.TEXT, text="Body after non-target rich table")
    keys = list(adapter.inventory(doc, 1))
    literals = ["<s>", "&lt;s&gt;", "& x < 7 | y", "*literal*", "**bold**", "a_b_c", "`x`",
                "[x](https://example.invalid)", "![x](file.png)", r"\*x\*", r"a\b", "001.20", "0", "", "—",
                "CR\rline", "CRLF\r\nline", "LF\nline"]
    ordinary = [cell("Method", 0, 0, header=True, row_header=True), cell("Value", 0, 1, header=True)]
    for r, text in enumerate(literals, 1):
        ordinary.extend([cell(f"Literal {r}", r, 0, row_header=True), cell(text, r, 1)])
    complex_cells = [
        cell("Method", 0, 0, height=2, header=True, row_header=True),
        cell("Setting", 0, 1, height=2, header=True),
        cell("A", 0, 2, width=2, header=True), cell("B", 0, 4, width=2, header=True),
        cell("Score", 1, 2, header=True), cell("Spread", 1, 3, header=True),
        cell("Score", 1, 4, header=True), cell("Spread", 1, 5, header=True),
        cell("Group alpha", 2, 0, width=6, section=True),
        cell("Method X", 3, 0, height=2, row_header=True),
        cell("Setting one", 3, 1, row_header=True), cell("001.20", 3, 2), cell("0", 3, 3), cell("", 3, 4), cell("1.2 ± 0.3", 3, 5),
        cell("Setting two", 4, 1, row_header=True), cell("—", 4, 2), cell("-0.0", 4, 3), cell("1e-3", 4, 4), cell("10 / 20", 4, 5),
        cell("Group beta", 5, 0, width=6, section=True),
        cell("Method Y", 6, 0, row_header=True), cell("Setting three", 6, 1, row_header=True),
        cell("9", 6, 2), cell("0.00", 6, 3), cell("8", 6, 4), cell("2.0 ± 0.4", 6, 5),
    ]
    payload = {"targets": []}
    for key, data in zip(keys, [dict(num_rows=len(literals) + 1, num_cols=2, table_cells=ordinary),
                                dict(num_rows=7, num_cols=6, table_cells=complex_cells)], strict=True):
        payload["targets"].append(dict(target_key=key, caption="", conditions=[], uncertainties=[],
                                       panels=[dict(panel_label="", title="", data=data)]))
    return doc, keys, payload, literals


def checks():
    doc, keys, payload, literals = fixture()
    original = doc.model_dump_json()
    baseline_md = doc.export_to_markdown()
    old.assert_graph(doc)
    parsed = adapter.parse_response(payload, keys)
    assert parsed.targets[0].panels[0].data.table_cells[0].column_header
    assert parsed.targets[0].panels[0].data.table_cells[0].row_header, "legal corner must survive"
    original_targets = adapter.inventory(doc, 1)
    excluded = {node.self_ref for target in original_targets.values() for node in old.walk(doc, target)}
    untouched = [source_signature(n, doc) for n in old.walk(doc) if n.self_ref not in excluded]
    captions = [[old.signature(r.resolve(doc)) for r in target.captions] for target in original_targets.values()]
    out, bindings = adapter.map_response(doc, payload, 1, keys)
    assert doc.model_dump_json() == original
    old.assert_graph(out)
    changed = {node.self_ref for binding in bindings for node in old.walk(out, RefItem(cref=binding["group_ref"]).resolve(out))}
    assert [source_signature(n, out) for n in old.walk(out) if n.self_ref not in changed] == untouched
    assert out.pages == doc.pages and out.origin == doc.origin and out.furniture == doc.furniture
    for binding, expected, source, caption in zip(bindings, payload["targets"], original_targets.values(), captions, strict=True):
        assert [old.signature(RefItem(cref=r).resolve(out)) for r in binding["captions"]] == caption
        assert len(binding["panels"]) == 1
        table = RefItem(cref=binding["panels"][0]["table_ref"]).resolve(out)
        assert table.prov == source.prov
        assert all(c.bbox is None for c in table.data.table_cells)
        assert [c.model_dump(include=set(expected["panels"][0]["data"]["table_cells"][0])) for c in table.data.table_cells] == expected["panels"][0]["data"]["table_cells"]
    complex_table = RefItem(cref=bindings[1]["panels"][0]["table_ref"]).resolve(out)
    assert len(complex_table.data.table_cells) == len(payload["targets"][1]["panels"][0]["data"]["table_cells"])
    assert complex_table.data.grid[3][5].text == "1.2 ± 0.3" and complex_table.data.grid[3][5].col_span == 1
    assert complex_table.data.grid[3][0] is complex_table.data.grid[4][0]
    assert complex_table.data.grid[2][0].row_section and not complex_table.data.grid[2][0].column_header
    before_render = out.model_dump_json()
    serialized = adapter.serialize(out, bindings)
    markdown = serialized.text
    assert adapter.export_markdown(out, bindings) == markdown
    assert out.model_dump_json() == before_render
    for span in serialized.spans:
        assert span.item.model_dump_json() == span.item.get_ref().resolve(out).model_dump_json(), "render copy escaped into source spans"
    tables, rendered = rendered_tables(markdown)
    assert len(tables) == 3
    assert tables[0] == [["Method", "Value"]] + [[f"Literal {i}", " ".join(text.splitlines())] for i, text in enumerate(literals, 1)]
    assert tables[1] == [
        ["Method", "Setting", "A - Score", "A - Spread", "B - Score", "B - Spread"],
        ["Group alpha"] * 6,
        ["Method X", "Setting one", "001.20", "0", "", "1.2 ± 0.3"],
        ["Method X", "Setting two", "—", "-0.0", "1e-3", "10 / 20"],
        ["Group beta"] * 6,
        ["Method Y", "Setting three", "9", "0.00", "8", "2.0 ± 0.4"],
    ]
    assert tables[2] == rendered_tables(baseline_md)[0][-1], "non-target rich output changed"
    ordered = ["Body before target tables", "Synthetic source caption 1", "Body after target 1",
               "Synthetic source caption 2", "Body after target 2", "Untouched rich", "Body after non-target rich table"]
    assert [markdown.index(s) for s in ordered] == sorted(markdown.index(s) for s in ordered)
    assert all(markdown.count(f"Synthetic source caption {i}") == 1 for i in (1, 2))
    loaded = DoclingDocument.model_validate_json(out.model_dump_json())
    old.assert_graph(loaded)
    assert adapter.export_markdown(loaded, bindings) == markdown
    assert loaded.model_dump(mode="json") == out.model_dump(mode="json")
    rejected = []
    variants = {}
    def variant(name, change):
        value = deepcopy(payload)
        change(value)
        variants[name] = value
    def first(value):
        return value["targets"][0]["panels"][0]["data"]
    variant("missing target", lambda v: v["targets"].pop())
    variant("duplicate target", lambda v: v["targets"].append(deepcopy(v["targets"][0])))
    variant("unknown target", lambda v: v["targets"][0].__setitem__("target_key", "unknown"))
    variant("unknown root key", lambda v: v.__setitem__("extra", 1))
    variant("unknown table key", lambda v: first(v).__setitem__("orientation", "rot_0"))
    variant("missing cell", lambda v: first(v)["table_cells"].pop())
    variant("duplicate overlap", lambda v: first(v)["table_cells"].append(deepcopy(first(v)["table_cells"][0])))
    for field, value in [("num_rows", 0), ("num_cols", 0), ("num_rows", 257), ("num_cols", 65),
                         ("num_rows", True), ("num_rows", 16.0), ("num_cols", "2")]:
        variant(f"dimension {field} {value!r}", lambda v, f=field, x=value: first(v).__setitem__(f, x))
    for field, value in [("start_row_offset_idx", -1), ("start_col_offset_idx", -1),
                         ("end_row_offset_idx", 999), ("end_col_offset_idx", 999),
                         ("end_row_offset_idx", 0), ("row_span", 0), ("col_span", 2),
                         ("row_span", True), ("start_row_offset_idx", 0.0), ("column_header", 1),
                         ("text", 1.2), ("text", None), ("ref", {"$ref": "#/texts/0"}),
                         ("bbox", None), ("fillable", False), ("row_section", True)]:
        variant(f"cell {field} {value!r}", lambda v, f=field, x=value: first(v)["table_cells"][0].__setitem__(f, x))
    variant("missing text", lambda v: first(v)["table_cells"][0].pop("text"))
    variant("unknown panel key", lambda v: v["targets"][0]["panels"][0].__setitem__("extra", 0))
    variant("unknown target key", lambda v: v["targets"][0].__setitem__("extra", 0))
    for name, value in variants.items():
        try:
            adapter.map_response(doc, value, 1, keys)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(f"invalid producer accepted: {name}")
        assert doc.model_dump_json() == original, f"partial mutation on {name}"
    for name, selected in [("unknown registered key", ["absent"]), ("duplicate registered key", keys + keys[:1]),
                            ("empty registered keys", [])]:
        try:
            adapter.map_response(doc, payload, 1, selected)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(name)
    invalid_source = doc.model_copy(deep=True)
    invalid_source.tables[0].prov[0].bbox.r = 601
    rich_source = doc.model_copy(deep=True)
    rich_target = rich_source.tables[0]
    child = rich_source.add_text(label=DocItemLabel.TEXT, text="Rich target body", parent=rich_target)
    rich_target.data = TableData(num_rows=1, num_cols=1, table_cells=[RichTableCell(**cell("", 0, 0), ref=child.get_ref())])
    special_label = doc.model_copy(deep=True)
    special_label.tables[0].label = DocItemLabel.DOCUMENT_INDEX
    comment_source = doc.model_copy(deep=True)
    comment_source.tables[0].comments.append(comment_source.tables[0].captions[0])
    for name, source in [("out-of-page source", invalid_source), ("rich target", rich_source),
                         ("non-default table label", special_label), ("non-default target comments", comment_source)]:
        before = source.model_dump_json()
        try:
            adapter.map_response(source, payload, 1, keys)
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError(name)
        assert source.model_dump_json() == before
    # Structurally valid invented content remains the evaluator's responsibility.
    wrong = deepcopy(payload)
    wrong["targets"][0]["panels"][0]["data"]["table_cells"][3]["text"] = "999999"
    adapter.parse_response(wrong, keys)
    repeated = deepcopy(payload)
    repeated["targets"][0]["panels"].append(deepcopy(repeated["targets"][0]["panels"][0]))
    repeat_doc, repeat_bindings = adapter.map_response(doc, repeated, 1, keys)
    old.assert_graph(repeat_doc)
    repeat_refs = [p["table_ref"] for b in repeat_bindings for p in b["panels"]]
    assert len(repeat_refs) == len(set(repeat_refs)) == 3, "ordered panel identity must not merge repeated source labels"
    assert doc.model_dump_json() == original
    (HERE / "synthetic-input.json").write_text(original + "\n")
    write("synthetic-response.json", payload)
    (HERE / "synthetic-document.json").write_text(out.model_dump_json(indent=2) + "\n")
    (HERE / "synthetic-document.md").write_text(markdown + "\n")
    (HERE / "synthetic-rendered.html").write_text(rendered + "\n")
    write("synthetic-bindings.json", bindings)
    return {"checks": ["complete plain cells and legal corner", "multi-dimensional row labels", "stacked headers with repeated metric names",
        "rowspan and colspan roles retained", "row sections stay out of global headers", "paired values remain one physical typed cell",
        "blank versus missing versus zero versus precision", "literal HTML entities and Markdown render faithfully",
        "CR/LF display wraps flatten to spaces; canonical source retained", "caption once and body order unchanged",
        "non-target rich table preserved", "whole-table provenance only; no invented cell geometry", "all source spans original", "canonical immutable during serialization",
        "complete graph and JSON reload", "repeated or empty panel labels retain independent ordered identities",
        "source-incorrect but schema-valid text not repaired"], "rejected": rejected}


def main():
    start = time.perf_counter()
    registration = {"started_at": datetime.now(timezone.utc).isoformat(), "stage": "A: source-independent synthetic representation gate",
        "budget_seconds": 5400, "code_hashes": {p.name: sha(p) for p in (HERE / "adapter.py", Path(__file__))},
        "versions": {p: version(p) for p in ("docling-core", "pydantic", "markdown-it-py")},
        "source_paper_reads": 0, "oracle_reads": 0, "new_model_inferences": 0, "API_requests": 0}
    write("gate-registration.json", registration)
    try:
        report = checks()
        assert not {"torch", "transformers", "mlx"}.intersection(sys.modules)
        assert time.perf_counter() - start < 5400
    except Exception as error:
        write("verification.json", {"status": "failed", "scope": "A only; live stage stopped", "error": repr(error),
            "duration_seconds": time.perf_counter() - start, "code_hashes": registration["code_hashes"]})
        raise
    report.update(status="passed", scope="A representation only; no live/model quality claim", duration_seconds=time.perf_counter() - start,
                  code_hashes=registration["code_hashes"], API_requests=0, new_model_inferences=0, oracle_reads=0, source_paper_reads=0)
    write("verification.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
