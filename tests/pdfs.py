"""Synthetic PDFs for tests: a tiny writer, so fixtures need no third-party documents."""

import io
import zlib
from dataclasses import dataclass, field

from pypdf import PdfReader, PdfWriter


@dataclass
class Page:
    lines: list[str] = field(default_factory=list)  # body text, one Tj per line
    picture: bool = False  # a 200x150 pt raster block under the text
    size: tuple[float, float] = (612, 792)  # points


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


def write_pdf(pages: list[Page]) -> bytes:
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    pages_id = len(objects) + 1 + 2 * len(pages) + sum(p.picture for p in pages)
    for page in pages:
        width, height = page.size
        ops = []
        resources = f"/Font << /F1 {font} 0 R >>"
        if page.picture:
            w, h = 64, 48
            pixels = b"".join(bytes(((x * 4) % 256, (y * 5) % 256, ((x + y) * 3) % 256))
                              for y in range(h) for x in range(w))  # fmt: skip
            data = zlib.compress(pixels)
            image = add(
                f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB "
                f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(data)} >>\n"
                f"stream\n".encode()
                + data
                + b"\nendstream"
            )
            resources += f" /XObject << /Im1 {image} 0 R >>"
            ops.append(f"q 200 0 0 150 72 {height - 400} cm /Im1 Do Q")
        y = height - 72
        for i, line in enumerate(page.lines):
            size = 16 if i == 0 else 11
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"BT /F1 {size} Tf 72 {y} Td ({escaped}) Tj ET")
            y -= 24 if i == 0 else 16
            if page.picture and i == 0:
                y -= 180
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
