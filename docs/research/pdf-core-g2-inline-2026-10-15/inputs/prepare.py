"""Select ordinary paragraphs from complete provider documents, then render their provenance."""

import hashlib
import json
import math
from pathlib import Path
import shutil
import unicodedata

from PIL import Image
import pypdfium2 as pdfium

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
REGISTRY_SHA = "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
SOURCES = [
    ("wikiskill", "SRC01", [21], "docs/research/pdf-core-g2-heading-2026-10-15/inputs/wikiskill"),
    ("dgm", "SRC10", [51], "docs/research/paper-pdf-dgm-durable-q10-2026-10-11/runtime/E/export/assembly"),
    ("seal", "SRC11", [3, 4], "docs/research/paper-pdf-functional-2026-10-11/remaining-group5/17-2506.10943v1/native"),
    ("controls", "SRC05", [1], "docs/research/pdf-core-g2-heading-2026-10-15/inputs/controls/runs/controls-p1"),
]
SCALE, PADDING_POINTS, STITCH_GAP = 3, 2, 24


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def gate_characters(text):
    return sorted(set(c for c in text if unicodedata.category(c) == "Sm"
        or "\u0370" <= c <= "\u03ff" or "\U0001d400" <= c <= "\U0001d7ff" or c in "_=<>^{}"))


