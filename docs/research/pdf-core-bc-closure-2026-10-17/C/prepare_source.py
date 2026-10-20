"""Render only the predeclared 55 source pages for a visual C census."""
import hashlib
import json
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
SCOPE = {
    "SRC01": list(range(1, 29)), "SRC11": [2, 3, 4],
    "SRC10": [24, 51, 63, 64], "SRC06": [8], "SRC07": [8],
    "SRC09": [17], "SRC08": [27, 28, 29], "SRC03": [3],
    "SRC02": [1], "SRC04": [1, 2], "SRC12": [2],
    "SRC13": [9], "SRC05": list(range(1, 9)),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    sources = json.loads(Path("docs/fixtures/pdf-core-g1-2026-10-14/cases.json").read_text())["sources"]
    sources = {s["id"]: s for s in sources}
    assert sum(map(len, SCOPE.values())) == 55
    pages = []
    (ROOT / "pages").mkdir(exist_ok=True)
    (ROOT / "sheets").mkdir(exist_ok=True)
    for sid, nums in SCOPE.items():
        source = sources[sid]
        assert sha(source["path"]) == source["sha256"], sid
        pdf = pdfium.PdfDocument(source["path"])
        for n in nums:
            page = pdf[n - 1]
            im = page.render(scale=1.5).to_pil().convert("RGB")
            path = ROOT / "pages" / f"{sid}-p{n:02}.png"
            im.save(path)
            textpage = page.get_textpage()
            (path.with_suffix(".txt")).write_text(textpage.get_text_range())
            pages.append({"page_id": f"{sid}-p{n:02}", "source_id": sid,
                          "physical_page_1based": n, "source_pdf": source["path"],
                          "source_sha256": source["sha256"],
                          "page_size_points": list(page.get_size()),
                          "render_scale": 1.5, "image": str(path.relative_to(ROOT)),
                          "image_sha256": sha(path), "pixels": list(im.size),
                          "review_status": "pending", "figures": []})
            textpage.close()
            page.close()
        pdf.close()
    for start in range(0, len(pages), 4):
        sheet = Image.new("RGB", (1000, 1450), "#ddd")
        draw = ImageDraw.Draw(sheet)
        for j, row in enumerate(pages[start:start + 4]):
            im = Image.open(ROOT / row["image"])
            im.thumbnail((490, 690))
            x, y = (j % 2) * 500, (j // 2) * 725
            draw.text((x + 10, y + 3), row["page_id"], fill="black")
            sheet.paste(im, (x + (500 - im.width) // 2, y + 25))
            row["contact_sheet"] = f"sheets/sheet-{start // 4 + 1:02}.png"
        sheet.save(ROOT / "sheets" / f"sheet-{start // 4 + 1:02}.png")
    assert len({(p["source_sha256"], p["physical_page_1based"]) for p in pages}) == 55
    (ROOT / "source-pages.json").write_text(json.dumps(pages, indent=2) + "\n")
    print(json.dumps({"pages": len(pages), "sources": len(SCOPE), "sheets": 14, "model_calls": 0}))


if __name__ == "__main__":
    main()
