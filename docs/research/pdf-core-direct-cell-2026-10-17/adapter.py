"""Research-only strict plain cells and public Docling mapping/serialization."""
from copy import deepcopy
import html
import importlib.util
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator
from docling_core.transforms.serializer.markdown import MarkdownDocSerializer, MarkdownTableSerializer
from docling_core.types.doc import DocItemLabel, RichTableCell, TableCell, TableData, TableItem
from docling_core.types.doc.items.group import GroupItem


OLD = Path(__file__).resolve().parent.parent / "pdf-core-table-delivery-2026-10-17/mapper.py"
spec = importlib.util.spec_from_file_location("previous_table_inventory", OLD)
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
inventory = previous.inventory


class Shape(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


CELL_FIELDS = ("text", "start_row_offset_idx", "end_row_offset_idx",
               "start_col_offset_idx", "end_col_offset_idx", "row_span", "col_span",
               "column_header", "row_header", "row_section")
# Use the pinned public field definitions, without generated geometry or rich references.
Cell = create_model("Cell", __base__=Shape, **{
    name: (TableCell.model_fields[name].annotation, deepcopy(TableCell.model_fields[name]))
    for name in CELL_FIELDS})


class Data(Shape):
    num_rows: int = Field(ge=1, le=256)
    num_cols: int = Field(ge=1, le=64)
    table_cells: list[Cell] = Field(min_length=1, max_length=16384)

    @model_validator(mode="after")
    def check_grid(self):
        occupied = set()
        for cell in self.table_cells:
            r0, r1 = cell.start_row_offset_idx, cell.end_row_offset_idx
            c0, c1 = cell.start_col_offset_idx, cell.end_col_offset_idx
            if not (0 <= r0 < r1 <= self.num_rows and 0 <= c0 < c1 <= self.num_cols):
                raise ValueError("cell offsets outside the declared table")
            if cell.row_span != r1-r0 or cell.col_span != c1-c0:
                raise ValueError("spans must equal the declared offset ranges")
            if cell.row_section and (cell.column_header or cell.row_header):
                raise ValueError("row section cannot also be a column/row header")
            slots = {(r, c) for r in range(r0, r1) for c in range(c0, c1)}
            if occupied & slots:
                raise ValueError("overlapping or duplicate cells")
            occupied.update(slots)
        if len(occupied) != self.num_rows*self.num_cols:
            raise ValueError("uncovered grid positions require explicit source empty cells")
        return self


class Panel(Shape):
    panel_label: str
    title: str
    data: Data


class Target(Shape):
    target_key: str
    caption: str
    conditions: list[str]
    panels: list[Panel] = Field(min_length=1, max_length=16)
    uncertainties: list[str] = Field(default_factory=list)


class Response(Shape):
    targets: list[Target] = Field(min_length=1, max_length=12)


def parse_response(payload, expected_keys):
    parsed = Response.model_validate(payload)
    keys = [t.target_key for t in parsed.targets]
    if len(keys) != len(set(keys)) or set(keys) != set(expected_keys):
        raise ValueError("whole-page target keys must match the inventory exactly once")
    return parsed


def map_response(baseline, response, page_no, registered_keys):
    """Validate the entire response first, then mutate only an isolated document copy."""
    all_targets = inventory(baseline, page_no)
    if (not registered_keys or len(set(registered_keys)) != len(registered_keys)
            or set(registered_keys)-all_targets.keys()):
        raise ValueError("registered targets must uniquely identify native tables")
    parsed = parse_response(response, registered_keys)
    for key in registered_keys:
        old = all_targets[key]
        carried = {"self_ref", "parent", "children", "data", "prov", "captions"}
        if any(getattr(old, name) != field.get_default(call_default_factory=True)
               for name, field in TableItem.model_fields.items() if name not in carried):
            raise ValueError("non-default target metadata is unsupported; no silent loss")
        captions = [r.resolve(baseline) for r in old.captions]
        if (any(isinstance(c, RichTableCell) for c in old.data.table_cells)
                or any(c.children for c in captions)
                or {r.cref for r in old.children} != {c.self_ref for c in captions}):
            raise ValueError("rich targets and non-caption table children are unsupported")
    doc = baseline.model_copy(deep=True)
    targets = inventory(doc, page_no)
    by_key = {t.target_key: t for t in parsed.targets}
    bindings = []
    for key in registered_keys:
        old, result = targets[key], by_key[key]
        captions = [r.resolve(doc) for r in old.captions]
        envelope = deepcopy(old.prov)
        group = GroupItem(self_ref="#/groups/0", name=key)
        doc.insert_item_before_sibling(new_item=group, sibling=old)
        binding = {"target_key": key, "group": group, "panels": [], "captions": [],
                   "original_provenance": [p.model_dump(mode="json") for p in envelope],
                   "location_precision": "native table envelope only; no panel/cell geometry",
                   "provider": result.model_dump(mode="json")}
        for index, panel in enumerate(result.panels):
            title = doc.add_text(label=DocItemLabel.TEXT,
                text=" ".join(s for s in (panel.panel_label, panel.title) if s), parent=group)
            title.prov = deepcopy(envelope)
            data = TableData(num_rows=panel.data.num_rows, num_cols=panel.data.num_cols,
                table_cells=[TableCell.model_validate(c.model_dump(), strict=True)
                             for c in panel.data.table_cells])
            table = doc.add_table(data=data, parent=group)
            table.prov = deepcopy(envelope)
            if index == 0:
                for caption in captions:
                    clone = caption.model_copy(deep=True)
                    doc.append_child_item(child=clone, parent=table)
                    table.captions.append(clone.get_ref())
                    binding["captions"].append(clone)
                if not captions and result.caption:
                    cap = doc.add_text(label=DocItemLabel.CAPTION, text=result.caption, parent=table)
                    cap.prov = deepcopy(envelope)
                    table.captions.append(cap.get_ref())
                    binding["captions"].append(cap)
            binding["panels"].append({"title": title, "table": table})
        doc.delete_items(node_items=[old])
        bindings.append(binding)
    return doc, [{**{k: v for k, v in b.items() if k not in ("group", "panels", "captions")},
        "group_ref": b["group"].self_ref, "captions": [c.self_ref for c in b["captions"]],
        "panels": [{"title_ref": p["title"].self_ref, "table_ref": p["table"].self_ref}
                   for p in b["panels"]]} for b in bindings]


class LiteralTableSerializer(MarkdownTableSerializer):
    def __init__(self, target_refs=None):
        self.target_refs = target_refs

    def serialize(self, *, item, doc_serializer, **kwargs):
        if self.target_refs is not None and item.self_ref not in self.target_refs:
            return super().serialize(item=item, doc_serializer=doc_serializer, **kwargs)
        display = item.model_copy(deep=True)
        for cell in display.data.table_cells:
            if not isinstance(cell, RichTableCell):
                cell.text = html.escape(" ".join(cell.text.splitlines()), quote=False).translate({
                    ord(c): f"&#{ord(c)};" for c in "\\`*_[]$~"})
        result = super().serialize(item=display, doc_serializer=doc_serializer, **kwargs)
        for span in result.spans:
            if span.item.self_ref == item.self_ref:
                span.item = item
        return result


def serialize(doc, bindings=None):
    refs = None if bindings is None else {p["table_ref"] for b in bindings for p in b["panels"]}
    return MarkdownDocSerializer(doc=doc,
        table_serializer=LiteralTableSerializer(target_refs=refs)).serialize()


def export_markdown(doc, bindings=None):
    return serialize(doc, bindings).text
