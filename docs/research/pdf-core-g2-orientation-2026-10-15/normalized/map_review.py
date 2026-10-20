"""Validate four saved results and map review provenance without changing provider data."""

import importlib.util
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def transform(matrix, point):
    x, y = point
    return [matrix[0][0]*x + matrix[0][1]*y + matrix[0][2],
            matrix[1][0]*x + matrix[1][1]*y + matrix[1][2]]


def main():
    spec = importlib.util.spec_from_file_location("derived_standard_run", HERE / "run.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    assert run.check() == read(HERE / "frozen-inputs.json")
    manifest, summary = read(HERE / "input-manifest.json"), read(HERE / "summary.json")
    assert len(summary["jobs"]) == 4
    completed = []
    for job, source_page in zip(summary["jobs"], manifest["pages"], strict=True):
        assert job["execution_status"] == "completed" and job["stopped"] is None
        assert job["sampled_tree_peak_rss_bytes"] < 6*1024**3
        folder = HERE / "runs" / job["name"]
        document, result = read(folder / "document.json"), read(folder / "conversion-result.json")
        assert DoclingDocument.model_validate(result["document"]) == DoclingDocument.model_validate(document)
        derivative_page = source_page["derived_physical_page_1based"]
        assert set(document["pages"]) == {str(derivative_page)}
        assert document["origin"]["filename"] == "derived-normalized-controls.pdf"
        assert read(folder / "metrics.json")["source_sha256"] == manifest["sources"][0]["sha256"]
        producer, method = read(folder / "producer.json"), read(folder / "method.json")
        assert all(s["providers"] == ["CPUExecutionProvider"] for s in producer["actual_sessions"].values())
        assert method["options"]["accelerator_options"]["device"] == "cpu"
        assert method["options"]["layout_batch_size"] == method["options"]["ocr_batch_size"] == method["options"]["table_batch_size"] == 1
        original_mapping = source_page["classifier_source_mapping"]
        raster_matrix = original_mapping["normalized_raster_to_original_pdf_points_3x3"]
        point_matrix = [[row[0]*3, row[1]*3, row[2]] for row in raster_matrix[:2]] + [[0, 0, 1]]
        original_size = original_mapping["source_page_size_points"]
        corners = [transform(point_matrix, p) for p in [(0, 0), (612, 0), (612, 792), (0, 792)]]
        assert sorted((round(x, 7), round(y, 7)) for x, y in corners) == sorted(
            [(0, 0), (original_size[0], 0), tuple(original_size), (0, original_size[1])])
        items = []
        for collection in ("texts", "pictures", "tables", "key_value_items", "form_items"):
            for item in document[collection]:
                locations = []
                for provenance in item.get("prov", []):
                    assert provenance["page_no"] == derivative_page
                    box = provenance["bbox"]
                    top, bottom = (box["t"], box["b"]) if box["coord_origin"] == "TOPLEFT" else (792-box["t"], 792-box["b"])
                    quad = [transform(point_matrix, p) for p in
                            [(box["l"], top), (box["r"], top), (box["r"], bottom), (box["l"], bottom)]]
                    xs, ys = [p[0] for p in quad], [p[1] for p in quad]
                    locations.append({"derivative_provenance": provenance,
                        "original_physical_page_1based": source_page["original_physical_page_1based"],
                        "original_source_quad_top_left_points": quad,
                        "original_source_envelope_top_left_points": [min(xs), min(ys), max(xs), max(ys)]})
                items.append({"derivative_ref": item["self_ref"], "parent": item.get("parent"),
                    "children": item.get("children", []), "captions": item.get("captions", []),
                    "label": item["label"], "text": item.get("text"), "orig": item.get("orig"),
                    "mapped_locations": locations})
        review = {"format": "g2-derived-standard-original-source-review-v1",
            "scope": "Mapped review wrapper only, not a provider ConversionResult or Canonical representation",
            "raw_derivative_document_unchanged": True,
            "derived_source": manifest["sources"][0],
            "derived_physical_page_1based": derivative_page,
            "derived_page_size_points": [612, 792],
            "original_source": manifest["original_source"],
            "original_physical_page_1based": source_page["original_physical_page_1based"],
            "original_page_size_points": original_size,
            "model_predicted_correction_ccw_degrees": source_page["classifier_predicted_correction_ccw_degrees"],
            "normalized_pdf_top_left_to_original_pdf_top_left_3x3": point_matrix,
            "matrix_derivation": "Classifier normalized-raster to original-PDF matrix composed with 3 pixels per normalized-PDF point",
            "coordinate_uncertainty": "Raster/render resampling and provider bounding-box uncertainty remain; no new pixel-IoU tolerance",
            "body_ordered_refs": document["body"]["children"],
            "furniture_ordered_refs": document["furniture"]["children"], "items": items}
        save(folder / "mapped-review.json", review)
        completed.append({"job": job["name"], "original_page": source_page["original_physical_page_1based"],
            "raw_derivative_document_equivalent_to_export": True, "mapped_items": len(items),
            "matrix_page_corner_check": True, "cpu_only": True})
    save(HERE / "verification.json", {"original_registry_and_92_baseline_files_unchanged": True,
        "frozen_derived_inputs_unchanged": True, "completed_jobs": completed,
        "semantic_score": "Independent evaluator; no pass verdict here"})
    print(json.dumps({"validated_jobs": len(completed), "mapped_reviews_written": len(completed)}))


if __name__ == "__main__":
    main()
