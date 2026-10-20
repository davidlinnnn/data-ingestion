"""Actual pinned Result/disk-export and pure postprocess controls; no models."""
from copy import deepcopy
from pathlib import Path
import shutil

from join_common import HERE, deny_network, read, sha, verify_registration, write


def main():
    verify_registration()
    network = deny_network()
    from PIL import Image
    from paddlex.inference.pipelines.paddleocr_vl.result import PaddleOCRVLBlock, PaddleOCRVLResult
    from paddlex.inference.pipelines.paddleocr_vl.pipeline import _PaddleOCRVLPipeline
    from paddlex.inference.pipelines.layout_parsing.utils import construct_img_path

    fixture = read(HERE / "fixture.json")
    out = HERE / "paddle"
    out.mkdir(exist_ok=False)

    def make_page(page):
        blocks = []
        for row in page["blocks"]:
            block = PaddleOCRVLBlock(row["label"], row["bbox"], row["content"], group_id=row.get("group_id"))
            if row["label"] in ("image", "chart"):
                box = row["bbox"]
                with Image.open(HERE / f"sources/page-{page['page_index'] + 1}.png") as raster:
                    crop = raster.convert("RGB").crop(box)
                block.image = {"path": construct_img_path(row["label"], box), "img": crop}
            blocks.append(block)
        return PaddleOCRVLResult({"input_path": "synthetic-source.pdf", "page_index": page["page_index"],
            "page_count": page["page_count"], "width": page["width"], "height": page["height"],
            "parsing_res_list": blocks, "imgs_in_doc": [], "layout_det_res": {"boxes": []},
            "model_settings": {"use_doc_preprocessor": False, "use_layout_detection": True,
                "format_block_content": False, "use_chart_recognition": True,
                "use_ocr_for_image_block": False, "use_seal_recognition": False, "markdown_ignore_labels": []}})

    pages = [make_page(p) for p in fixture["pages"]]
    for n, page in enumerate(pages, 3):
        page.save_to_json(str(out / f"raw-p{n}.json"))
        write(out / f"wrapped-p{n}.json", page.json)
    original = [deepcopy(page.json) for page in pages]
    assert read(out / "raw-p3.json") == original[0]["res"]

    shared = out / "shared"
    shared.mkdir()
    pages[0].save_to_markdown(shared / "p3.md", pretty=False, show_formula_number=True)
    image_path = pages[0]["parsing_res_list"][1].image["path"]
    before = sha(shared / image_path)
    pages[1].save_to_markdown(shared / "p4.md", pretty=False, show_formula_number=True)
    after = sha(shared / image_path)
    assert before != after, "predeclared same-bbox distinct-image collision control"
    assert image_path in (shared / "p3.md").read_text() and image_path in (shared / "p4.md").read_text()

    # Asset-only export view; original provider content and first serialization stay immutable.
    bundle = out / "bundle-before-move"
    bundle.mkdir()
    views, assets = [], []
    for n, page in enumerate(pages, 3):
        view = deepcopy(page)
        for block_id, block in enumerate(view["parsing_res_list"]):
            if block.image is not None:
                block.image["path"] = f"pages/p{n}/" + block.image["path"]
                assets.append({"image_key": f"{fixture['document_id']}:{fixture['source_revision_id']}:p{n}:b{block_id}",
                    "source_revision_id": fixture["source_revision_id"], "page_no": n, "block_id": block_id,
                    "path": block.image["path"], "bbox_processed_pixels": block.bbox})
        view.save_to_markdown(bundle / f"page-{n}.md", pretty=False, show_formula_number=True)
        views.append(view._to_markdown(pretty=False, show_formula_number=True))
    master = _PaddleOCRVLPipeline.concatenate_markdown_pages(None, views)
    (bundle / "document.md").write_text(master)
    for asset in assets:
        asset["sha256"] = sha(bundle / asset["path"])
    write(bundle / "assets.json", assets)
    for n in (3, 4):
        shutil.copyfile(out / f"raw-p{n}.json", bundle / f"raw-p{n}.json")
    frozen = {str(p.relative_to(bundle)): sha(p) for p in bundle.rglob("*") if p.is_file()}
    write(bundle / "integrity.json", frozen)
    moved = out / "relocated-bundle"
    shutil.move(str(bundle), str(moved))

    def check_assets(root, revision):
        for item in read(root / "assets.json"):
            assert item["source_revision_id"] == revision, "foreign revision"
            path = (root / item["path"]).resolve()
            assert path.is_relative_to(root.resolve()), "foreign asset path"
            assert sha(path) == item["sha256"], "missing or changed asset"

    check_assets(moved, fixture["source_revision_id"])
    assert all(sha(moved / path) == digest for path, digest in frozen.items())
    assert not bundle.exists()
    assert len({a["image_key"] for a in assets}) == len(assets)
    assert len({a["path"] for a in assets}) == len(assets)
    negative = []
    try:
        check_assets(moved, "synthetic-revision-B")
    except AssertionError:
        negative.append("foreign_revision_rejected")
    target = moved / assets[0]["path"]
    target.rename(target.with_suffix(".held"))
    try:
        check_assets(moved, fixture["source_revision_id"])
    except FileNotFoundError:
        negative.append("missing_image_rejected")
    finally:
        target.with_suffix(".held").rename(target)
    assert len(negative) == 2
    check_assets(moved, fixture["source_revision_id"])
    assert [p.json for p in pages] == original

    live = list(_PaddleOCRVLPipeline.restructure_pages(None, deepcopy(pages),
        merge_tables=False, relevel_titles=False, concatenate_pages=False))
    saved = list(_PaddleOCRVLPipeline.restructure_pages(None, deepcopy(original),
        merge_tables=False, relevel_titles=False, concatenate_pages=False))
    combined = list(_PaddleOCRVLPipeline.restructure_pages(None, deepcopy(pages),
        merge_tables=False, relevel_titles=False, concatenate_pages=True))[0]
    for name, values in (("live", live), ("saved", saved), ("combined", [combined])):
        for i, page in enumerate(values):
            write(out / f"{name}-{i}.json", page.json)
            page.save_to_markdown(out / name / f"page-{i}.md", pretty=False, show_formula_number=True)
    code_before = pages[0]["parsing_res_list"][3].content
    code_after = saved[0]["parsing_res_list"][3].content
    assert code_before.startswith("# source comment") and code_after.startswith("source comment")

    table_results = {}
    for case in fixture["table_control"]["cases"]:
        second_header = ["C", "D"] if case == "different_headers_unrelated_tables_negative" else ["A", "B"]
        second_data = ["a", "1"] if case == "same_headers_identical_data_row_negative" else ["b", "2"]
        table_pages = []
        for index, (header, data) in enumerate([(["A", "B"], ["a", "1"]), (second_header, second_data)]):
            text = "<table><tr>" + "".join(f"<th>{v}</th>" for v in header) + "</tr><tr>" + "".join(f"<td>{v}</td>" for v in data) + "</tr></table>"
            page = {"page_index": index, "page_count": 2, "width": 800, "height": 1000, "color": "white",
                "blocks": [{"label": "table", "bbox": [10, 100 if index == 0 else 20, 210, 300 if index == 0 else 220], "content": text}]}
            table_pages.append(make_page(page))
        raw = [deepcopy(p.json) for p in table_pages]
        merged = list(_PaddleOCRVLPipeline.restructure_pages(None, table_pages,
            merge_tables=True, relevel_titles=False, concatenate_pages=False))
        table_results[case] = {"input": raw, "output": [p.json for p in merged],
            "first_content": merged[0]["parsing_res_list"][0].content,
            "second_content": merged[1]["parsing_res_list"][0].content}
    assert not table_results["same_headers_distinct_rows_positive"]["second_content"]
    write(out / "table-controls.json", table_results)

    first_md = views[0]["markdown_texts"]
    report = {"model_calls": 0, "blocked_network_attempts": network, "complete_Result_and_disk_export": True,
        "postprocess_scope": "Actual unbound official postprocess method, self=None; no pipeline constructor or model factory.",
        "shared_directory_image_overwrite": before != after, "image_key_collision_path": image_path,
        "asset_only_namespacing_move_and_reload": True, "asset_negative_controls": negative,
        "original_provider_serializations_unchanged": [p.json for p in pages] == original,
        "native_json_embeds_images": any("image" in b for b in original[0]["res"]["parsing_res_list"]),
        "native_inline_prose_literal_preserved": fixture["pages"][0]["blocks"][5]["content"] in first_md,
        "native_plain_algorithm_literal_preserved_in_markdown_source": code_before in first_md,
        "native_fenced_algorithm_literal_preserved": fixture["pages"][0]["blocks"][4]["content"] in first_md,
        "native_image_ocr_in_primary_markdown": "DERIVED_IMAGE_OCR_ONLY" in first_md,
        "native_chart_data_in_primary_markdown": "DERIVED_CHART_DATA_ONLY" in first_md,
        "native_separate_inline_reassembled": "Before inline formula $x_i < y_j$ after inline formula." in first_md,
        "native_display_bare_formula_delimited": "$$E = mc^2$$" in first_md,
        "native_formula_number_in_markdown": "(7)" in first_md,
        "saved_dict_restructure_changes_code_comment": code_after != code_before,
        "live_restructure_preserves_code_comment": live[0]["parsing_res_list"][3].content == code_before,
        "live_group_before": original[0]["res"]["parsing_res_list"][6:9],
        "live_group_after": live[0].json["res"]["parsing_res_list"][6:9],
        "saved_dict_image_has_bytes": saved[0]["parsing_res_list"][1].image["img"] is not None,
        "combined_page_index": combined["page_index"], "combined_page_count": combined["page_count"],
        "combined_width_height": [combined["width"], combined["height"]],
        "combined_block_dynamic_page_indexes": [b.page_index for b in combined["parsing_res_list"]],
        "combined_block_json_has_page_index": any("page_index" in b for b in combined.json["res"]["parsing_res_list"]),
        "native_paragraph_continuation_reconstructed": "A paragraph starts here and continues on the next page without a new paragraph." in master}
    write(out / "results.json", report)
    assert not network
    print("Actual Result export, image collision, namespaced relocation, live/saved/combined restructuring and three table controls completed; zero inference.")


if __name__ == "__main__":
    main()
