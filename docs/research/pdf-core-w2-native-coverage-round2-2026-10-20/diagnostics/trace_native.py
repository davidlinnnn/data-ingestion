"""Observe official reading order using saved inputs, without model inference."""
import argparse
import hashlib
import json
from pathlib import Path
from docling_core.types.doc import BoundingBox

from docling.datamodel.base_models import AssembledUnit, ContainerElement, InputFormat, Page
from docling.datamodel.document import ConversionResult, InputDocument
from docling.models.stages.reading_order.readingorder_model import ReadingOrderModel, ReadingOrderOptions


def ro_row(e):
    return {"cid": e.cid, "id": e.ref.cref, "page_no": e.page_no,
            "text": e.text or "", "label": e.label.value,
            "bbox": {k: getattr(e, k) for k in ("l", "t", "r", "b")}}


def replay(path, pages, options, markdown_path=None, allow_mismatch=False):
    raw = json.loads(path.read_text())
    metadata = {**raw["input"], "file": Path(raw["input"]["file"]),
                "format": InputFormat(raw["input"]["format"])}
    conv = ConversionResult.model_construct(
        input=InputDocument.model_construct(**metadata),
        pages=[Page.model_validate(p) for p in raw["pages"]],
        assembled=AssembledUnit.model_validate(raw["assembled"]), timings={})
    # The untagged union otherwise reloads a serialized ContainerElement as FigureElement.
    for field in ("elements", "body", "headers"):
        values = getattr(conv.assembled, field)
        for i, element in enumerate(raw["assembled"][field]):
            if element["label"] in ("form", "key_value_region"):
                values[i] = ContainerElement.model_validate(element)
    shapes_path = path.with_name("private-shapes.json")
    shapes = json.loads(shapes_path.read_text()) if shapes_path.exists() else raw.get("private_shapes", {})
    for p in conv.pages:
        saved = shapes.get(str(p.page_no), {})
        for attr in ("_shape_lines", "_shape_bounding_boxes"):
            value = saved.get(attr, saved.get(attr.removeprefix("_")))
            if value is not None:
                setattr(p, attr, [BoundingBox.model_validate(b) for b in value])
    model = ReadingOrderModel(ReadingOrderOptions.model_validate(options))
    assembled = [{"id": model._element_ref(e), "page_no": e.page_no,
                  "label": e.label.value, "text": e.text or "",
                  "bbox": e.cluster.bbox.model_dump(mode="json"),
                  "cells": [c.model_dump(mode="json") for c in e.cluster.cells]}
                 for e in conv.assembled.elements if e.page_no in pages]
    calls = []

    def observe(name):
        native = getattr(model.ro_model, name)

        def wrapped(*args, **kwargs):
            result = native(*args, **kwargs)
            input_elements = kwargs.get("page_elements", kwargs.get("sorted_elements", []))
            if any(e.page_no in pages for e in input_elements):
                calls.append({"stage": name,
                              "input": [ro_row(e) for e in input_elements if e.page_no in pages],
                              "result": ([ro_row(e) for e in result if e.page_no in pages]
                                         if name == "predict_reading_order" else result)})
            return result

        setattr(model.ro_model, name, wrapped)

    for name in ("predict_reading_order", "predict_to_captions", "predict_to_footnotes", "predict_merges"):
        observe(name)
    final = model(conv)
    actual = final.model_dump(mode="json")
    equal = {k: actual[k] == raw["document"][k]
             for k in ("texts", "groups", "body", "furniture", "tables")}
    equal["pictures_except_later_image_attachment"] = [
        {k: v for k, v in p.items() if k != "image"} for p in actual["pictures"]
    ] == [{k: v for k, v in p.items() if k != "image"} for p in raw["document"]["pictures"]]
    assert all(equal.values()) or allow_mismatch, equal
    markdown_equal = None
    if markdown_path:
        markdown_equal = final.export_to_markdown() == markdown_path.read_bytes().decode()
        assert markdown_equal or allow_mismatch, str(markdown_path)
    final_items = [{**item.model_dump(mode="json"), "traversal_depth": depth}
                   for item, depth in final.iterate_items(with_groups=False, traverse_pictures=True)
                   if any(p.page_no in pages for p in getattr(item, "prov", []))]
    layout_path = path.with_name("layout-raw.json")
    return {"input_result": str(path.resolve()),
            "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "new_model_inferences": 0, "reading_order_options": options,
            "selected_pages": sorted(pages), "native_replay_equal": equal,
            "stage_attribution_valid": all(equal.values()),
            "mismatch_first_items": {k: [{"index": i, "original": b, "replayed": a}
                  for i, (a, b) in enumerate(zip(actual[k], raw["document"][k])) if a != b][:1]
                  for k in ("texts", "tables", "pictures", "groups") if not equal.get(k, True)},
            "private_shapes": {str(p): shapes.get(str(p)) for p in pages},
            "raw_layout_path": str(layout_path.resolve()) if layout_path.exists() else None,
            "markdown_equal": markdown_equal,
            "assembled": assembled, "native_stage_calls": calls,
            "final_items": final_items,
            "saved_pages": [p for p in raw["pages"] if p["page_no"] in pages],
            "limits": "Assembled order is predictor tie-break input, not a reading-order oracle. Stage attribution requires checking the actual source page and candidate anchors. No upstream layout rerun or modification."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pages", type=int, nargs="+", required=True)
    parser.add_argument("--options", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--allow-mismatch", action="store_true", help="Save invalid replay evidence; no stage attribution")
    args = parser.parse_args()
    assert not args.output.exists(), str(args.output)
    trace = replay(args.result, set(args.pages), json.loads(args.options.read_text()), args.markdown, args.allow_mismatch)
    args.output.write_text(json.dumps(trace, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "selected_pages": args.pages,
                      "native_replay_equal": trace["native_replay_equal"]}))


if __name__ == "__main__":
    main()
