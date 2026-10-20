"""Zero-inference probe of the unmodified released PaddleOCR-VL importer."""

import base64
import copy
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if sys.argv[1:] == ["--prepare"]:
    code = '# keep <node> & x != y\nif x < limit and y > 0:\n    result = a_b + "$HOME"\n    print("<tag>")\n    return result'
    contents = [
        ("doc_title", "# Synthetic title"),
        ("paragraph_title", "### Nested section"),
        ("header", "Running header"),
        ("text", r"Use $x_i < y_j$ and `arr[i]` before cleanup."),
        ("algorithm", code),
        ("algorithm", '```python\nif x < 2:\n    print("<tag>")\n```'),
        ("text", "Before inline formula "),
        ("inline_formula", r"x_i < y_j"),
        ("text", " after inline formula."),
        ("display_formula", r"\theta = \theta_0 + \frac{a}{b}"),
        ("display_formula", r"$$\theta = \theta_0 + \frac{a}{b}$$"),
        ("table", '<table><caption>Grouped results</caption><tr><th rowspan="2">Setting</th><th colspan="2">Score</th></tr><tr><th>A</th><th>B</th></tr><tr><th scope="row">Base</th><td>1</td><td>2</td></tr></table>'),
        ("image", ""),
        ("figure_title", '<div style="text-align: center;">Figure 1. Pipeline</div>\n'),
        ("chart", "Series A: 1, 2"),
        ("footer", "Running footer"),
    ]
    blocks = []
    for index, (label, content) in enumerate(contents):
        top = 20 + index * 45
        blocks.append({"block_label": label, "block_content": content,
                       "block_bbox": [10, top, 600, top + 30], "block_id": index,
                       "block_order": 100 - index, "group_id": 7 if 6 <= index <= 8 else index,
                       "global_block_id": 1000 + index, "global_group_id": 7 if 6 <= index <= 8 else index,
                       "block_polygon_points": [[10, top], [600, top], [600, top + 30], [10, top + 30]]})
    fixture = {"input_path": "synthetic-source.pdf", "page_index": 2, "page_count": 3,
               "width": 612, "height": 792,
               "model_settings": {"format_block_content": True, "use_layout_detection": True,
                                  "use_doc_preprocessor": False, "markdown_ignore_labels": []},
               "parsing_res_list": blocks}
    write_json(ROOT / "synthetic-provider.json", fixture)
    scope = {
        "scope": "Perfect synthetic single-page PaddleX 3.7.2-shaped JSON through official Docling 2.132.0 importer, Docling JSON round-trip and stock Markdown export; no provider or model behavior measured.",
        "registered_before_execution": True,
        "runtime": "/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/bin/python",
        "source_identity": "runtime-identity.json",
        "cases": ["formatted title/heading/caption", "running header/footer", "inline math in prose", "plain algorithm with HTML-like literals/indentation", "fenced algorithm", "separate inline_formula within provider group", "bare versus provider-delimited display formula", "row/column headers and spans", "missing image bytes and caption association", "processed pixel provenance, polygon/group/order loss", "bare/wrapped JSON/string/bytes", "invalid geometry and ambiguous multipage rejection"],
        "requirements": {"code": "Exact literal text and indentation, usable Markdown code delivery", "inline_math": "LaTeX retained in prose or correctly associated inline within its source paragraph", "formula": "Usable single display wrapper", "table": "Header roles and spans retained in JSON; document Markdown remains usable", "picture": "Picture source bytes and caption association explicitly checked", "provenance": "Preserve page and bbox; do not claim original PDF point coordinates or source digest from placeholder origin"},
        "no_inference": True, "no_install": True, "no_model_weights": True,
        "fixture_sha256": digest(ROOT / "synthetic-provider.json"),
        "script_sha256": digest(Path(__file__)),
    }
    write_json(ROOT / "synthetic-scope.json", scope)
    print("Synthetic inputs and pre-execution scope registered.")
    raise SystemExit

assert sys.argv[1:] == ["--run"]
scope = json.loads((ROOT / "synthetic-scope.json").read_text())
assert digest(ROOT / "synthetic-provider.json") == scope["fixture_sha256"]
assert digest(Path(__file__)) == scope["script_sha256"]
distribution = metadata.distribution("docling-slim")
assert distribution.version == "2.132.0"
for name in ["docling/utils/paddleocr_vl_utils.py", "docling/utils/chandra_utils.py", "docling/utils/vlm_utils.py"]:
    record = next(item for item in distribution.files if str(item) == name)
    encoded = base64.urlsafe_b64encode(hashlib.sha256(distribution.locate_file(record).read_bytes()).digest()).rstrip(b"=").decode()
    assert record.hash.value == encoded, name

