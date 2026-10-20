"""Independent saved-artifact evaluation; no candidate inference or oracle changes."""

from copy import deepcopy
from difflib import SequenceMatcher
from hashlib import sha256
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
FROZEN_SHA = "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
SOURCE_SHA = "8ddae37b0461b3749402e44b4a40b0e65b3d6b9ad78cf2f03ed20d1950faba90"


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def whitespace(text):
    return re.sub(r"\s+", " ", text).strip()


def match_units(expected, texts):
    """Exact unit matching after neutral whitespace only; preserve producer indices."""
    rows = []
    for text in expected:
        positions = [i for i, candidate in enumerate(texts) if whitespace(candidate) == whitespace(text)]
        best = max(range(len(texts)), key=lambda i: SequenceMatcher(None, text, texts[i]).ratio()) if texts else None
        rows.append({"expected": text, "producer_indices": positions,
                     "exact_once": len(positions) == 1,
                     "closest_diagnostic_only": {"producer_index": best, "text": texts[best]} if best is not None else None})
    indices = [row["producer_indices"][0] for row in rows if row["exact_once"]]
    complete = len(indices) == len(expected)
    return {"units": rows, "expected_count": len(expected),
            "exact_once_count": sum(row["exact_once"] for row in rows),
            "all_exact_once": complete,
            "matched_indices_in_expected_order": indices,
            "all_units_in_order": complete and indices == sorted(set(indices)),
            "matched_subset_in_order": indices == sorted(set(indices)),
            "all_units_contiguous_in_producer": complete and indices == list(range(indices[0], indices[0] + len(indices)))}


def english_paragraphs(texts, expected):
    # G1-O03 explicitly allows joining layout lines and re- + sources.
    def normalize(text):
        return whitespace(text).replace("re- sources", "resources")
    actual = normalize(" ".join(texts))
    groups = (expected[:6], expected[6:])
    normalized = [normalize(" ".join(group)) for group in groups]
    positions = [actual.find(text) for text in normalized]
    between = actual[positions[0] + len(normalized[0]):positions[1]].strip() if all(p >= 0 for p in positions) else None
    return {"normalization": "Neutral whitespace, layout line joining, and explicitly allowed re- + sources joining only; punctuation and glyphs unchanged.",
            "paragraphs_present_without_interleaving": [p >= 0 for p in positions],
            "both_paragraphs_in_order": all(p >= 0 for p in positions) and positions[0] < positions[1],
            "no_unrelated_content_between_selected_paragraphs": between == "",
            "intervening_content": between}


def matrix_point(matrix, point):
    x, y = point
    v = [sum(matrix[r][c] * (x, y, 1)[c] for c in range(3)) for r in range(3)]
    return [v[0] / v[2], v[1] / v[2]]


def inverse_correction_point(point, correction, source_width, source_height):
    x, y = point
    return {0: [x, y], 90: [source_width - y, x],
            180: [source_width - x, source_height - y],
            270: [y, source_height - x]}[correction]


def inverse_correction_polygon(polygon, correction, source_width, source_height):
    return [inverse_correction_point(point, correction, source_width, source_height) for point in polygon]


def correct_angle(source_content_ccw, correction_ccw):
    return (source_content_ccw + correction_ccw) % 360 == 0


def flattened_texts(document):
    nodes = {"#/body": document["body"], "#/furniture": document["furniture"]}
    for name in ("texts", "groups", "pictures", "tables"):
        nodes.update({node["self_ref"]: node for node in document.get(name, [])})
    rows = []

    def visit(node_ref):
        node = nodes[node_ref]
        if "text" in node:
            rows.append(node)
        for child in node.get("children", []):
            visit(child.get("$ref", child.get("cref")))
    visit("#/body")
    return rows


def bbox(poly):
    return [min(p[0] for p in poly), min(p[1] for p in poly), max(p[0] for p in poly), max(p[1] for p in poly)]


def max_error(a, b):
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return max((max_error(x, y) for x, y in zip(a, b)), default=0)
    return abs(a - b)


