"""Render retained S0 with native Docling visualizers; never rerun parsing models."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from docling.datamodel.settings import settings
from docling.models.base_ocr_model import BaseOcrModel
from docling_core.transforms.serializer.html import HTMLDocSerializer, HTMLParams, HTMLOutputStyle
from docling_core.transforms.visualizer.layout_visualizer import LayoutVisualizer
from docling_core.transforms.visualizer.reading_order_visualizer import ReadingOrderVisualizer
from docling_core.types.doc import BoundingBox, DoclingDocument, ImageRef, ImageRefMode, Size
from docling_core.types.doc.page import TextCell

HERE = Path(__file__).resolve().parent
RETAINED = HERE.parent / "pdf-core-native-round-2026-10-17"
TRACE = HERE.parent / "pdf-core-ocr-boundary-trace-2026-10-19"
SOURCE = RETAINED / "inputs/scan-p1.png"
DOC = RETAINED / "S0/scan/document.json"
RESULT = RETAINED / "S0/scan/result.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render():
    source_paths = [SOURCE, DOC, RESULT, RETAINED / "S0/scan/document.md", TRACE / "analysis.json"]
    hashes = {str(p): sha(p) for p in source_paths}
    saved = json.loads(RESULT.read_text())
    assert saved["pages"][0]["page_no"] == 1 and len(saved["pages"]) == 1
    assert Path(saved["input"]["file"]).name == "scan-pages-3-5.pdf"
    document = DoclingDocument.load_from_json(DOC)
    assert set(document.pages) == {1}
    original = document.model_dump(mode="json")
    expected_markdown = (RETAINED / "S0/scan/document.md").read_text()
    assert document.export_to_markdown() == expected_markdown
    view = document.model_copy(deep=True)
    background = Image.open(SOURCE).convert("RGB")
    page_size = view.pages[1].size
    assert background.size == (round(page_size.width*2), round(page_size.height*2)) == (1224, 1584)
    # Presentation copy only: overlays align to the exact PNG requested by the user.
    view.pages[1].image = ImageRef.from_pil(background, dpi=144)
    assert view.export_to_markdown() == expected_markdown
    assert view.model_dump(mode="json", exclude={"pages"}) == document.model_dump(mode="json", exclude={"pages"})

    out = HERE / "output"
    out.mkdir(exist_ok=False)
    # Native labels include a synthetic 1.00, so hide them rather than imply confidence.
    layout = LayoutVisualizer(params=LayoutVisualizer.Params(show_label=False))
    layout_image = layout.get_visualization(doc=view)[1]
    layout_image.save(out / "final-layout.png")
    reading_image = view.get_visualization(show_label=False, show_branch_numbering=False)[1]
    reading_image.save(out / "reading-order.png")
    reading = ReadingOrderVisualizer(base_visualizer=layout)
    html = HTMLDocSerializer(doc=view, params=HTMLParams(
        output_style=HTMLOutputStyle.SPLIT_PAGE, image_mode=ImageRefMode.EMBEDDED,
    )).serialize(visualizer=reading).text
    assert "data:image/png;base64," in html and "foror" in html
    (out / "source-and-parsed.html").write_text(html)

    cells = [TextCell.model_validate(c) for c in saved["pages"][0]["parsed_page"]["textline_cells"]]
    rects = [BoundingBox.model_validate(v) for v in json.loads((TRACE / "analysis.json").read_text())["dedup"]["20"]["rects"]]
    previous = settings.debug.debug_output_path
    try:
        settings.debug.debug_output_path = out
        BaseOcrModel.draw_ocr_rects_and_cells(None,
            SimpleNamespace(input=SimpleNamespace(file=SOURCE)),
            SimpleNamespace(image=background, size=Size(width=612, height=792), cells=cells, page_no=1),
            rects, show=False)
    finally:
        settings.debug.debug_output_path = previous

    assert document.model_dump(mode="json") == original
    assert all(sha(p) == digest for p, digest in hashes.items())
    outputs = {str(p.relative_to(out)): {"sha256": sha(p), "bytes": p.stat().st_size}
               for p in sorted(out.rglob("*")) if p.is_file()}
    for relative in outputs:
        if relative.endswith(".png"):
            with Image.open(out / relative) as image:
                assert image.size == background.size
                image.verify()
    manifest = {"input_hashes": hashes, "outputs": outputs, "parsed_profile": "retained S0 StandardPdfPipeline",
        "visualization_background": str(SOURCE), "page_no": 1, "new_model_inferences": 0,
        "presentation_only_image_replacement": True, "parsed_text_and_geometry_changed": False,
        "note": "Final layout boxes are DocItem provenance, not raw Heron proposals; arrows show saved document order, not ground truth.",
        "official_api": "https://docling-project.github.io/docling/reference/docling_document/#docling_core.types.doc.document.DoclingDocument.get_visualization"}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"output": str(out), "files": list(outputs), "new_model_inferences": 0}))


if __name__ == "__main__":
    render()
