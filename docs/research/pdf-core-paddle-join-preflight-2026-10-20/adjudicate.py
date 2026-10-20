"""Read-only outcome checks; preserve the original probe diagnostics verbatim."""
from html.parser import HTMLParser

from join_common import HERE, read, sha, verify_registration, write


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, text):
        self.parts.append(text)


def main():
    registration = verify_registration()
    paddle = read(HERE / "paddle/results.json")
    docling = read(HERE / "docling/results.json")
    tables = read(HERE / "paddle/table-controls.json")
    fixture = read(HERE / "fixture.json")
    native = (HERE / "paddle/relocated-bundle/document.md").read_text()
    stock = VisibleText()
    stock.feed((HERE / "docling/stock-render.html").read_text())
    visible = "".join(stock.parts)
    markers = ["DERIVED_IMAGE_OCR_ONLY", "DERIVED_CHART_DATA_ONLY"]
    assert all(marker in visible for marker in markers)
    assert not docling["pages"][0]["image_content_in_docling_primary_markdown"]
    assert not docling["pages"][0]["chart_content_in_docling_primary_markdown"]
    numbered_formula = "$$E = mc^2 \\tag*{(7)}$$"
    assert numbered_formula in native
    assert not paddle["native_display_bare_formula_delimited"]
    for page in fixture["pages"]:
        for block in page["blocks"]:
            if block["label"] == "text" and "paragraph" in block["content"]:
                assert block["content"] in native

    positive = tables["same_headers_distinct_rows_positive"]
    duplicate = tables["same_headers_identical_data_row_negative"]
    unrelated = tables["different_headers_unrelated_tables_negative"]
    data_row = "<tr><td>a</td><td>1</td></tr>"
    assert "<tr><td>b</td><td>2</td></tr>" in positive["first_content"]
    assert sum(p["res"]["parsing_res_list"][0]["block_content"].count(data_row)
               for p in duplicate["input"]) == 2
    assert duplicate["first_content"].count(data_row) == 1
    assert not duplicate["second_content"]
    assert "<th>A</th>" in unrelated["first_content"]
    assert "<th>C</th>" in unrelated["first_content"]
    for result in docling["postmerge_table_imports"].values():
        assert result[0]["table_provenance_pages"] == [[1]]
        assert result[1]["status"] == "rejected"

    bundle = HERE / "paddle/relocated-bundle"
    for path, digest in read(bundle / "integrity.json").items():
        assert sha(bundle / path) == digest
    assets = read(bundle / "assets.json")
    for asset in assets:
        assert asset["source_revision_id"] == fixture["source_revision_id"]
        assert sha(bundle / asset["path"]) == asset["sha256"]
    images = [a for a in assets if a["block_id"] in (0, 1)]
    assert len({a["path"] for a in images}) == 2
    assert len({a["sha256"] for a in images}) == 2
    for result in (paddle, docling):
        assert result["model_calls"] == 0 and result["blocked_network_attempts"] == []
    assert docling["native_fenced_code_render_token_equal"]
    assert not docling["stock_fenced_code_render_token_equal"]
    assert docling["plain_algorithm_tag_literal_hidden_by_HTML"]

    write(HERE / "adjudication.json", {
        "scope": "Post-run checks and independent-review corrections; no behavioral rerun or input changes.",
        "registered_hashes_unchanged": len(registration["hashes"]),
        "stock_primary_contains_derived_image_OCR_and_chart_data": True,
        "native_numbered_display_formula_delimiters_and_number_preserved": True,
        "original_diagnostic_false_negatives": [
            "Docling direct substring misses escaped underscores; rendered visible text contains both markers.",
            "Exact unnumbered formula substring misses the correct numbered formula."],
        "paragraph_fragments_both_present": True,
        "paragraph_single_joined_string_absent_is_not_itself_a_semantic_failure": True,
        "native_logical_continuation_relation": "not supplied by page concatenation; full capability unproven",
        "cross_page_table_controls": {
            "positive_distinct_rows_merged": True,
            "legitimate_identical_data_row_count_before": 2,
            "legitimate_identical_data_row_count_after": 1,
            "fixture_intended_unrelated_tables_falsely_merged": True,
            "different_headers_are_not_universally_a_noncontinuation_oracle": True,
            "second_empty_fragment_import_rejected": True,
            "merged_table_has_only_first_page_provenance": True},
        "namespaced_asset_integrity_after_actual_move": True,
        "native_JPEG_export_not_claimed_pixel_exact_to_source_crop": True,
        "not_tested": ["real model outputs", "pipeline constructor or predict", "unnumbered bare formula in this fixture",
            "upstream dollar-literal normalization", "math typesetting", "rotation/unwarp inverse mapping",
            "complete supplement/caption ownership contract", "latency/GPU/load"],
        "full_required_method_verdict": "not_passed",
        "evidence_interpretation": "Export/postprocess/import boundaries, not recognition accuracy or a Paddle model failure."})
    print("Adjudication assertions passed; original registration and moved assets unchanged.")


if __name__ == "__main__":
    main()