def geometry_errors(mapping, records, physical_page):
    errors = []
    width, height = mapping["source_render_pixels_wh"]
    correction = mapping["model_predicted_corrective_ccw_degrees"]
    scale = mapping["source_render_scale_pixels_per_point"]
    for i, row in enumerate(records):
        expected_pixels = inverse_correction_polygon(row["normalized_polygon_pixels"], correction, width, height)
        expected_points = [[x / scale, y / scale] for x, y in expected_pixels]
        if row["original_physical_page_1based"] != physical_page:
            errors.append({"index": i, "error": "wrong physical page"})
        # A float arithmetic consistency check, not a source-envelope/IoU tolerance.
        for key, expected in (("original_source_polygon_pixels", expected_pixels),
                              ("original_source_polygon_pdf_points_top_left", expected_points),
                              ("original_source_bbox_pdf_points_top_left", bbox(expected_points))):
            if max_error(row[key], expected) > 1e-8:
                errors.append({"index": i, "error": key, "maximum_arithmetic_error": max_error(row[key], expected)})
    return errors


def orientation_run(page, case):
    path = WORK / "orientation/runs" / f"p{page}"
    orientation = read(path / "orientation.json")
    mapping = read(path / "source-mapping.json")
    output = read(path / "ocr.json")
    raw = read(path / "raw-ocr-stages.json")
    runtime = read(path / "runtime.json")
    manifest = read(WORK / "orientation/input-manifest.json")
    entry = next(row for row in manifest["pages"] if row["physical_page_1based"] == page)
    expected = case["details"]["oracle"]["expected_region_transcript"].splitlines()
    matches = match_units(expected, output["texts"])
    indices = [row["producer_indices"][0] for row in matches["units"] if row["exact_once"]]
    selected_boxes = [output["source_mapped_boxes"][i] for i in indices]
    oracle = case["details"]["oracle"]
    independent_source_envelope = bbox([point for row in selected_boxes for point in row["original_source_polygon_pdf_points_top_left"]])
    raw_values = orientation["raw_outputs"][0][0]
    labels = [0, 90, 180, 270]
    class_id = max(range(4), key=lambda i: raw_values[i])
    correction = orientation["correction_ccw_degrees"]
    width, height = mapping["source_render_pixels_wh"]
    normalized_w, normalized_h = mapping["normalized_pixels_wh"]
    corner_checks = []
    for point in [[0, 0], [normalized_w, 0], [0, normalized_h], [normalized_w, normalized_h]]:
        original = inverse_correction_point(point, correction, width, height)
        matrix_original = matrix_point(mapping["normalized_raster_to_source_raster_3x3"], point)
        matrix_normalized = matrix_point(mapping["source_raster_to_normalized_raster_3x3"], original)
        matrix_points = matrix_point(mapping["normalized_raster_to_original_pdf_points_3x3"], point)
        corner_checks.append(max_error(original, matrix_original) <= 1e-8 and max_error(point, matrix_normalized) <= 1e-8
            and max_error(matrix_points, [v / mapping["source_render_scale_pixels_per_point"] for v in original]) <= 1e-8)
    return {"path": str(path.relative_to(ROOT)), "case": case["id"],
            "artifact_sha256": {f: digest(path / f) for f in ("orientation.json", "source-mapping.json", "ocr.json", "raw-ocr-stages.json", "runtime.json", "normalized.png")},
            "source_hash_matches": mapping["source_sha256"] == SOURCE_SHA and runtime["source_pdf_sha256"] == SOURCE_SHA,
            "input_render_hash_matches": digest(ROOT / entry["path"]) == entry["sha256"] == runtime["source_render_sha256"],
            "normalized_hash_matches": digest(path / "normalized.png") == runtime["normalized_sha256"],
            "physical_page_correct": mapping["physical_page_1based"] == orientation["physical_page_1based"] == page,
            "source_rotate_metadata_zero": mapping["pdf_rotate_degrees"] == 0,
            "native_text_absent": entry["native_text_characters"] == 0,
            "model_outputs": {"raw_values": raw_values, "class_id": class_id, "correction_ccw_degrees": correction,
                "matches_model_argmax_and_label": orientation["class_ids"] == [class_id] and correction == labels[class_id],
                "source_content_ccw_degrees": oracle["source_content_rotation_ccw_degrees"],
                "corrective_angle_correct": correct_angle(oracle["source_content_rotation_ccw_degrees"], correction)},
            "all_live_sessions_cpu": orientation["providers"] == ["CPUExecutionProvider"] and
                all(s["providers"] == ["CPUExecutionProvider"] for s in runtime["sessions"].values()),
            "dictionary": runtime["dictionary"], "provider_texts": output["texts"],
            "selected_lines": matches, "selected_paragraphs": english_paragraphs(output["texts"], expected),
            "all_corner_matrix_checks_pass": all(corner_checks),
            "filtered_geometry_errors": geometry_errors(mapping, output["source_mapped_boxes"], page),
            "raw_geometry_errors": geometry_errors(mapping, raw["source_mapped_boxes"], page),
            "selected_source_envelope": independent_source_envelope,
            "frozen_source_envelope": case["details"]["locators"][0]["bbox_points_top_left"],
            "source_envelope_assessment": "Report coordinates for manual source-region comparison; no new IoU acceptance threshold.",
            "coordinate_convention": mapping["coordinates"]}


