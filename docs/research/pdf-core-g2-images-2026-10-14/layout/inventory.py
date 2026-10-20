"""Render actual stock PictureItem boxes; compare source coverage without changing them."""
import hashlib
import json
from pathlib import Path

import pypdfium2 as pdfium
from docling_core.types.doc import DoclingDocument

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
registry = json.loads((REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json").read_text())
sources = {s["id"]: s for s in registry["sources"]}
jobs = [("wikiskill-p4", "SRC01", HERE / "runs/wikiskill-p4/document.json"),
        ("controls-p2", "SRC05", HERE / "runs/controls-p2/document.json"),
        ("nccu-p3", "SRC03", REPO / "docs/research/pdf-core-g2-local-cpu-2026-10-14/runs/nccu-p3-native/document.json")]
out = HERE / "crops"
out.mkdir(exist_ok=True)
inputs, records = [], []
for job, source_id, doc_path in jobs:
    source = sources[source_id]
    pdf_path = REPO / source["path"]
    assert hashlib.sha256(pdf_path.read_bytes()).hexdigest() == source["sha256"]
    document = DoclingDocument.model_validate_json(doc_path.read_text())
    with pdfium.PdfDocument(pdf_path) as pdf:
        for i, picture in enumerate(document.pictures):
            assert len(picture.prov) == 1
            prov = picture.prov[0]
            size = document.pages[prov.page_no].size
            box = prov.bbox.to_top_left_origin(page_height=size.height)
            coords = [box.l, box.t, box.r, box.b]
            assert 0 <= box.l < box.r <= size.width and 0 <= box.t < box.b <= size.height
            image = pdf[prov.page_no - 1].render(scale=3).to_pil().convert("RGB")
            pixel_box = [round(v * 3) for v in coords]
            image = image.crop(pixel_box)
            path = out / f"{job}-{i}.png"
            image.save(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            input_id = f"native-{job}-picture{i}"
            record = {"input_id": input_id, "path": str(path.relative_to(REPO)), "sha256": digest,
                      "pixels": list(image.size), "source_id": source_id, "source_pdf": source["path"],
                      "source_sha256": source["sha256"], "physical_page": prov.page_no,
                      "picture_ref": picture.self_ref, "bbox_top_left_pdf_points": coords,
                      "render_scale": 3, "rounded_fullpage_pixel_crop": pixel_box,
                      "page_size_points": size.model_dump(), "area_fraction": box.area() / (size.width * size.height),
                      "provider_document": str(doc_path.relative_to(REPO)),
                      "provider_document_sha256": hashlib.sha256(doc_path.read_bytes()).hexdigest(),
                      "scope": "Actual unmodified layout bbox, PDF rerendered3x; not baseline cached crop pixels or complete required-content coverage"}
            records.append(record)
            inputs.append({k: record[k] for k in ["input_id", "path", "sha256", "pixels"]})
(HERE / "native-inputs.json").write_text(json.dumps({"inputs": inputs}, indent=2) + "\n")
(HERE / "native-inventory.json").write_text(json.dumps({"pictures": records}, indent=2) + "\n")
assert len(inputs) == 6
print(json.dumps({"actual_picture_items": len(inputs), "sources": 3, "new_baseline_pages": 2, "reused_baseline_pages": 1}))
