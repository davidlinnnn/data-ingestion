"""Build a clearly derived raster PDF from saved classifier-corrected images."""

import hashlib
import json
from pathlib import Path

from PIL import Image
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ORIENTATION = HERE.parent / "orientation"
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert sha(REGISTRY) == "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
    source = next(s for s in json.loads(REGISTRY.read_text())["sources"] if s["id"] == "SRC05")
    assert sha(REPO / source["path"]) == source["sha256"]
    inputs = HERE / "inputs"
    inputs.mkdir(exist_ok=False)
    pdf = inputs / "derived-normalized-controls.pdf"
    producer = canvas.Canvas(str(pdf), pagesize=(612, 792), invariant=1, pageCompression=1)
    producer.setTitle("DERIVED classifier-normalized raster controls; not original SRC05 bytes")
    producer.setAuthor("G2 bounded CPU integration diagnostic")
    producer.showPage()
    producer.showPage()
    records = []
    for page in range(3, 7):
        folder = ORIENTATION / "runs" / f"p{page}"
        image = folder / "normalized.png"
        mapping = json.loads((folder / "source-mapping.json").read_text())
        orientation = json.loads((folder / "orientation.json").read_text())
        with Image.open(image) as raster:
            assert raster.size == (1836, 2376)
        assert mapping["physical_page_1based"] == page
        assert mapping["source_sha256"] == source["sha256"]
        assert mapping["model_predicted_corrective_ccw_degrees"] == orientation["correction_ccw_degrees"]
        producer.drawImage(str(image), 0, 0, width=612, height=792)
        producer.showPage()
        records.append({"derived_physical_page_1based": page,
            "original_physical_page_1based": page,
            "normalized_image_path": str(image.relative_to(REPO)), "normalized_image_sha256": sha(image),
            "orientation_result_path": str((folder / "orientation.json").relative_to(REPO)),
            "orientation_result_sha256": sha(folder / "orientation.json"),
            "source_mapping_path": str((folder / "source-mapping.json").relative_to(REPO)),
            "source_mapping_sha256": sha(folder / "source-mapping.json"),
            "classifier_predicted_correction_ccw_degrees": orientation["correction_ccw_degrees"],
            "derived_pdf_top_left_to_normalized_raster": [[3, 0, 0], [0, 3, 0], [0, 0, 1]],
            "classifier_source_mapping": mapping})
    producer.save()
    manifest = {"format": "g2-classifier-normalized-derived-source-v1",
        "identity": "DERIVED-NORMALIZED-CONTROLS",
        "scope": "Derived raster PDF integration probe, not frozen G1 source bytes or a production adapter",
        "compatibility_alias": "sources[0].id=SRC05 is only the unchanged baseline worker lookup key in this local manifest",
        "original_registry_path": str(REGISTRY.relative_to(REPO)), "original_registry_sha256": sha(REGISTRY),
        "original_source": source,
        "sources": [{"id": "SRC05", "derived_source_id": "DERIVED-NORMALIZED-CONTROLS",
            "path": str(pdf.relative_to(REPO)), "sha256": sha(pdf), "pages": 6,
            "page_size_points": [612, 792], "not_original_source_bytes": True}],
        "blank_pages": [1, 2],
        "blank_page_reason": "Retain derivative page numbers 3-6 for reuse of unchanged worker observation hooks",
        "derivation": "Lossless saved classifier-normalized RGB PNGs placed full-bleed at 612x792 PDF points; no text layer",
        "derivation_inputs": "Classifier predictions and saved transforms only; no oracle text, expected angles or region crops",
        "pages": records}
    (HERE / "input-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"derived_pdf": str(pdf), "sha256": sha(pdf), "pages": 6}))


if __name__ == "__main__":
    main()