def baseline_run(name, case, lane="baseline", expected_source_sha=SOURCE_SHA):
    path = WORK / f"{lane}/runs" / name
    doc = read(path / "document.json")
    metrics = read(path / "metrics.json")
    raw_calls = [read(p) for p in sorted((path / "raw-ocr-calls").glob("*.raw.json"))]
    outputs = [read(p) for p in sorted((path / "raw-ocr-calls").glob("*.output.json"))]
    texts = [text for call in outputs for text in call["texts"]]
    doc_rows = flattened_texts(doc)
    result = {"path": str(path.relative_to(ROOT)), "case": case["id"],
              "source_hash_matches": metrics["source_sha256"] == expected_source_sha,
              "document_hash_matches": digest(path / "document.json") == metrics["document_sha256"],
              "artifact_sha256": {f: digest(path / f) for f in
                  ("document.json", "document.md", "conversion-result.json", "producer.json", "method.json", "metrics.json", "cell-merge.json")},
              "raw_recognizer_texts": [call["recognizer_texts"] for call in raw_calls],
              "raw_recognizer_scores": [call["recognizer_scores"] for call in raw_calls],
              "raw_classifier_results": [call["classifier_results"] for call in raw_calls],
              "provider_texts": texts,
              "source_mappings": [call["source_mapping"] for call in outputs],
              "all_output_mappings_correct_physical_page": all(call["source_mapping"]["physical_page_1based"] == case["physical_pages_1based"][0] for call in outputs),
              "all_document_provenance_correct_physical_page": all(p["page_no"] == case["physical_pages_1based"][0] for row in doc["texts"] for p in row["prov"]),
              "document_texts_in_tree_order": [{"ref": row["self_ref"], "label": row["label"], "text": row["text"], "parent": row.get("parent"), "prov": row["prov"]} for row in doc_rows]}
    oracle = case["details"]["oracle"]
    if case["id"] in ("G1-C08", "G1-C09", "G1-C10", "G1-C11"):
        expected = oracle["expected_region_transcript"].splitlines()
        result["provider_selected_lines"] = match_units(expected, texts)
        result["provider_selected_paragraphs"] = english_paragraphs(texts, expected)
        result["document_selected_paragraphs"] = english_paragraphs([row["text"] for row in doc_rows], expected)
        result["orientation_method"] = "Stock baseline has no learned whole-page correction stage; per-line classifier output is not document orientation."
    else:
        merge = read(path / "cell-merge.json")
        result["cell_merge_counts"] = {k: len(merge[k]) for k in ("native_before", "ocr_before", "merged_after")}
        result["native_cells_before"] = merge["native_before"]
        result["merged_cells_after"] = merge["merged_after"]
        if case["id"] == "G1-C12":
            expected_image = oracle["image_expected_transcript"].splitlines()
            result["provider_image_units"] = match_units(expected_image, texts)
            result["document_image_units"] = match_units(expected_image, [row["text"] for row in doc_rows])
            result["native_counts"] = {key: {
                "document": sum(row["text"] == oracle[key] for row in doc["texts"]),
                "markdown": (path / "document.md").read_text().count(oracle[key]),
                "merged_cells": sum(row["text"] == oracle[key] for row in merge["merged_after"]),
                "merged_native_cells": sum(row["text"] == oracle[key] and not row["from_ocr"] for row in merge["merged_after"])}
                for key in ("native_text_before", "native_text_after", "source_caption", "additional_native_mixed_line")}
            caption_refs = [row["self_ref"] for row in doc["texts"] if row["text"] == oracle["source_caption"]]
            result["caption_attached_to_picture"] = len(caption_refs) == 1 and any(
                any(ref.get("$ref", ref.get("cref")) == caption_refs[0] for ref in pic.get("captions", [])) for pic in doc["pictures"])
            result["ocr_text_picture_children"] = [row["self_ref"] for row in doc["texts"]
                if row["text"] in texts and row.get("parent", {}).get("$ref", "").startswith("#/pictures/") and row["label"] != "caption"]
            markdown = (path / "document.md").read_text()
            result["main_markdown"] = markdown
            result["main_markdown_has_usable_image_reference"] = bool(re.search(r"!\[[^\]]*\]\([^)]+\)", markdown))
            result["picture_embedded_image_present"] = any(pic.get("image", {}).get("uri", "").startswith("data:image/") for pic in doc["pictures"])
        else:
            expected = oracle["expected_ordered_blocks"]
            result["provider_complete_page_blocks"] = match_units(expected, texts)
            result["document_complete_page_blocks"] = match_units(expected, [row["text"] for row in doc_rows])
            blocks = [re.sub(r"^#{1,6} ", "", b) for b in (path / "document.md").read_text().split("\n\n")]
            result["main_markdown_complete_page_blocks"] = match_units(expected, blocks)
            result["raster_ocr_native_cell_count"] = len(merge["native_before"])
    return result


