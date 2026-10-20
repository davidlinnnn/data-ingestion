"""Research-only table representation mapping; no model, oracle, or content repair."""
from copy import deepcopy

from pydantic import BaseModel, ConfigDict, StrictStr, model_validator
from docling_core.types.doc import DocItemLabel, RefItem, TableCell, TableData
from docling_core.types.doc.items.group import GroupItem


class Shape(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Value(Shape):
    column: StrictStr
    value: StrictStr


class Row(Shape):
    setting: StrictStr
    values: list[Value]


class Panel(Shape):
    panel_label: StrictStr
    title: StrictStr
    columns: list[StrictStr]
    rows: list[Row]

    @model_validator(mode="after")
    def check_columns(self):
        if not self.columns or len(set(self.columns)) != len(self.columns):
            raise ValueError("metric columns must be nonempty and unique")
        for row in self.rows:
            keys = [v.column for v in row.values]
            if len(keys) != len(self.columns) or set(keys) != set(self.columns):
                raise ValueError("each row must bind each declared metric exactly once")
        return self


class Target(Shape):
    target_key: StrictStr
    caption: StrictStr
    conditions: list[StrictStr]
    panels: list[Panel]
    uncertainties: list[StrictStr] = []

    @model_validator(mode="after")
    def check_panels(self):
        labels = [p.panel_label for p in self.panels]
        if not labels or len(labels) != len(set(labels)):
            raise ValueError("panels must be nonempty with unique labels")
        return self


class Response(Shape):
    targets: list[Target]


def parse_response(payload, expected_keys):
    result = Response.model_validate(payload)
    keys = [t.target_key for t in result.targets]
    if len(keys) != len(set(keys)) or set(keys) != set(expected_keys):
        raise ValueError("whole-page target keys must match the registered inventory exactly once")
    return result


def inventory(doc, page_no):
    targets = {}
    for table in doc.tables:
        prov = [p for p in table.prov if p.page_no == page_no]
        if not prov:
            continue
        if len(table.prov) != 1:
            raise ValueError("this bounded page protocol does not support multi-page table targets")
        p = prov[0]
        page = doc.pages[p.page_no]
        b = p.bbox.to_top_left_origin(page_height=page.size.height)
        if not (0 <= b.l < b.r <= page.size.width and 0 <= b.t < b.b <= page.size.height):
            raise ValueError("native table envelope outside the source page")
        key = f"p{page_no}:{table.self_ref}"
        targets[key] = table
    if not targets:
        raise ValueError("no native table inventory")
    return targets


def panel_data(panel):
    # Empty setting header preserves the provider's missing literal header; never invent one.
    grid = [[""] + panel.columns]
    for row in panel.rows:
        by_column = {v.column: v.value for v in row.values}
        grid.append([row.setting] + [by_column[c] for c in panel.columns])
    return TableData(num_rows=len(grid), num_cols=len(grid[0]), table_cells=[
        TableCell(text=text, start_row_offset_idx=r, end_row_offset_idx=r + 1,
                  start_col_offset_idx=c, end_col_offset_idx=c + 1,
                  column_header=r == 0, row_header=c == 0 and r > 0)
        for r, row in enumerate(grid) for c, text in enumerate(row)
    ])


def map_response(baseline, response, page_no, registered_keys):
    """All-or-nothing copy: old input remains unchanged even if a target fails."""
    doc = baseline.model_copy(deep=True)
    all_targets = inventory(doc, page_no)
    if not registered_keys or len(set(registered_keys)) != len(registered_keys) or set(registered_keys) - all_targets.keys():
        raise ValueError("registered targets must uniquely identify existing native tables")
    targets = {key: all_targets[key] for key in registered_keys}
    parsed = parse_response(response, targets)
    by_key = {t.target_key: t for t in parsed.targets}
    bindings = []
    for key, old in targets.items():
        result = by_key[key]
        caption_nodes = [r.resolve(doc) for r in old.captions]
        if any(n.children for n in caption_nodes) or {r.cref for r in old.children} != {n.self_ref for n in caption_nodes}:
            raise ValueError("unsupported non-caption table children; no private tree repair")
        envelope = [p.model_copy(deep=True) for p in old.prov]
        group = GroupItem(self_ref="#/groups/0", name=key)
        doc.insert_item_before_sibling(new_item=group, sibling=old)
        group_binding = {"target_key": key, "group": group, "panels": [],
                         "original_provenance": [p.model_dump(mode="json") for p in envelope],
                         "location_precision": "native table envelope only; no panel/cell geometry",
                         "provider": result.model_dump(mode="json"), "captions": []}
        for index, panel in enumerate(result.panels):
            heading = " ".join(s for s in (panel.panel_label, panel.title) if s)
            title = doc.add_text(label=DocItemLabel.TEXT, text=heading, parent=group)
            title.prov = deepcopy(envelope)
            table = doc.add_table(data=panel_data(panel), parent=group)
            table.prov = deepcopy(envelope)
            if index == 0:
                for caption in caption_nodes:
                    clone = caption.model_copy(deep=True)
                    doc.append_child_item(child=clone, parent=table)
                    table.captions.append(clone.get_ref())
                    group_binding["captions"].append(clone)
                if not caption_nodes and result.caption:
                    cap = doc.add_text(label=DocItemLabel.CAPTION, text=result.caption, parent=table)
                    cap.prov = deepcopy(envelope)
                    table.captions.append(cap.get_ref())
                    group_binding["captions"].append(cap)
            group_binding["panels"].append({"title": title, "table": table})
        # Public deletion also removes the old caption children; copies are already attached.
        doc.delete_items(node_items=[old])
        bindings.append(group_binding)
    manifest = []
    for b in bindings:
        manifest.append({**{k: v for k, v in b.items() if k not in ("group", "panels", "captions")},
                         "group_ref": b["group"].self_ref,
                         "captions": [c.self_ref for c in b["captions"]],
                         "panels": [{"title_ref": p["title"].self_ref, "table_ref": p["table"].self_ref}
                                    for p in b["panels"]]})
    return doc, manifest


def recover_provider_from_cells(doc, binding):
    """Evaluation view reconstructed from saved public cells, not copied provider values."""
    result = deepcopy(binding["provider"])
    for panel, refs in zip(result["panels"], binding["panels"], strict=True):
        item = RefItem(cref=refs["table_ref"]).resolve(doc)
        grid = item.data.grid
        panel["columns"] = [c.text for c in grid[0][1:]]
        panel["rows"] = [{"setting": row[0].text,
                          "values": [{"column": c, "value": v.text}
                                     for c, v in zip(panel["columns"], row[1:], strict=True)]}
                         for row in grid[1:]]
    return result
