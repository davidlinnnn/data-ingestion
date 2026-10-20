"""Import actual Result exports and inspect source-preserving delivery; no inference."""
from copy import deepcopy
import html
from html.parser import HTMLParser
from pathlib import Path

from join_common import HERE, deny_network, read, sha, verify_registration, write


def main():
    verify_registration()
    network = deny_network()
    from docling.utils.paddleocr_vl_utils import parse_paddleocr_vl_result
    from docling_core.types.doc import DoclingDocument
    from markdown_it import MarkdownIt

    out = HERE / "docling"
    out.mkdir(exist_ok=False)
    fixture = read(HERE / "fixture.json")
    pages, checks, ledger = [], [], []
    for source in fixture["pages"]:
        page_no = source["page_index"] + 1
        raw = read(HERE / f"paddle/raw-p{page_no}.json")
        doc = parse_paddleocr_vl_result(raw)
        path = out / f"p{page_no}.json"
        doc.save_as_json(path)
        markdown = doc.export_to_markdown()
        (out / f"p{page_no}.md").write_text(markdown)
        assert DoclingDocument.load_from_json(path).export_to_markdown() == markdown
        assert list(doc.pages) == [page_no]
        assert doc.pages[page_no].size.width == source["width"]
        assert doc.pages[page_no].size.height == source["height"]
        assert all(prov.page_no == page_no for item, _ in doc.iterate_items() for prov in item.prov)
        picture = doc.pictures[0]
        box = picture.prov[0].bbox
        assert [box.l, box.t, box.r, box.b] == [100, 100, 220, 220]
        pdf_points_top_left = [v / fixture["render_scale"] for v in (box.l, box.t, box.r, box.b)]
        assert pdf_points_top_left == [50, 50, 110, 110]
        ledger.append({"output_part": f"p{page_no}.json", "source_document_id": fixture["document_id"],
            "source_revision_id": fixture["source_revision_id"], "source_pdf_sha256": sha(HERE / "sources/source.pdf"),
            "source_physical_page_no": page_no, "processed_pixel_canvas": [source["width"], source["height"]],
            "source_point_canvas": [source["width"] / 2, source["height"] / 2],
            "mapping": "Unrotated, unwarped144dpi renderer; x/2,y/2; explicit synthetic control only.",
            "picture_bbox_pdf_points_top_left": pdf_points_top_left,
            "importer_origin": doc.origin.model_dump(mode="json"),
            "importer_picture_has_image_bytes": picture.image is not None})
        checks.append({"page_no": page_no, "roundtrip_markdown_equal": True,
            "pixel_geometry_and_nonzero_source_page_preserved": True,
            "provider_nonempty_blocks": sum(bool(b["block_content"]) for b in raw["parsing_res_list"]),
            "image_content_in_docling_primary_markdown": "DERIVED_IMAGE_OCR_ONLY" in markdown,
            "chart_content_in_docling_primary_markdown": "DERIVED_CHART_DATA_ONLY" in markdown,
            "provider_ids_stored_in_Docling_items": any("block_id" in i.model_dump() for i, _ in doc.iterate_items())})
        pages.append(doc)

    combined = DoclingDocument.concatenate(pages)
    combined.save_as_json(out / "concatenated.json")
    (out / "concatenated.md").write_text(combined.export_to_markdown())
    assert list(combined.pages) == [1, 2]
    for output_page, entry in enumerate(ledger, 1):
        entry["aggregate_output_page_no"] = output_page
    write(out / "source-ledger.json", ledger)

    rejection = {}
    combined_payload = read(HERE / "paddle/combined-0.json")
    try:
        parse_paddleocr_vl_result(combined_payload)
    except ValueError as error:
        rejection["combined_result"] = str(error)
    assert "combined_result" in rejection
    for kind in ("negative_bbox", "out_of_bounds"):
        bad = deepcopy(read(HERE / "paddle/raw-p3.json"))
        bad["parsing_res_list"][0]["block_bbox"] = [-1, 20, 80, 40] if kind == "negative_bbox" else [0, 0, 9999, 9999]
        try:
            parse_paddleocr_vl_result(bad)
        except ValueError as error:
            rejection[kind] = str(error)
    assert len(rejection) == 3
    table_checks = {}
    for name, result in read(HERE / "paddle/table-controls.json").items():
        output = []
        for raw in result["output"]:
            try:
                table_doc = parse_paddleocr_vl_result(raw)
                output.append({"status": "imported", "table_count": len(table_doc.tables),
                    "table_provenance_pages": [[p.page_no for p in table.prov] for table in table_doc.tables]})
            except ValueError as error:
                output.append({"status": "rejected", "message": str(error)})
        table_checks[name] = output

    renderer = MarkdownIt("commonmark", {"html": True})
    native = (HERE / "paddle/relocated-bundle/document.md").read_text()
    stock = (out / "p3.md").read_text()
    expected_code = fixture["pages"][0]["blocks"][3]["content"]
    native_tokens = renderer.parse(native)
    stock_tokens = renderer.parse(stock)
    native_fences = [t.content for t in native_tokens if t.type == "fence"]
    stock_fences = [t.content for t in stock_tokens if t.type == "fence"]
    native_render = renderer.render(native)
    stock_render = renderer.render(stock)
    class VisibleText(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, text):
            self.parts.append(text)
    plain_view = VisibleText()
    plain_view.feed(renderer.render(expected_code))
    plain_visible = "".join(plain_view.parts)
    assert "<tag>" not in plain_visible and "$5 & " in plain_visible
    (out / "native-render.html").write_text(native_render)
    (out / "stock-render.html").write_text(stock_render)
    assert expected_code in native_fences
    assert any(t.type == "heading_open" for t in renderer.parse(expected_code))
    summary = {"model_calls": 0, "blocked_network_attempts": network, "pages": checks,
        "importer_scoped_to_processed_pixels": True, "source_mapping_requires_explicit_renderer_record": True,
        "aggregate_page_numbers": list(combined.pages), "original_pages_need_external_mapping": True,
        "importer_rejections": rejection, "postmerge_table_imports": table_checks,
        "native_fenced_code_render_token_equal": expected_code in native_fences,
        "stock_fenced_code_render_token_equal": expected_code in stock_fences,
        "plain_algorithm_is_not_code_in_commonmark": any(t.type == "heading_open" for t in renderer.parse(expected_code)),
        "plain_algorithm_tag_literal_hidden_by_HTML": "<tag>" not in plain_visible,
        "plain_algorithm_rendered_visible_text": plain_visible,
        "native_markdown_contains_source_caption": "Figure 1. Original source caption" in native,
        "native_markdown_contains_generated_image_OCR": "DERIVED_IMAGE_OCR_ONLY" in native,
        "native_markdown_contains_generated_chart_data": "DERIVED_CHART_DATA_ONLY" in native,
        "stock_primary_and_native_primary_are_different_artifacts": native != stock,
        "note": "CommonMark rendering tests literals/indentation; absence of a particular fence/typed label alone is not a failure. No math-rendering engine or recognition quality tested."}
    write(out / "results.json", summary)
    assert not network
    print("Official importer, JSON reload, pixel/point mapping control, aggregate renumbering, table-merge boundaries and actual Markdown token/render checks completed; zero inference.")


if __name__ == "__main__":
    main()