def normalized_integration(page, case):
    manifest = read(WORK / "normalized/input-manifest.json")
    source = manifest["sources"][0]
    entry = next(row for row in manifest["pages"] if row["derived_physical_page_1based"] == page)
    path = WORK / "normalized/runs" / f"normalized-p{page}-full"
    result = baseline_run(f"normalized-p{page}-full", case, "normalized", source["sha256"])
    result["orientation_method"] = "Standard CPU conversion of an explicitly derived normalized raster PDF; additional PDF/render boundary, not original source bytes."
    wrapper = read(path / "mapped-review.json")
    doc = read(path / "document.json")
    nodes = {row["self_ref"]: row for name in ("texts", "pictures", "tables") for row in doc[name]}
    errors = []
    if [row["derivative_ref"] for row in wrapper["items"]] != list(nodes):
        errors.append("wrapper item identity/order differs")
    if wrapper["body_ordered_refs"] != doc["body"]["children"] or wrapper["furniture_ordered_refs"] != doc["furniture"]["children"]:
        errors.append("wrapper root traversal differs")
    width, height = wrapper["original_page_size_points"]
    correction = entry["classifier_predicted_correction_ccw_degrees"]
    for row in wrapper["items"]:
        original = nodes[row["derivative_ref"]]
        for key in ("text", "orig", "parent", "children", "captions", "label"):
            if row.get(key, [] if key in ("children", "captions") else None) != original.get(key, [] if key in ("children", "captions") else None):
                errors.append(f"wrapper changed {row['derivative_ref']} {key}")
        if len(row["mapped_locations"]) != len(original["prov"]):
            errors.append(f"wrapper provenance count {row['derivative_ref']}")
        for loc, prov in zip(row["mapped_locations"], original["prov"]):
            if loc["derivative_provenance"] != prov or loc["original_physical_page_1based"] != page:
                errors.append(f"wrapper provenance/page {row['derivative_ref']}")
            box = prov["bbox"]
            top = doc["pages"][str(page)]["size"]["height"] - box["t"] if box["coord_origin"] == "BOTTOMLEFT" else box["t"]
            bottom = doc["pages"][str(page)]["size"]["height"] - box["b"] if box["coord_origin"] == "BOTTOMLEFT" else box["b"]
            quad = [[box["l"], top], [box["r"], top], [box["r"], bottom], [box["l"], bottom]]
            expected = inverse_correction_polygon(quad, correction, width, height)
            if max_error(expected, loc["original_source_quad_top_left_points"]) > 1e-8 or max_error(bbox(expected), loc["original_source_envelope_top_left_points"]) > 1e-8:
                errors.append(f"wrapper inverse geometry {row['derivative_ref']}")
            if any(max_error(matrix_point(wrapper["normalized_pdf_top_left_to_original_pdf_top_left_3x3"], point), mapped) > 1e-8 for point, mapped in zip(quad, expected)):
                errors.append(f"wrapper matrix {row['derivative_ref']}")
    result["derivation"] = {"identity": manifest["identity"], "derived_source_sha256": source["sha256"],
        "derived_source_hash_matches": digest(ROOT / source["path"]) == source["sha256"],
        "original_source_sha256": manifest["original_source"]["sha256"],
        "original_source_identity_correct": manifest["original_source"]["sha256"] == SOURCE_SHA and source["sha256"] != SOURCE_SHA,
        "normalized_input_hash_matches": digest(ROOT / entry["normalized_image_path"]) == entry["normalized_image_sha256"],
        "classifier_record_hash_matches": digest(ROOT / entry["orientation_result_path"]) == entry["orientation_result_sha256"],
        "classifier_mapping_hash_matches": digest(ROOT / entry["source_mapping_path"]) == entry["source_mapping_sha256"],
        "wrapper_hash": digest(path / "mapped-review.json"), "wrapper_errors": errors,
        "scope": wrapper["scope"], "local_worker_source_id_alias": manifest["compatibility_alias"]}
    return result


