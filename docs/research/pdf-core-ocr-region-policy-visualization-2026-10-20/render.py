"""Present sealed final documents using native Docling renderers; zero inference."""
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image
from docling_core.transforms.serializer.html import HTMLDocSerializer, HTMLParams, HTMLOutputStyle
from docling_core.transforms.visualizer.layout_visualizer import LayoutVisualizer
from docling_core.transforms.visualizer.reading_order_visualizer import ReadingOrderVisualizer
from docling_core.types.doc import DoclingDocument, ImageRef, ImageRefMode

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "pdf-core-ocr-regression-2026-10-19"
POLICY = ROOT / "pdf-core-ocr-region-policy-2026-10-20"
OFFICIAL = ROOT / "pdf-core-ocr-official-options-2026-10-19"
OUT = ROOT / "pdf-core-native-visualization-2026-10-19/output/region-policies"
RESPONSIVE = "<style>body{margin:0}html{background:white;font-size:14px}.page{box-sizing:border-box;max-width:100%;width:auto;margin:0;padding:12px}img{min-width:0!important;max-width:100%!important}</style>"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render():
    jobs = json.loads((POLICY / "registration.json").read_text())["jobs"]
    profiles = {"C0": POLICY / "C0", "C10": POLICY / "C10", "R0": BASE / "R0", "FULL": OFFICIAL / "full"}
    hashes, entries = {}, []
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(HERE / "index.html", OUT / "index.html")
    for job in jobs:
        key = job["id"]
        source = ROOT / "pdf-core-native-round-2026-10-17/inputs/scan-p1.png" if key == "known" else BASE / f"corpus/source-pages/{key}.png"
        hashes[str(source)] = sha(source)
        shutil.copyfile(source, OUT / f"source-{key}.png")
        for name, folder in profiles.items():
            path = folder / key / "document.json"
            markdown = folder / key / "document.md"
            hashes[str(path)], hashes[str(markdown)] = sha(path), sha(markdown)
            document = DoclingDocument.load_from_json(path)
            assert set(document.pages) == {1}
            original = document.model_dump(mode="json")
            expected = markdown.read_text()
            assert document.export_to_markdown() == expected
            view = document.model_copy(deep=True)
            with Image.open(source) as image:
                background = image.convert("RGB")
            size = view.pages[1].size
            assert background.size == (round(size.width * 2), round(size.height * 2))
            view.pages[1].image = ImageRef.from_pil(background, dpi=144)
            assert view.model_dump(mode="json", exclude={"pages"}) == document.model_dump(mode="json", exclude={"pages"})
            assert view.export_to_markdown() == expected
            layout = LayoutVisualizer(params=LayoutVisualizer.Params(show_label=False))
            view.get_visualization(show_label=False, show_branch_numbering=False)[1].save(OUT / f"{name}-{key}-order.png")
            for mode, style in (("text", HTMLOutputStyle.SINGLE_COLUMN), ("split", HTMLOutputStyle.SPLIT_PAGE)):
                content = HTMLDocSerializer(doc=view, params=HTMLParams(
                    output_style=style, image_mode=ImageRefMode.EMBEDDED,
                )).serialize(visualizer=ReadingOrderVisualizer(base_visualizer=layout)).text
                content = content.replace("</head>", RESPONSIVE + "</head>")
                (OUT / f"{name}-{key}-{mode}.html").write_text(content)
            assert document.model_dump(mode="json") == original
            entries.append({"profile": name, "page": key, "source_document": str(path),
                "native_text": f"{name}-{key}-text.html", "native_split": f"{name}-{key}-split.html",
                "native_reading_order": f"{name}-{key}-order.png"})
    assert len(entries) == 28
    assert all(sha(Path(path)) == digest for path, digest in hashes.items())
    for path in OUT.glob("*.png"):
        with Image.open(path) as image:
            image.verify()
    manifest = {"new_model_inferences": 0, "source_text_and_geometry_changed": False,
        "presentation_copy_only": "144dpi source page background for native visualization",
        "note": "Native final DocItem provenance/order; not raw Heron boxes or confidence. Text is saved document content, not corrected.",
        "inputs": hashes, "entries": entries,
        "outputs": {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file()}}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    (HERE / "receipt.json").write_text(json.dumps({"output": str(OUT), "documents": len(entries), "model_inferences": 0}, indent=2) + "\n")
    print(json.dumps({"output": str(OUT), "documents": len(entries), "model_inferences": 0}))


if __name__ == "__main__":
    render()
