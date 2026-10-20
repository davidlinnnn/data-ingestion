"""One compact research protocol; no source values, graph repair or renderer."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
policy = load("stage1_caption_policy", ROOT / "pdf-core-caption-ownership-2026-10-17/policy.py")
adapter = policy.adapter

class Shape(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
class Unknown(Shape):
    unknown: Literal[True]
class Span(Shape):
    row: int = Field(ge=0)
    col: int = Field(ge=0)
    rows: int = Field(ge=1)
    cols: int = Field(ge=1)
class Role(Shape):
    row: int = Field(ge=0)
    col: int = Field(ge=0)
    kind: Literal["column", "row", "corner", "section"]
class RowGroup(Shape):
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    label_row: int = Field(ge=0)
    label_col: int = Field(ge=0)
class Grid(Shape):
    grid: list[list[str | None | Unknown]] = Field(min_length=1, max_length=256)
    spans: list[Span]
    roles: list[Role]
    row_groups: list[RowGroup]

    @model_validator(mode="after")
    def validate_grid(self):
        rows, cols = len(self.grid), len(self.grid[0])
        if not 1 <= cols <= 64 or any(len(row) != cols for row in self.grid):
            raise ValueError("grid must be rectangular, 1..64 columns")
        covered, anchors = set(), set()
        for span in self.spans:
            r, c = span.row, span.col
            if r + span.rows > rows or c + span.cols > cols or (span.rows, span.cols) == (1, 1):
                raise ValueError("span out of bounds or redundant unit span")
            slots = {(i, j) for i in range(r, r+span.rows) for j in range(c, c+span.cols)}
            if slots & covered or (r,c) in anchors or self.grid[r][c] is None:
                raise ValueError("overlapping span or invalid anchor")
            for i,j in slots - {(r,c)}:
                if self.grid[i][j] is not None:
                    raise ValueError("covered positions must be null, never duplicate content")
            anchors.add((r,c)); covered.update(slots)
        nulls = {(r,c) for r,row in enumerate(self.grid) for c,value in enumerate(row) if value is None}
        if nulls != covered - anchors:
            raise ValueError("null means covered slot only")
        roles = {}
        for role in self.roles:
            pos = (role.row, role.col)
            if pos in roles or role.row >= rows or role.col >= cols or self.grid[role.row][role.col] is None:
                raise ValueError("duplicate, outside or covered role anchor")
            roles[pos] = role.kind
        groups = set()
        previous_end = 0
        for group in self.row_groups:
            pos = (group.label_row, group.label_col)
            if not (previous_end <= group.start < group.end <= rows and group.start == group.label_row):
                raise ValueError("row group ranges must be ordered, nonoverlapping and begin at label")
            if roles.get(pos) != "section" or pos in groups:
                raise ValueError("rowgroup requires unique section label")
            groups.add(pos); previous_end = group.end
        if groups != {pos for pos,kind in roles.items() if kind == "section"}:
            raise ValueError("every section needs an explicit rowgroup scope")
        header_rows = {r for (r,c),kind in roles.items() if kind in ("column", "corner")}
        if header_rows and header_rows != set(range(max(header_rows)+1)):
            raise ValueError("column headers must occupy a contiguous leading band")
        if any(r <= max(header_rows, default=-1) for r,c in groups):
            raise ValueError("row section cannot be in column header band")
        return self

    def data(self):
        span_at = {(s.row,s.col):s for s in self.spans}
        role_at = {(s.row,s.col):s.kind for s in self.roles}
        cells = []
        for r,row in enumerate(self.grid):
            for c,value in enumerate(row):
                if value is None:
                    continue
                if isinstance(value, Unknown):
                    raise ValueError("unknown source content is unresolved; cannot accept complete table")
                span, role = span_at.get((r,c)), role_at.get((r,c))
                height, width = (span.rows,span.cols) if span else (1,1)
                cells.append(dict(text=value,start_row_offset_idx=r,end_row_offset_idx=r+height,
                    start_col_offset_idx=c,end_col_offset_idx=c+width,row_span=height,col_span=width,
                    column_header=role in ("column","corner"),row_header=role in ("row","corner"),row_section=role=="section"))
        return dict(num_rows=len(self.grid),num_cols=len(self.grid[0]),table_cells=cells)
class Panel(Shape):
    panel_label: str
    title: str
    data: Grid
class Target(Shape):
    target_key: str
    caption: Literal[""]
    conditions: list[str]
    panels: list[Panel] = Field(min_length=1,max_length=16)
    diagnostics: list[str]
class Response(Shape):
    targets: list[Target] = Field(min_length=1,max_length=12)

def parse(payload, keys):
    parsed = Response.model_validate(payload)
    actual = [t.target_key for t in parsed.targets]
    if not keys or len(keys)!=len(set(keys)) or len(actual)!=len(set(actual)) or set(actual)!=set(keys):
        raise ValueError("missing, duplicate or foreign target key")
    return parsed

def map_response(baseline,payload,page_no,keys):
    if set(adapter.inventory(baseline,page_no)) != set(keys):
        raise ValueError("map requires the complete page target inventory")
    parsed = parse(payload,keys)
    expanded = {"targets":[dict(target_key=t.target_key,caption=t.caption,conditions=t.conditions,
        uncertainties=t.diagnostics,panels=[dict(panel_label=p.panel_label,title=p.title,data=p.data.data()) for p in t.panels]) for t in parsed.targets]}
    doc,bindings = policy.map_preserving_ownership(baseline,expanded,page_no,keys)
    compact = {t.target_key:t.model_dump(mode="json") for t in parsed.targets}
    for binding in bindings:
        binding["compact_provider"] = deepcopy(compact[binding["target_key"]])
        binding["protocol"] = "grid-spans-v1"
        binding["row_group_scope_location"] = "compact_provider.panels[].data.row_groups; Core row_section labels plus explicit scope supplement"
    return doc,bindings
