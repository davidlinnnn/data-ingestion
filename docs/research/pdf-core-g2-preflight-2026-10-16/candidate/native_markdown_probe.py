"""Test complete official PaddleX pure converters, without a Paddle runtime."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


if sys.argv[1:] == ["--prepare"]:
    fixture = json.loads((ROOT / "synthetic-provider.json").read_text())
    fixture["model_settings"]["format_block_content"] = False
    fixture["parsing_res_list"][0]["block_content"] = "Synthetic title"
    fixture["parsing_res_list"][1]["block_content"] = "Nested section"
    fixture["parsing_res_list"][13]["block_content"] = "Figure 1. Pipeline"
    write_json(ROOT / "native-synthetic-provider.json", fixture)
    scope = {
        "registered_before_execution": True,
        "scope": "Complete unchanged PaddleX v3.7.2 MarkdownConverter and markdown_format_funcs modules only; standard namespace package import, synthetic documented block protocol inputs, no PaddleOCRVLResult import or save_to_markdown integration claim.",
        "handler_wiring": "PaddleOCRVLResult._build_handle_funcs_dict(pretty=False), use_chart_recognition=True, use_ocr_for_image_block=False, use_seal_recognition=False, markdown_ignore_labels=[]",
        "same_content_cases": "synthetic-scope.json; title/caption wrappers removed because native block.content is raw rather than format_block_content=True serialized JSON",
        "cases": ["raw and fenced algorithm exact literals", "inline math in prose", "separate inline_formula group", "bare/provider-delimited formula", "HTML table headers/spans", "header/footer retention", "missing image and real in-memory image collection"],
        "fixture_sha256": digest(ROOT / "native-synthetic-provider.json"),
        "script_sha256": digest(Path(__file__)),
        "sources": {name: digest(ROOT / "native_paddlex_v372" / name) for name in ["markdown_converter.py", "markdown_format_funcs.py"]},
        "no_inference": True, "no_install": True,
    }
    write_json(ROOT / "native-synthetic-scope.json", scope)
    print("Native pure-converter component preflight registered.")
    raise SystemExit

assert sys.argv[1:] == ["--run"]
scope = json.loads((ROOT / "native-synthetic-scope.json").read_text())
assert scope["fixture_sha256"] == digest(ROOT / "native-synthetic-provider.json")
assert scope["script_sha256"] == digest(Path(__file__))
for name, expected in scope["sources"].items():
    assert digest(ROOT / "native_paddlex_v372" / name) == expected
    assert (ROOT / "native_paddlex_v372" / name).read_bytes() == (ROOT / f"paddlex-v372-{name}").read_bytes()

from native_paddlex_v372.markdown_converter import MarkdownConverter
from native_paddlex_v372.markdown_format_funcs import (
    build_handle_funcs_dict, format_chart2html_table, format_image_plain,
    format_text_plain, simplify_table,
)
from PIL import Image


@dataclass
class SyntheticBlock:
    label: str
    content: str
    bbox: list
    image: dict | None = None


fixture = json.loads((ROOT / "native-synthetic-provider.json").read_text())
blocks = [SyntheticBlock(block["block_label"], block["block_content"], block["block_bbox"]) for block in fixture["parsing_res_list"]]
handlers = build_handle_funcs_dict(
    text_func=format_text_plain,
    image_func=lambda block: format_image_plain(block, show_ocr_content=False),
    chart_func=format_chart2html_table,
    table_func=lambda block: simplify_table("\n" + block.content),
    formula_func=lambda block: block.content,
    seal_func=lambda block: format_image_plain(block, show_ocr_content=False),
)
result = MarkdownConverter.convert(blocks, handle_funcs_dict=handlers, show_formula_number=False, imgs_in_doc=[])
markdown = result["markdown_texts"]
(ROOT / "native-synthetic-document.md").write_text(markdown + "\n")
raw_code, fenced_code = [fixture["parsing_res_list"][index]["block_content"] for index in [4, 5]]
assert raw_code in markdown
assert fenced_code in markdown
assert fixture["parsing_res_list"][3]["block_content"] in markdown
assert fixture["parsing_res_list"][11]["block_content"] in markdown
assert result["markdown_images"] == {}

image = Image.new("RGB", (2, 2), "white")
blocks[12].image = {"path": "imgs/synthetic-image.png", "img": image}
with_image = MarkdownConverter.convert(blocks, handle_funcs_dict=handlers, show_formula_number=False, imgs_in_doc=[])
assert with_image["markdown_images"]["imgs/synthetic-image.png"] is image
assert "![](imgs/synthetic-image.png)" in with_image["markdown_texts"]
image.save(ROOT / "native-synthetic-image.png")
report = {
    "model_calls": 0, "network_calls": 0, "package_installs": 0,
    "component_only": True, "whole_result_and_save_to_markdown_tested": False,
    "complete_unchanged_official_modules": True, "dependency_stubs": False,
    "raw_algorithm_exact_substring": raw_code in markdown,
    "raw_algorithm_wrapped_in_code_fence": "```\n" + raw_code + "\n```" in markdown,
    "fenced_algorithm_exact_substring": fenced_code in markdown,
    "prose_inline_math_exact_substring": fixture["parsing_res_list"][3]["block_content"] in markdown,
    "grouped_inline_reassembled_in_prose": "Before inline formula $x_i < y_j$ after inline formula." in markdown,
    "separate_inline_formula_has_paragraph_separators": "Before inline formula \n\nx_i < y_j\n\n after inline formula." in markdown,
    "bare_display_formula_gets_math_delimiters": "$$" + blocks[9].content + "$$" in markdown[:markdown.index(blocks[10].content)],
    "provider_delimited_formula_exact_substring": blocks[10].content in markdown,
    "table_html_headers_and_spans_exact_substring": blocks[11].content in markdown,
    "running_header_footer_retained": all(text in markdown for text in ["Running header", "Running footer"]),
    "missing_image_produces_reference": "![](" in markdown,
    "real_in_memory_image_collected": True, "image_saved_by_official_mixin": False,
}
write_json(ROOT / "native-synthetic-results.json", report)
print(json.dumps(report, indent=2))