def line_classifier_diagnostic(name, case):
    path = WORK / "line-cls/runs" / name
    baseline = WORK / "baseline/runs" / name
    raw = read(path / "raw.json")
    old_raw = read(baseline / "raw-ocr-calls/000.raw.json")
    output = read(path / "output.json")
    producer = read(path / "producer.json")
    old_producer = read(baseline / "producer.json")
    oracle = case["details"]["oracle"]
    expected = oracle.get("image_expected_transcript", "").splitlines() if case["id"] == "G1-C12" else oracle["expected_ordered_blocks"]
    instruction = (oracle["image_expected_transcript"].splitlines()[3] if case["id"] == "G1-C12" else expected[5])
    # Explicit diagnostic of the base O01 quotation/whitespace allowance; never changes strict scores.
    def quote_words(text):
        return re.sub(r"\s+", "", text.replace("“", '"').replace("”", '"'))
    return {"case": case["id"], "path": str(path.relative_to(ROOT)),
            "scope": "Two saved exact-input OCR calls with line classification disabled; no Standard document delivery or acceptance claim.",
            "artifact_sha256": {f: digest(path / f) for f in ("raw.json", "output.json", "producer.json")},
            "baseline_producer_hash_matches": digest(ROOT / producer["baseline_producer_path"]) == producer["baseline_producer_sha256"],
            "exact_baseline_input_png_hash_matches": digest(ROOT / producer["input_png_path"]) == producer["input_png_sha256"],
            "resolved_config_identical": producer["resolved_config"] == old_producer["resolved_config"],
            "model_and_dictionary_identical": producer["model_sha256"] == old_producer["model_sha256"] and all(
                producer["recognizer_dictionary"][k] == old_producer["recognizer_dictionary"][k]
                for k in ("character_count", "utf8_newline_joined_sha256")),
            "dictionary_origin_description": {"baseline": old_producer["recognizer_dictionary"]["origin"],
                "diagnostic": producer["recognizer_dictionary"]["origin"]},
            "source_mapping_identical": output["source_mapping"] == read(baseline / "raw-ocr-calls/000.output.json")["source_mapping"],
            "all_detector_and_preprocessing_fields_identical": all(raw[k] == old_raw[k] for k in
                ("detector_boxes_before_mapping", "detector_boxes_crop_pixels", "detector_scores", "preprocessing_coordinate_record", "input_image_shape_hwc")),
            "call_disables_line_classifier": output["effective_call_kwargs"] == {"use_cls": False} and producer["effective_use_cls_after_call"] is False,
            "line_classifier_inference_calls": producer["line_classifier_inference_calls"],
            "raw_classifier_results_absent": raw["classifier_results"] is None,
            "all_sessions_cpu": all(s["providers"] == ["CPUExecutionProvider"] for s in producer["actual_sessions"].values()),
            "provider_units": match_units(expected, output["texts"]),
            "raw_text_changes": [{"producer_index": i, "before": old, "after": new,
                "baseline_classifier": old_raw["classifier_results"][i], "new_recognizer_score": raw["recognizer_scores"][i]}
                for i, (old, new) in enumerate(zip(old_raw["recognizer_texts"], raw["recognizer_texts"])) if old != new],
            "strict_instruction_present": any(whitespace(text) == whitespace(instruction) for text in output["texts"]),
            "instruction_words_match_after_explicit_curly_quote_and_whitespace_normalization": any(quote_words(text) == quote_words(instruction) for text in output["texts"]),
            "normalization_diagnostic_policy": "Curly quotes to ASCII and neutral whitespace removal for this Chinese instruction only, reported separately from strict scoring; no Simplified/Traditional conversion.",
            "provider_texts": output["texts"]}


