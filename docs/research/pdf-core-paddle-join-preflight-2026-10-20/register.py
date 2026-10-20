"""Freeze dependency/source identities and synthetic inputs before behavior tests."""
import ast
import importlib.metadata
from pathlib import Path
import subprocess

from join_common import HERE, read, sha, write


def main():
    assert not (HERE / "registration.json").exists()
    assert not (HERE / "paddle").exists() and not (HERE / "docling").exists()
    from PIL import Image, ImageDraw
    import pypdfium2 as pdfium
    source = HERE / "sources"
    source.mkdir(exist_ok=True)
    fixture = read(HERE / "fixture.json")
    canvas = [Image.new("RGB", (1200, 1600), "white") for _ in range(2)]
    for page in fixture["pages"]:
        image = Image.new("RGB", (page["width"], page["height"]), "white")
        draw = ImageDraw.Draw(image)
        for block in page["blocks"]:
            x1, y1, x2, y2 = block["bbox"]
            if block["label"] in ("image", "chart"):
                draw.rectangle([x1, y1, x2 - 1, y2 - 1], fill=page["color"])
            else:
                draw.text((x1, y1), block["content"], fill="black")
        canvas.append(image)
    canvas[0].save(source / "source.pdf", save_all=True, append_images=canvas[1:], resolution=144)
    pdf = pdfium.PdfDocument(source / "source.pdf")
    geometry = []
    for page in fixture["pages"]:
        index = page["page_index"]
        actual = pdf[index]
        expected = [page["width"] / 2, page["height"] / 2]
        assert list(actual.get_size()) == expected
        raster = actual.render(scale=2).to_pil().convert("RGB")
        assert raster.size == (page["width"], page["height"])
        raster.save(source / f"page-{index + 1}.png")
        geometry.append({"source_physical_page_no": index + 1, "pdf_points": expected,
            "rendered_pixels": list(raster.size), "render_scale": 2, "orientation": False, "unwarp": False})
    write(HERE / "source-geometry.json", {"scope": "Generated synthetic four-page PDF and actual PyPdfium144dpi renders, not Paddle model inputs.",
        "source_pdf_sha256": sha(source / "source.pdf"), "pages": geometry})
    for script in HERE.glob("*.py"):
        ast.parse(script.read_text())
    site = Path("/private/tmp/pdf-core-paddle-join-20261020/venv/lib/python3.12/site-packages")
    old = HERE.parent / "pdf-core-g2-preflight-2026-10-16/candidate"
    for name, path in (("result", "inference/pipelines/paddleocr_vl/result.py"),
                       ("pipeline", "inference/pipelines/paddleocr_vl/pipeline.py")):
        assert (site / "paddlex" / path).read_bytes() == (old / f"paddlex-v372-{name}.py").read_bytes()
    from docling.utils import paddleocr_vl_utils, chandra_utils, vlm_utils
    from docling_core.types.doc import document
    assert Path(paddleocr_vl_utils.__file__).read_bytes() == (old / "docling-v2132-paddleocr_vl_utils.py").read_bytes()
    paths = [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    paths += list((site / "paddlex").rglob("*.py"))
    paths += [Path(module.__file__) for module in (paddleocr_vl_utils, chandra_utils, vlm_utils, document)]
    versions = subprocess.check_output(["rtk", "proxy", "/private/tmp/pdf-core-paddle-join-20261020/venv/bin/python", "-B", "-m", "pip", "freeze", "--all"], text=True)
    (HERE / "paddlex-client-lock.txt").write_text(versions)
    paths.append(HERE / "paddlex-client-lock.txt")
    write(HERE / "registration.json", {"state": "frozen_before_behavioral_probes", "model_inference_calls_allowed": 0,
        "model_weight_downloads_allowed": 0, "worker_network_allowed": False,
        "core_runtime": {name: importlib.metadata.version(name) for name in ("docling-slim", "docling-core", "pypdfium2", "markdown-it-py")},
        "paddlex_client": "3.7.2 isolated PyPI installation, complete result/export modules; no Paddle engine or model weights",
        "hashes": {str(p.resolve()): sha(p) for p in paths},
        "table_controls": fixture["table_control"]["cases"],
        "stop": "No inference; required contract defects are recorded, not repaired with semantic heuristics or SDK edits."})
    print("Frozen complete official modules, client lock, actual synthetic PDF/raster geometry and eight contract-control families; zero inference.")


if __name__ == "__main__":
    main()
