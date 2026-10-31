"""Synthetic PDFs for tests: a tiny writer, so fixtures need no third-party documents."""

import io
import zlib
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter


@dataclass
class Page:
    lines: list[str] = field(default_factory=list)  # body text, one Tj per line
    picture: bool = False  # a 200x150 pt raster block under the text
    size: tuple[float, float] = (612, 792)  # points
    picture_text: list[str] = field(default_factory=list)  # words drawn into the raster block
    code: list[str] = field(default_factory=list)  # a Courier listing below the text
    table: list[list[str]] = field(default_factory=list)  # rows of cells, ruled, below the code


def paper(pages: int, picture_on: tuple[int, ...] = ()) -> list[Page]:
    """`pages` text pages, each with a heading and a paragraph; a picture on the given
    1-based pages."""
    return [
        Page(
            lines=[f"Section {n}", *(f"Line {i} of page {n} says something about topic {n}."
                                     for i in range(1, 12))],
            picture=n in picture_on,
        )
        for n in range(1, pages + 1)
    ]  # fmt: skip


def picture_pixels(words: list[str]) -> tuple[int, int, bytes]:
    """RGB pixels of the raster block: a gradient, or the words in boxes on white."""
    if not words:
        w, h = 64, 48
        return w, h, b"".join(bytes(((x * 4) % 256, (y * 5) % 256, ((x + y) * 3) % 256))
                              for y in range(h) for x in range(w))  # fmt: skip
    image = Image.new("RGB", (800, 600), (225, 235, 245))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=40)
    for i, word in enumerate(words):
        x, y = 40 + (i % 2) * 390, 40 + (i // 2) * 180
        draw.rectangle([x, y, x + 350, y + 120], outline="black", width=4)
        draw.text((x + 20, y + 35), word, fill="black", font=font)
    return image.width, image.height, image.tobytes()


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(pages: list[Page]) -> bytes:
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    mono = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    page_ids = []
    pages_id = len(objects) + 1 + 2 * len(pages) + sum(p.picture for p in pages)
    for page in pages:
        width, height = page.size
        ops = []
        resources = f"/Font << /F1 {font} 0 R /F2 {mono} 0 R >>"
        if page.picture:
            w, h, pixels = picture_pixels(page.picture_text)
            data = zlib.compress(pixels)
            image = add(
                f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
                f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(data)} >>\n"
                f"stream\n".encode()
                + data
                + b"\nendstream"
            )
            resources += f" /XObject << /Im1 {image} 0 R >>"
            ops.append(f"q 200 0 0 150 72 {height - 276} cm /Im1 Do Q")  # under the heading
        y = height - 72
        for i, line in enumerate(page.lines):
            size = 16 if i == 0 else 11
            ops.append(f"BT /F1 {size} Tf 72 {y} Td ({_escape(line)}) Tj ET")
            y -= 24 if i == 0 else 16
            if page.picture and i == 0:
                y -= 200
        y -= 10
        for line in page.code:
            # Indentation is an x offset, as LaTeX listings typeset it: no leading spaces.
            indent = 6 * (len(line) - len(line.lstrip(" ")))  # Courier 10 pt advances 6 pt
            ops.append(f"BT /F2 10 Tf {90 + indent} {y} Td ({_escape(line.lstrip(' '))}) Tj ET")
            y -= 13
        if page.table:
            y -= 30
            columns = [150 + 90 * c for c in range(len(page.table[0]) + 1)]
            for r, row in enumerate(page.table):
                for c, cell in enumerate(row):
                    ops.append(f"BT /F1 10 Tf {columns[c] + 6} {y - (r + 1) * 18 + 5} Td "
                               f"({_escape(cell)}) Tj ET")  # fmt: skip
            for r in (0, 1, len(page.table)):
                ops.append(f"{columns[0]} {y - r * 18} m {columns[-1]} {y - r * 18} l S")
        stream = "\n".join(ops).encode()
        content = add(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
        page_ids.append(
            add(
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {width} {height}] "
                f"/Resources << {resources} >> /Contents {content} 0 R >>".encode()
            )
        )
    kids = " ".join(f"{i} 0 R" for i in page_ids)
    assert add(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode()) == pages_id
    catalog = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())

    out = io.BytesIO()
    out.write(b"%PDF-1.7\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\n".encode())
    out.write(f"startxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def encrypt(pdf: bytes, password: str = "secret") -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    writer.encrypt(user_password=password, owner_password=password, algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