from docling.utils.paddleocr_vl_utils import parse_paddleocr_vl_result
from docling_core.types.doc import DoclingDocument

fixture = json.loads((ROOT / "synthetic-provider.json").read_text())
doc = parse_paddleocr_vl_result(fixture)
document = doc.export_to_dict()
write_json(ROOT / "synthetic-document.json", document)
markdown = doc.export_to_markdown()
(ROOT / "synthetic-document.md").write_text(markdown + "\n")
roundtrip = DoclingDocument.model_validate(document)
assert roundtrip.export_to_dict() == document
assert roundtrip.export_to_markdown() == markdown
for representation in [{"res": fixture}, json.dumps(fixture), json.dumps({"res": fixture}).encode()]:
    assert parse_paddleocr_vl_result(representation).export_to_dict() == document

items = [item for item, _ in doc.iterate_items()]
algorithms = [item for item in doc.texts if item.text.startswith(("# keep", "```python"))]
formulas = [item for item in doc.texts if item.label.value == "formula"]
table = doc.tables[0]
cells = [cell.model_dump(mode="json") for cell in table.data.table_cells]
invalid = {}
for case, update in [("negative_bbox", {"block_bbox": [-1, 20, 30, 40]}), ("outside_bbox", {"block_bbox": [10, 20, 700, 40]})]:
    payload = copy.deepcopy(fixture)
    payload["parsing_res_list"][0].update(update)
    try:
        parse_paddleocr_vl_result(payload)
    except ValueError as error:
        invalid[case] = str(error)
    else:
        raise AssertionError(case)
payload = copy.deepcopy(fixture)
payload["page_index"] = None
try:
    parse_paddleocr_vl_result(payload)
except ValueError as error:
    invalid["ambiguous_multipage"] = str(error)
else:
    raise AssertionError("ambiguous_multipage")

report = {
    "model_calls": 0, "network_calls_during_test": 0, "package_installs": 0,
    "fixture_sha256": scope["fixture_sha256"],
    "json_roundtrip_exact": True, "markdown_after_json_roundtrip_exact": True,
    "input_forms_equivalent": True, "invalid_cases_rejected": invalid,
    "algorithm_json_exact": [item.text == fixture["parsing_res_list"][index]["block_content"] for item, index in zip(algorithms, [4, 5])],
    "algorithm_labels": [item.label.value for item in algorithms],
    "plain_algorithm_verbatim_substring_in_markdown": fixture["parsing_res_list"][4]["block_content"] in markdown,
    "fenced_algorithm_verbatim_substring_in_markdown": fixture["parsing_res_list"][5]["block_content"] in markdown,
    "prose_inline_math_json_exact": doc.texts[3].text == fixture["parsing_res_list"][3]["block_content"],
    "prose_inline_math_markdown_exact_substring": fixture["parsing_res_list"][3]["block_content"] in markdown,
    "formula_texts": [item.text for item in formulas],
    "separate_inline_formula_label": formulas[0].label.value,
    "triple_dollar_occurs": "$$$" in markdown,
    "table_cells": cells,
    "table_caption_refs": [ref.cref for ref in table.captions],
    "picture_images": [picture.image for picture in doc.pictures],
    "picture_caption_refs": [[ref.cref for ref in picture.captions] for picture in doc.pictures],
    "page_numbers": sorted(doc.pages),
    "page_size": doc.pages[3].size.model_dump(),
    "origin": doc.origin.model_dump(mode="json"),
    "item_order": [item.text if hasattr(item, "text") else item.label.value for item in items],
    "first_provenance": doc.texts[0].prov[0].model_dump(mode="json"),
    "polygons_or_provider_ids_in_docling_json": any(key in json.dumps(document) for key in ["block_polygon_points", "global_group_id", "global_block_id", "block_order"]),
}
assert len(algorithms) == 2
assert report["algorithm_json_exact"] == [True, True]
assert len(formulas) == 3
write_json(ROOT / "synthetic-results.json", report)
print(json.dumps({key: value for key, value in report.items() if key not in ["table_cells", "item_order"]}, ensure_ascii=False, indent=2))
