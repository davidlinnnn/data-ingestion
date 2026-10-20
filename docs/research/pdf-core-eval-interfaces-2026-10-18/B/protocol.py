"""Strict semantic transport bridged to the frozen public-Core table method."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RESEARCH = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("semantic_B_frozen_method",
    RESEARCH / "pdf-core-bc-closure-2026-10-17/B/method.py")
method = importlib.util.module_from_spec(spec)
spec.loader.exec_module(method)
adapter = method.adapter
policy_spec = importlib.util.spec_from_file_location("semantic_B_caption_policy",
    RESEARCH / "pdf-core-caption-ownership-2026-10-17/policy.py")
policy = importlib.util.module_from_spec(policy_spec)
policy_spec.loader.exec_module(policy)


def loads(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


class Shape(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Header(Shape):
    id: str = Field(min_length=1, max_length=128)
    text: str = Field(max_length=8192)


class Column(Shape):
    key: str = Field(min_length=1, max_length=128)
    path: list[Header] = Field(min_length=1, max_length=16)


class Cell(Shape):
    id: str = Field(min_length=1, max_length=128)
    column: str = Field(min_length=1, max_length=128)
    text: str = Field(max_length=16384)


class Row(Shape):
    key: str = Field(min_length=1, max_length=128)
    dimensions: dict[str, str]
    group: str | None
    cells: list[Cell] = Field(min_length=1, max_length=64)


class Group(Shape):
    id: str = Field(min_length=1, max_length=128)
    label: str = Field(max_length=8192)
    rows: list[str] = Field(min_length=1, max_length=256)


class Panel(Shape):
    panel_label: str = Field(max_length=8192)
    title: str = Field(max_length=8192)
    dimension_names: list[str] = Field(max_length=16)
    columns: list[Column] = Field(min_length=1, max_length=64)
    rows: list[Row] = Field(min_length=1, max_length=255)
    groups: list[Group] = Field(max_length=255)

    @model_validator(mode="after")
    def check_semantics(self):
        method.normalized_panel(self.model_dump(mode="json"))
        return self

    @property
    def data(self):
        # The frozen HTTP runner validates the public Data after content parsing.
        return SimpleNamespace(data=lambda: method.normalized_panel(self.model_dump(mode="json"))[0])


class Target(Shape):
    target_key: str = Field(min_length=1, max_length=128)
    caption: Literal[""]
    conditions: list[str] = Field(max_length=64)
    diagnostics: list[str] = Field(max_length=64)
    panels: list[Panel] = Field(min_length=1, max_length=16)


class Response(Shape):
    targets: list[Target] = Field(min_length=1, max_length=12)


def parse(payload, keys):
    result = Response.model_validate(payload)
    actual = [target.target_key for target in result.targets]
    if not keys or len(set(keys)) != len(keys) or len(set(actual)) != len(actual) or set(actual) != set(keys):
        raise ValueError("missing, duplicate or foreign target")
    return result


def map_response(baseline, payload, page_no, keys):
    if set(adapter.inventory(baseline, page_no)) != set(keys):
        raise ValueError("complete page target inventory required")
    parsed = parse(payload, keys)
    expanded = {"targets": []}; supplements = {}
    for target in parsed.targets:
        panels = []; observations = []
        for panel in target.panels:
            data, supplement = method.normalized_panel(panel.model_dump(mode="json"))
            panels.append(dict(panel_label=panel.panel_label, title=panel.title, data=data))
            observations.append(supplement)
        expanded["targets"].append(dict(target_key=target.target_key, caption="", conditions=target.conditions,
            uncertainties=target.diagnostics, panels=panels))
        supplements[target.target_key] = observations
    doc, bindings = policy.map_preserving_ownership(baseline, expanded, page_no, keys)
    by_key = {target.target_key: target.model_dump(mode="json") for target in parsed.targets}
    for binding in bindings:
        binding["semantic_provider"] = deepcopy(by_key[binding["target_key"]])
        binding["semantic_panels"] = supplements[binding["target_key"]]
        binding["protocol"] = "header-paths-dimensions-v1"
    return doc, bindings
