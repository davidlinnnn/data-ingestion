"""Probe the unmodified official dots parser; synthetic inputs, no inference."""
import hashlib
import inspect
import json
from importlib.metadata import version
from pathlib import Path

from PIL import Image
from docling_core.types.doc import Size
from docling.utils.dots_utils import parse_dots_json
from docling.utils.vlm_utils import compute_qwen2vl_image_size

HERE = Path(__file__).resolve().parent
OUT = HERE / "preflight"
CODE = 'def f(x):\n    if x <= 2:\n        return {"key": [1, 2]}\n    return None'
INLINE = r"For $x_i^2$ and $\theta'$ use `items[i] <= limit`; preserve the sentence."
FORMULA = r"p(y_{<s}) = \sum_{i=1}^{n} x_i^2 \tag{4}"


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def main():
    OUT.mkdir(exist_ok=False)
    elements = [
        {"category": "Title", "bbox": [40, 20, 1080, 70], "text": "# Native dots fixture"},
        {"category": "Text", "bbox": [40, 90, 1080, 190], "text": INLINE},
        {"category": "Formula", "bbox": [40, 210, 1080, 290], "text": FORMULA},
        {"category": "Text", "bbox": [40, 310, 1080, 470], "text": "```python\n" + CODE + "\n```"},
        {"category": "Table", "bbox": [40, 490, 1080, 620], "text": '<table><tr><th rowspan="2">A</th><th>B</th></tr><tr><td>12.5</td></tr></table>'},
        {"category": "Picture", "bbox": [40, 640, 1080, 800]},
        {"category": "Caption", "bbox": [40, 820, 1080, 880], "text": "Figure 1. Source caption."},
        {"category": "Text", "bbox": [40, 900, 1080, 1000], "text": "Plain identifier under_score_name; price $5; literal 3 < 4; <b>bold</b>."},
    ]
    raw = json.dumps(elements, ensure_ascii=False)
    (OUT / "input.json").write_text(raw + "\n")
    kwargs = dict(original_page_size=Size(width=560, height=840), page_no=3,
                  filename="synthetic.json", page_image=Image.new("RGB", (1120, 1680), "white"),
                  model_image_size=Size(width=1120, height=1680))
    doc = parse_dots_json(raw, **kwargs)
    doc.save_as_json(OUT / "document.json")
    default = doc.export_to_markdown()
    literal = doc.export_to_markdown(escape_underscores=False)
    native_markdown = doc.export_to_markdown(escape_underscores=False, escape_html=False)
    (OUT / "default.md").write_text(default)
    (OUT / "literal-underscores.md").write_text(literal)
    (OUT / "native-markdown.md").write_text(native_markdown)
    data = doc.model_dump(mode="json")
    texts = data["texts"]
    prov = [p for collection in ("texts", "tables", "pictures") for x in data[collection] for p in x.get("prov", [])]
    checks = {
        "raw_inline_paragraph_preserved": any(x["text"] == INLINE for x in texts),
        "default_markdown_inline_latex_preserved": INLINE in default,
        "official_no_escape_option_inline_latex_preserved": INLINE in literal,
        "official_markdown_options_preserve_inline": INLINE in native_markdown,
        "formula_literal_less_than_and_label_preserved": any(x["label"] == "formula" and x["text"] == FORMULA for x in texts),
        "formula_markdown_preserved": FORMULA in default,
        "code_exact_indentation_and_symbols": any(x["label"] == "code" and x["text"] == CODE for x in texts),
        "code_markdown_preserved": CODE in default,
        "inline_code_literal_preserved": "`items[i] <= limit`" in default,
        "merged_table_cell_preserved": any(c["row_span"] == 2 and c["text"] == "A" for c in data["tables"][0]["data"]["table_cells"]),
        "picture_crop_available": doc.pictures[0].get_image(doc) is not None,
        "caption_linked": bool(doc.pictures[0].captions),
        "physical_page_preserved": all(p["page_no"] == 3 for p in prov),
        "coordinate_scale_exact": texts[0]["prov"][0]["bbox"]["l"] == 20,
        "all_boxes_within_page": all(0 <= p["bbox"]["l"] < p["bbox"]["r"] <= 560 and 0 <= p["bbox"]["t"] < p["bbox"]["b"] <= 840 for p in prov),
    }
    negatives = []
    for name, response in [("empty", ""), ("truncated", raw[:-1]), ("non_json", "I cannot parse this page")]:
        rejected_by_strict_transport_gate = False
        try:
            parsed = json.loads(response)
            rejected_by_strict_transport_gate = not isinstance(parsed, list) or not parsed
        except ValueError:
            rejected_by_strict_transport_gate = True
        native = parse_dots_json(response, **kwargs)
        negatives.append({"name": name, "native_items": len(list(native.iterate_items())),
                          "strict_json_completeness_gate_rejects": rejected_by_strict_transport_gate})
    source = Path(inspect.getfile(parse_dots_json))
    record = {"model_calls": 0, "kind": "official parser component preflight, not full pipeline or model quality",
              "packages": {k: version(k) for k in ("docling-slim", "docling-core", "docling-parse")},
              "parser_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "checks": checks, "negative_controls": negatives,
              "resize_probe": {str((w,h)): compute_qwen2vl_image_size(width=w,height=h,scale=1,max_size=None).model_dump(mode="json") for w,h in [(1120,1680),(1200,1600),(200,300)]},
              "custom_output_repairs": 0}
    save(OUT / "results.json", record)
    assert all(n["strict_json_completeness_gate_rejects"] for n in negatives)
    assert checks["code_exact_indentation_and_symbols"] and checks["physical_page_preserved"]
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
