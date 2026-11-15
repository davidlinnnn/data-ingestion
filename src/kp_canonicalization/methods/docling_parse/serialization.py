"""Serialize the docling-parse evidence without embedded images or nonfinite JSON numbers."""

import io
import json
import math
from typing import Any, Literal

from docling.datamodel.base_models import (
    AssembledUnit,
    ContainerElement,
    FigureElement,
    Page,
    PageConfidenceScores,
    Table,
    TextElement,
)
from docling_core.types.doc.base import BoundingBox, Size
from PIL import Image
from pydantic import BaseModel, Field, StrictInt

ELEMENT_TYPES = {cls.__name__: cls for cls in (TextElement, Table, FigureElement, ContainerElement)}


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def pack_assembled(unit: AssembledUnit) -> dict[str, Any]:
    return {
        key: [
            {"type": type(element).__name__, "value": element.model_dump(mode="json")}
            for element in getattr(unit, key)
        ]
        for key in ("elements", "headers", "body")
    }


def unpack_assembled(data: dict[str, Any]) -> AssembledUnit:
    if set(data) != {"elements", "headers", "body"}:
        raise ValueError("Incomplete assembled unit")
    try:
        return AssembledUnit(
            **{
                key: [
                    ELEMENT_TYPES[element["type"]].model_validate(element["value"])
                    for element in values
                ]
                for key, values in data.items()
            }
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid assembled element tag") from exc


class SavedPage(BaseModel):
    page_no: int = Field(strict=True, gt=0)
    size: Size
    assembled: dict[str, Any]
    confidence: dict[str, float | None]
    shape_lines: list[BoundingBox] | None
    shape_bounding_boxes: list[BoundingBox] | None


class PageImage(BaseModel):
    page: int = Field(strict=True, gt=0)
    ref: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Group(BaseModel):
    schema_: Literal["docling-parse-group/v1"] = Field(alias="schema")
    pages: tuple[StrictInt, StrictInt]
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(strict=True, gt=0)
    source_name: Literal["paper.pdf"]
    page_results: list[SavedPage]
    page_images: list[PageImage]


def capture_page(page: Page, confidence: PageConfidenceScores) -> SavedPage:
    if page.size is None or page.assembled is None:
        raise ValueError("Page has no completed assembly")
    return SavedPage(
        page_no=page.page_no,
        size=page.size,
        assembled=pack_assembled(page.assembled),
        confidence={
            key: value if math.isfinite(value) else None
            for key in PageConfidenceScores.model_fields
            for value in [getattr(confidence, key)]
        },
        shape_lines=page._shape_lines,
        shape_bounding_boxes=page._shape_bounding_boxes,
    )


def restore_page(saved: SavedPage, png: bytes) -> Page:
    if set(saved.confidence) != set(PageConfidenceScores.model_fields):
        raise ValueError("Incomplete page confidence")
    page = Page(page_no=saved.page_no, size=saved.size, assembled=unpack_assembled(saved.assembled))
    with Image.open(io.BytesIO(png)) as image:
        page._image_cache = {2.0: image.copy()}
    page._default_image_scale = 2.0
    page._shape_lines = saved.shape_lines
    page._shape_bounding_boxes = saved.shape_bounding_boxes
    return page


def group_json(group: Group) -> bytes:
    return json_bytes(group.model_dump(mode="json", by_alias=True))


def assembly_json(
    groups: list[dict[str, Any]], pictures: list[dict[str, Any]], document: dict[str, Any]
) -> bytes:
    return json_bytes(
        {
            "schema": "docling-parse-assembly/v1",
            "groups": groups,
            "picture_images": pictures,
            "document": document,
        }
    )
