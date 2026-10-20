"""Check saved evidence without importing or executing a model."""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    summary = json.loads((HERE / "summary.json").read_text())
    manifest = json.loads((HERE / "input-manifest.json").read_text())
    assert summary["runner_sha256"] == sha(HERE / "run.py")
    assert summary["method_sha256"] == sha(HERE / "method.json")
    assert summary["registry_sha256"] == sha(REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json")
    assert len(summary["jobs"]) == 4
    results = []
    normalized_hashes, texts = set(), []
    for job, item in zip(summary["jobs"], manifest["pages"]):
        number = job["physical_page_1based"]
        assert number == item["physical_page_1based"]
        assert job["status"] == "completed" and job["stopped"] is None and job["exit_code"] == 0
        assert job["available_before_bytes"] >= 8 * 1024**3
        assert job["sampled_tree_peak_rss_bytes"] <= 6 * 1024**3
        assert job["wall_seconds_including_process_start_exit"] < 180
        folder = HERE / "runs" / f"p{number}"
        ori = json.loads((folder / "orientation.json").read_text())
        ocr = json.loads((folder / "ocr.json").read_text())
        raw = json.loads((folder / "raw-ocr-stages.json").read_text())
        runtime = json.loads((folder / "runtime.json").read_text())
        mapping = json.loads((folder / "source-mapping.json").read_text())
        assert ori["providers"] == ["CPUExecutionProvider"]
        assert all(s["providers"] == ["CPUExecutionProvider"] for s in runtime["sessions"].values())
        assert all(s["threads_intra_inter"] == [4, 1] for s in runtime["sessions"].values())
        assert runtime["dictionary"]["embedded_sha256"] == sha(folder / "recognizer-embedded-dictionary.txt")
        assert runtime["dictionary"]["decoder_sha256"] == sha(folder / "recognizer-decoder-dictionary.json")
        assert sha(REPO / item["path"]) == item["sha256"] == runtime["source_render_sha256"]
        source = np.array(Image.open(REPO / item["path"]))
        normalized = np.array(Image.open(folder / "normalized.png"))
        angle = ori["correction_ccw_degrees"]
        assert np.array_equal(np.rot90(source, angle // 90), normalized)
        forward = np.array(mapping["source_raster_to_normalized_raster_3x3"])
        inverse = np.array(mapping["normalized_raster_to_source_raster_3x3"])
        assert np.allclose(forward @ inverse, np.eye(3))
        for row in ocr["source_mapped_boxes"] + raw["source_mapped_boxes"]:
            assert row["original_physical_page_1based"] == number
            polygon = np.array(row["normalized_polygon_pixels"])
            expected = (inverse @ np.column_stack([polygon, np.ones(len(polygon))]).T).T[:, :2] / 3
            assert np.allclose(expected, row["original_source_polygon_pdf_points_top_left"])
            assert np.allclose([*expected.min(axis=0), *expected.max(axis=0)], row["original_source_bbox_pdf_points_top_left"])
        assert np.array_equal(np.load(folder / "orientation-output.npy", allow_pickle=False), ori["raw_outputs"][0])
        tensor = np.load(folder / "orientation-input.npy", allow_pickle=False)
        assert hashlib.sha256(tensor.tobytes()).hexdigest() == ori["preprocess"]["tensor_sha256"]
        normalized_hashes.add(sha(folder / "normalized.png"))
        texts.append(ocr["texts"])
        results.append({"physical_page_1based": number, "model_corrective_ccw_degrees": angle,
                        "saved_boxes_checked": len(ocr["source_mapped_boxes"]) + len(raw["source_mapped_boxes"]),
                        "all_evidence_checks": "passed"})
    assert len(normalized_hashes) == 1 and all(t == texts[0] for t in texts)
    output = {"check": "Saved evidence integrity, CPU providers, transforms, exact image permutation and guards; no semantic oracle scoring",
              "source_render_scale": 3, "normalized_image_hashes": sorted(normalized_hashes),
              "all_four_ocr_text_outputs_identical": True, "results": results}
    (HERE / "verification.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