def main():
    assert sha(REGISTRY) == REGISTRY_SHA
    registry = json.loads(REGISTRY.read_text())
    (HERE / "candidates").mkdir(exist_ok=False)
    (HERE / "baselines").mkdir()
    (HERE / "pages").mkdir()
    manifest = {"format": "g2-inline-producer-paragraph-input-v1", "registry_sha256": REGISTRY_SHA,
        "selection": "All ordinary body text items intersecting selected physical pages are inventoried; primary inference gate uses only producer text characters",
        "gate": "Unicode Sm, Greek block, mathematical alphanumeric block, or ASCII _ = < > ^ { }; all controls formula/code items are regression jobs",
        "oracle_content_or_boxes_used_for_selection": False,
        "render_scale": SCALE, "padding_points": PADDING_POINTS, "stitch_gap_pixels": STITCH_GAP,
        "coordinate_policy": "Direct PDFium 3x RGB render, outward integer pixel crop; mappings are render-derived and do not claim glyph-measured localization",
        "sources": [], "ordinary_paragraph_inventory": [], "candidates": []}
    for name, source_id, selected_pages, old_folder in SOURCES:
        source = next(s for s in registry["sources"] if s["id"] == source_id)
        pdf_path = REPO / source["path"]
        assert sha(pdf_path) == source["sha256"]
        old = REPO / old_folder
        baseline = HERE / "baselines" / name
        baseline.mkdir()
        snapshots = []
        for filename in ("document.json", "method.json", "metrics.json"):
            target = baseline / filename
            shutil.copyfile(old / filename, target)
            assert sha(target) == sha(old / filename)
            snapshots.append({"original_path": str((old / filename).relative_to(REPO)),
                "path": str(target.relative_to(REPO)), "sha256": sha(target)})
        document = json.loads((baseline / "document.json").read_text())
        metrics = json.loads((baseline / "metrics.json").read_text())
        assert metrics["source_sha256"] == source["sha256"]
        assert document["origin"]["filename"] == pdf_path.name
        text_items = {t["self_ref"]: t for t in document["texts"]}
        selected = []
        for item in document["texts"]:
            intersects = any(p["page_no"] in selected_pages for p in item["prov"])
            ordinary = item["label"] == "text" and item["content_layer"] == "body"
            signals = gate_characters(item.get("text", ""))
            regression = name == "controls" and item["label"] in {"formula", "code"}
            if intersects and ordinary:
                manifest["ordinary_paragraph_inventory"].append({"source": name, "item_ref": item["self_ref"],
                    "provider_text": item["text"], "provider_provenance": item["prov"],
                    "gate_characters": signals, "selected_by_gate": bool(signals),
                    "document_path": str((baseline / "document.json").relative_to(REPO))})
            if intersects and ((ordinary and signals) or regression):
                selected.append(item)
        assert selected
        source_record = {"name": name, "source": source, "selected_physical_pages": selected_pages,
            "document_path": str((baseline / "document.json").relative_to(REPO)),
            "document_sha256": sha(baseline / "document.json"), "complete_document_pages": sorted(map(int, document["pages"])),
            "baseline_mode": metrics["mode"], "baseline_is_complete_source_document": name != "controls",
            "baseline_original_method": json.loads((baseline / "method.json").read_text()).get("continuation"),
            "snapshots": snapshots, "full_page_renders": []}
        needed_pages = sorted(set(selected_pages) | {p["page_no"] for t in selected for p in t["prov"]})
        rendered = {}
        pdf = pdfium.PdfDocument(pdf_path)
        try:
            for page_no in needed_pages:
                page = pdf[page_no - 1]
                bitmap = page.render(scale=SCALE)
                image = bitmap.to_pil().convert("RGB")
                bitmap.close()
                path = HERE / "pages" / f"{name}-p{page_no}.png"
                image.save(path)
                rendered[page_no] = image
                source_record["full_page_renders"].append({"physical_page_1based": page_no,
                    "path": str(path.relative_to(REPO)), "sha256": sha(path), "pixels_wh": list(image.size),
                    "page_size_points": list(page.get_size()), "scale_pixels_per_point": SCALE})
                page.close()
        finally:
            pdf.close()
        for item in selected:
            candidate_id = name + "-" + item["self_ref"].replace("#/", "").replace("/", "-")
            folder = HERE / "candidates" / candidate_id
            folder.mkdir()
            spans = sorted((p["charspan"] for p in item["prov"]))
            cursor = 0
            for start, end in spans:
                assert start >= cursor and 0 <= start <= end <= len(item["text"])
                assert not item["text"][cursor:start].strip(), "Provider fragments leave non-whitespace text unlocated"
                cursor = end
            assert not item["text"][cursor:].strip()
            fragments, crops, yoffset = [], [], 0
            for index, provenance in enumerate(sorted(item["prov"], key=lambda p: p["charspan"])):
                page_no = provenance["page_no"]
                page_size = document["pages"][str(page_no)]["size"]
                box = provenance["bbox"]
                top, bottom = ((box["t"], box["b"]) if box["coord_origin"] == "TOPLEFT"
                               else (page_size["height"]-box["t"], page_size["height"]-box["b"]))
                image = rendered[page_no]
                pixel_box = [max(0, math.floor((box["l"]-PADDING_POINTS)*SCALE)),
                    max(0, math.floor((top-PADDING_POINTS)*SCALE)),
                    min(image.width, math.ceil((box["r"]+PADDING_POINTS)*SCALE)),
                    min(image.height, math.ceil((bottom+PADDING_POINTS)*SCALE))]
                assert pixel_box[2] > pixel_box[0] and pixel_box[3] > pixel_box[1]
                crop = image.crop(pixel_box)
                path = folder / f"fragment-{index}.png"
                crop.save(path)
                fragments.append({"fragment_index": index, "physical_page_1based": page_no,
                    "provider_provenance": provenance, "source_page_size_points": page_size,
                    "provider_bbox_top_left_points": [box["l"], top, box["r"], bottom],
                    "render_crop_pixel_box": pixel_box, "fragment_pixels_wh": list(crop.size),
                    "fragment_image_path": str(path.relative_to(REPO)), "fragment_image_sha256": sha(path),
                    "paragraph_canvas_xywh": [0, yoffset, crop.width, crop.height],
                    "paragraph_pixels_to_source_top_left_points_3x3":
                        [[1/SCALE, 0, pixel_box[0]/SCALE], [0, 1/SCALE, (pixel_box[1]-yoffset)/SCALE], [0, 0, 1]]})
                crops.append(crop)
                yoffset += crop.height + STITCH_GAP
            paragraph = Image.new("RGB", (max(c.width for c in crops), yoffset-STITCH_GAP), "white")
            for crop, fragment in zip(crops, fragments, strict=True):
                paragraph.paste(crop, tuple(fragment["paragraph_canvas_xywh"][:2]))
            paragraph_path = folder / "paragraph.png"
            paragraph.save(paragraph_path)
            row = {"id": candidate_id, "source": name, "source_id": source_id,
                "source_pdf_path": source["path"], "source_pdf_sha256": source["sha256"],
                "baseline_document_path": source_record["document_path"],
                "baseline_document_sha256": source_record["document_sha256"],
                "item_ref": item["self_ref"], "provider_label": item["label"],
                "replacement_charspan": [0, len(item["text"])], "provider_text": item["text"],
                "provider_text_sha256": hashlib.sha256(item["text"].encode()).hexdigest(),
                "selection_reason": "controls_formula_code_label_regression" if item["label"] != "text" else "ordinary_body_text_character_gate",
                "gate_characters": gate_characters(item["text"]), "fragments": fragments,
                "image_path": str(paragraph_path.relative_to(REPO)), "image_sha256": sha(paragraph_path),
                "image_pixels_wh": list(paragraph.size), "render_scale": SCALE,
                "paragraph_fragment_order": "Provider charspan order; 24px white separator; no oracle labels added"}
            save(folder / "candidate.json", row)
            manifest["candidates"].append(row)
        manifest["sources"].append(source_record)
    manifest["counts"] = {"ordinary_paragraphs_inventoried": len(manifest["ordinary_paragraph_inventory"]),
        "ordinary_selected_by_character_gate": sum(r["selected_by_gate"] for r in manifest["ordinary_paragraph_inventory"]),
        "inference_candidates_including_controls_regression": len(manifest["candidates"]),
        "candidate_page_fragments": sum(len(c["fragments"]) for c in manifest["candidates"])}
    assert manifest["counts"]["ordinary_paragraphs_inventoried"] == 28
    assert manifest["counts"]["inference_candidates_including_controls_regression"] == 17
    save(HERE / "input-manifest.json", manifest)
    assert sha(REGISTRY) == REGISTRY_SHA
    print(json.dumps(manifest["counts"]))


if __name__ == "__main__":
    main()
