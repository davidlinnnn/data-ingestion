"""Offline semantic-table and already-logical multipage controls; no discovery or repair."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path

from docling_core.types.doc import RefItem, RichTableCell, TableData, TableItem

RESEARCH = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "bc_closure_original_cells", RESEARCH / "pdf-core-direct-cell-2026-10-17/adapter.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def normalized_panel(panel):
    """Paths/dimensions define normalized columns; printed cells remain raw and indivisible."""
    def shape(value, fields):
        if type(value) is not dict or set(value) != set(fields):
            raise ValueError("fields must match the declared semantic representation")

    def literal(value):
        if type(value) is not str:
            raise ValueError("known source strings only; unknown is not an empty cell")
        return value

    def ids(values):
        if type(values) is not list or any(type(v) is not str or not v for v in values) or len(set(values)) != len(values):
            raise ValueError("identifiers must be nonempty and unique")
        return values

    shape(panel, ("panel_label", "title", "dimension_names", "columns", "rows", "groups"))
    literal(panel["panel_label"]); literal(panel["title"])
    dimensions = ids(panel["dimension_names"])
    if type(panel["columns"]) is not list or not panel["columns"] or type(panel["rows"]) is not list or not panel["rows"]:
        raise ValueError("explicit nonempty columns and rows required")
    headers, paths, column_keys = {}, [], []
    for column in panel["columns"]:
        shape(column, ("key", "path"))
        column_keys.append(column["key"])
        if type(column["path"]) is not list or not column["path"]:
            raise ValueError("explicit header path required")
        parent = None; labels = []; visited = set()
        for node in column["path"]:
            shape(node, ("id", "text"))
            node_id = ids([node["id"]])[0]; text = literal(node["text"])
            if node_id in visited or node_id in headers and headers[node_id] != (parent, text):
                raise ValueError("header scope identity contradicts path parent or text")
            headers[node_id] = (parent, text); parent = node_id
            visited.add(node_id); labels.append(text)
        paths.append(" / ".join(labels))
    ids(column_keys)
    groups = {}
    if type(panel["groups"]) is not list:
        raise ValueError("explicit groups required")
    for group in panel["groups"]:
        shape(group, ("id", "label", "rows"))
        group_id = ids([group["id"]])[0]
        if group_id in groups:
            raise ValueError("duplicate group")
        groups[group_id] = (literal(group["label"]), ids(group["rows"]))
    grid = [(["Section"] if groups else []) + dimensions + paths]
    identities = []; row_keys = []; source_ids = {}; actual_groups = {key: [] for key in groups}
    for index, row in enumerate(panel["rows"], 1):
        shape(row, ("key", "dimensions", "group", "cells"))
        row_keys.append(row["key"])
        shape(row["dimensions"], dimensions)
        values = [literal(row["dimensions"][name]) for name in dimensions]
        if row["group"] is not None and row["group"] not in groups:
            raise ValueError("foreign group")
        if row["group"] is not None:
            actual_groups[row["group"]].append(row["key"])
        if type(row["cells"]) is not list:
            raise ValueError("explicit source cells required")
        by_column = {}
        for cell in row["cells"]:
            shape(cell, ("id", "column", "text"))
            identity = ids([cell["id"]])[0]
            text = literal(cell["text"])
            if identity in source_ids and source_ids[identity] != text or cell["column"] in by_column:
                raise ValueError("source cell split/changed or duplicate column binding")
            source_ids[identity] = text; by_column[cell["column"]] = text
            identities.append({"source_cell_id": identity, "row": row["key"],
                "column": cell["column"], "text": cell["text"],
                "normalized_anchor": [index, (1 if groups else 0) + len(dimensions) + column_keys.index(cell["column"])]})
        if set(by_column) != set(column_keys):
            raise ValueError("missing or foreign column binding")
        section = [groups[row["group"]][0] if row["group"] is not None else ""] if groups else []
        grid.append(section + values + [by_column[key] for key in column_keys])
    ids(row_keys)
    if any(actual_groups[key] != members for key, (_, members) in groups.items()):
        raise ValueError("group membership/order contradicts explicit scope")
    cells = [dict(text=text, start_row_offset_idx=r, end_row_offset_idx=r+1,
        start_col_offset_idx=c, end_col_offset_idx=c+1, row_span=1, col_span=1,
        column_header=r == 0, row_header=r > 0 and c < len(dimensions)+(1 if groups else 0), row_section=False)
        for r, row in enumerate(grid) for c, text in enumerate(row)]
    data = adapter.Data.model_validate(dict(num_rows=len(grid), num_cols=len(grid[0]), table_cells=cells))
    return data.model_dump(), {"semantic_provider": deepcopy(panel), "cell_identities": identities,
        "physical_evidence": "original source image/envelope; normalized cells do not claim original printed spans"}


def replace_already_logical_table(baseline, table_ref, expected_source_hash, data):
    """Public data replacement only: the logical owner must already exist; never merge fragments."""
    actual = sha256(baseline.model_dump_json().encode()).hexdigest()
    if actual != expected_source_hash:
        raise ValueError("stale source document")
    old = RefItem(cref=table_ref).resolve(baseline)
    if not isinstance(old, TableItem) or len(old.prov) < 2:
        raise ValueError("requires an already-logical table with multiple source envelopes")
    if any(isinstance(c, RichTableCell) for c in old.data.table_cells):
        raise ValueError("rich cells are outside this plain-cell experiment")
    if {r.cref for r in old.children} != {r.cref for r in old.captions}:
        raise ValueError("non-caption table children are unsupported")
    for prov in old.prov:
        page = baseline.pages[prov.page_no]
        box = prov.bbox.to_top_left_origin(page_height=page.size.height)
        if not (0 <= box.l < box.r <= page.size.width and 0 <= box.t < box.b <= page.size.height):
            raise ValueError("source envelope outside page")
    parsed = adapter.Data.model_validate(data)
    doc = baseline.model_copy(deep=True)
    table = RefItem(cref=table_ref).resolve(doc)
    table.data = TableData.model_validate(parsed.model_dump())
    binding = {"table_ref": table_ref,
        "source_hash": actual,
        "original_provenance": [p.model_dump(mode="json") for p in old.prov],
        "location_precision": "ordered native table envelopes only; no per-cell geometry",
        "provider_data": deepcopy(data)}
    return doc, binding