def self_checks(cases):
    expected = cases["G1-C13"]["details"]["oracle"]["expected_ordered_blocks"]
    tests = {}
    altered = expected.copy(); altered[1], altered[8] = altered[8], altered[1]
    tests["reject_swapped_order"] = not match_units(expected, altered)["all_units_in_order"]
    tests["reject_duplicate_native_line"] = not match_units(expected, expected + [expected[1]])["all_exact_once"]
    altered = expected.copy(); altered[5] = altered[5].replace('"連結"', '＂連結＂')
    tests["reject_silent_fullwidth_quote_change"] = not match_units(expected, altered)["all_exact_once"]
    altered = expected.copy(); altered[2] = altered[2].replace("系統", "系统")
    tests["reject_silent_simplified_glyph_change"] = not match_units(expected, altered)["all_exact_once"]
    lane = orientation_run(4, cases["G1-C09"])
    tests["reject_corrective_angle_sign"] = lane["model_outputs"]["corrective_angle_correct"] and not correct_angle(90, 90)
    mapping = read(WORK / "orientation/runs/p4/source-mapping.json")
    records = read(WORK / "orientation/runs/p4/ocr.json")["source_mapped_boxes"]
    assert not geometry_errors(mapping, records, 4)
    altered = deepcopy(records); altered[1]["original_source_polygon_pixels"] = altered[1]["normalized_polygon_pixels"]
    tests["reject_skipped_inverse_coordinate_map"] = bool(geometry_errors(mapping, altered, 4))
    altered = deepcopy(records); altered[1]["original_physical_page_1based"] = 1
    tests["reject_wrong_source_page"] = bool(geometry_errors(mapping, altered, 4))
    assert all(tests.values()), tests
    return tests


def main():
    assert digest(FROZEN) == FROZEN_SHA, "frozen oracle changed"
    assert digest(ROOT / "docs/fixtures/pdf-core-g1-controls-2026-10-14/controls.pdf") == SOURCE_SHA
    cases = {case["id"]: case for case in read(FROZEN)["cases"]}
    runs = [(f"controls-p{page}-full", f"G1-C{page+5:02}") for page in range(3, 7)]
    runs += [("controls-p7-selective", "G1-C12"), ("controls-p7-full", "G1-C12"), ("controls-p8-full", "G1-C13")]
    result = {"format": "orientation-mixed-ocr-independent-review-v1", "frozen_cases_sha256": digest(FROZEN),
              "checker_sha256": digest(__file__), "source_check": read(WORK / "review/source-check.json"),
              "independent_pixel_and_tensor_check": read(WORK / "review/pixel-check.json"),
              "method": "Saved artifacts only, strict text plus neutral whitespace; diagnostic closest matches do not grant credit. No inference, CER/IoU thresholds or oracle edits.",
              "baseline": {name: baseline_run(name, cases[case_id]) for name, case_id in runs},
              "orientation": {f"p{page}": orientation_run(page, cases[f"G1-C{page+5:02}"]) for page in range(3, 7)},
              "normalized_standard_integration": {f"p{page}": normalized_integration(page, cases[f"G1-C{page+5:02}"]) for page in range(3, 7)},
              "line_classifier_diagnostics": {name: line_classifier_diagnostic(name, cases[case_id]) for name, case_id in
                  (("controls-p7-selective", "G1-C12"), ("controls-p8-full", "G1-C13"))},
              "self_checks": self_checks(cases)}
    (WORK / "review/output-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"self_checks": result["self_checks"], "baseline": {
        name: {key: value for key, value in lane.items() if key.endswith("paragraphs") or key in ("native_counts", "main_markdown_has_usable_image_reference") or key.endswith("blocks") or key.endswith("selected_lines")}
        for name, lane in result["baseline"].items()}}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
