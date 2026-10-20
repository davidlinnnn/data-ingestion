"""Freeze source-only validation fixtures before any candidate output is produced."""
import hashlib
import json
from pathlib import Path
import re

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "validation"
SOURCES = {
    "bert": "https://aclanthology.org/N19-1423.pdf",
    "resnet": "https://openaccess.thecvf.com/content_cvpr_2016/papers/He_Deep_Residual_Learning_CVPR_2016_paper.pdf",
    "attention": "https://papers.nips.cc/paper_files/paper/2017/file/3f5ee243547dee91fbd053c1c4a845aa-Paper.pdf",
}
# Source-page annotation only. No coordinate below is passed to an OCR model.
# Tuples partition page bands: role, column, (left, top, right, bottom).
PAGES = {
    "bert-p1": [
        ("title_authors", "fullwidth", [0, 0, 596, 210]),
        ("paragraph", "left", [0, 210, 298, 552]),
        ("heading", "left", [0, 552, 298, 574]),
        ("paragraph", "left", [0, 574, 298, 780]),
        ("paragraph", "right", [298, 210, 596, 435]),
        ("paragraph", "right", [298, 435, 596, 632]),
        ("paragraph", "right", [298, 632, 596, 780]),
        ("footer", "fullwidth", [0, 780, 596, 842]),
    ],
    "bert-p2": [
        ("paragraph", "left", [0, 0, 298, 480]),
        ("heading", "left", [0, 480, 298, 510]),
        ("paragraph", "left", [0, 510, 298, 558]),
        ("heading", "left", [0, 558, 298, 580]),
        ("paragraph", "left", [0, 580, 298, 780]),
        ("paragraph", "right", [298, 0, 596, 525]),
        ("heading", "right", [298, 525, 596, 545]),
        ("paragraph", "right", [298, 545, 596, 780]),
        ("footer", "fullwidth", [0, 780, 596, 842]),
    ],
    "resnet-p1": [
        ("header", "fullwidth", [0, 0, 612, 60]),
        ("title_authors", "fullwidth", [0, 60, 612, 215]),
        ("heading", "left", [0, 215, 298, 245]),
        ("paragraph", "left", [0, 245, 298, 530]),
        ("heading", "left", [0, 530, 298, 550]),
        ("paragraph", "left", [0, 550, 298, 725]),
        ("figure", "right", [298, 215, 612, 303]),
        ("caption", "right", [298, 303, 612, 340]),
        ("paragraph", "right", [298, 340, 612, 725]),
        ("footer", "fullwidth", [0, 725, 612, 792]),
    ],
    "resnet-p2": [
        ("figure", "left", [0, 0, 298, 158]),
        ("caption", "left", [0, 158, 298, 180]),
        ("paragraph", "left", [0, 180, 298, 725]),
        ("paragraph", "right", [298, 0, 612, 190]),
        ("heading", "right", [298, 190, 612, 212]),
        ("paragraph", "right", [298, 212, 612, 460]),
        ("paragraph", "right", [298, 460, 612, 600]),
        ("paragraph", "right", [298, 600, 612, 725]),
        ("footer", "fullwidth", [0, 725, 612, 792]),
    ],
    "attention-p2": [
        ("paragraph", "single", [0, 0, 612, 270]),
        ("heading", "single", [0, 270, 612, 300]),
        ("paragraph", "single", [0, 300, 612, 545]),
        ("heading", "single", [0, 545, 612, 570]),
        ("paragraph", "single", [0, 570, 612, 675]),
        ("heading", "single", [0, 675, 612, 695]),
        ("paragraph", "single", [0, 695, 612, 735]),
        ("footer", "fullwidth", [0, 735, 612, 792]),
    ],
    "attention-p3": [
        ("figure", "fullwidth", [0, 0, 612, 400]),
        ("caption", "single", [0, 400, 612, 430]),
        ("paragraph", "single", [0, 430, 612, 510]),
        ("paragraph", "single", [0, 510, 612, 600]),
        ("heading", "single", [0, 600, 612, 620]),
        ("paragraph", "single", [0, 620, 612, 675]),
        ("heading", "single", [0, 675, 612, 695]),
        ("paragraph", "single", [0, 695, 612, 735]),
        ("footer", "fullwidth", [0, 735, 612, 792]),
    ],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not (OUT / "freeze.json").exists(), "Do not rebuild frozen validation inputs"
    assert not any((HERE / p).exists() for p in ("E-default", "E-full"))
    (OUT / "inputs").mkdir(exist_ok=True)
    refs, pages = [], []
    for pid, groups in PAGES.items():
        sid, number = pid.split("-p")
        document = pdfium.PdfDocument(OUT / "sources" / f"{sid}.pdf")
        page = document[int(number) - 1]
        w, h = page.get_size()
        textpage = page.get_textpage()
        image = page.render(scale=2).to_pil().convert("RGB")
        png = OUT / "source-pages" / f"{pid}.png"
        image.save(png)
        raster = pdfium.PdfDocument.new()
        target_page = raster.new_page(w, h)
        bitmap = pdfium.PdfBitmap.from_pil(image)
        raster_image = pdfium.PdfImage.new(raster)
        raster_image.set_bitmap(bitmap)
        raster_image.set_matrix(pdfium.PdfMatrix(w, 0, 0, h, 0, 0))
        target_page.insert_obj(raster_image)
        target_page.gen_content()
        path = OUT / "inputs" / f"{pid}.pdf"
        raster.save(path)
        check = pdfium.PdfDocument(path)
        assert check[0].get_textpage().count_chars() == 0
        assert check[0].get_size() == (w, h)
        ref = {"id": pid, "source_id": sid, "source_page": int(number), "page_size": [w, h],
               "items": [], "body_order": [], "source_lines": [], "legitimate_cross_column_items": []}
        for i, (role, column, box) in enumerate(groups, 1):
            left, top, right, bottom = box
            raw = textpage.get_text_bounded(left, h - bottom, min(w, right), h - top)
            text = re.sub(r"[\x02\ufffe]\s*", "", raw)
            text = " ".join(text.split())
            assert text or role in ("figure", "footer", "header"), (pid, i, role)
            uid = f"{pid}-U{i:02}"
            scored = role not in ("figure", "footer", "header")
            item = {"id": uid, "role": role, "column": column, "bbox": box,
                    "text": text, "native_text": raw, "scored": scored, "critical": role == "heading"}
            ref["items"].append(item)
            if scored and role != "caption":
                ref["body_order"].append(uid)
            if scored and column == "fullwidth":
                ref["legitimate_cross_column_items"].append(uid)
            for j, line in enumerate(raw.splitlines(), 1):
                if any(c.isalnum() for c in line):
                    ref["source_lines"].append({"id": f"{uid}-L{j:03}", "item_id": uid,
                        "text": line.replace("\x02", "").replace("\ufffe", ""), "bbox": box, "scored": scored})
        # Source annotations must partition every native non-space character once.
        for i in range(textpage.count_chars()):
            char = textpage.get_text_range(i, 1)
            if not char.strip():
                continue
            x0, y0, x1, y1 = textpage.get_charbox(i)
            x, y = (x0 + x1) / 2, h - (y0 + y1) / 2
            matches = [g for g in groups if g[2][0] <= x < g[2][2] and g[2][1] <= y < g[2][3]]
            assert len(matches) == 1, (pid, i, char, x, y, matches)
        refs.append(ref)
        pages.append({"id": pid, "source_id": sid, "page": int(number), "pdf": str(path.resolve()),
                      "pdf_sha256": sha(path), "source_png": str(png.resolve()), "png_sha256": sha(png)})
        (OUT / "source-pages" / f"{pid}-reference.txt").write_text("\n\n".join(
            f'{u["id"]} {u["role"]} {u["column"]}\n{u["text"]}' for u in ref["items"]))
    manifest = {"pages": pages, "sources": [{"id": k, "url": u,
        "pdf_sha256": sha(OUT / "sources" / f"{k}.pdf")} for k, u in SOURCES.items()],
        "source_visual_review": "All six pages inspected before candidate output; attention p3 adds spanning architecture figure.",
        "limits": ["Clean raster derivatives, no natural scan noise; English only.",
            "Coarse source narrative bands test column/band order; not exhaustive paragraph or formula ground truth.",
            "Figure interiors/furniture excluded from text acceptance; captions checked for coverage, not narrative placement.",
            "These source coordinates are reference annotations, never model crop/padding settings.",
            "No existing sealed holdout contents/answers read; independence means additional documents, not a benchmark claim."]}
    for name, data in (("manifest.json", manifest), ("reference.json", {"pages": refs})):
        (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    hashes = {str(p.relative_to(OUT)): sha(p) for p in sorted(OUT.rglob("*")) if p.is_file()}
    (OUT / "freeze.json").write_text(json.dumps({"frozen_before_candidate_inference": True,
        "candidate_outputs_seen": False, "files": hashes}, indent=2) + "\n")
    print("Frozen six source-only pages from three additional documents; no inference.")


if __name__ == "__main__":
    main()
