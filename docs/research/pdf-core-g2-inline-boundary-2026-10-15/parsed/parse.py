"""Reuse the frozen JSON contract/renderer for the six boundary inputs, offline."""

import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ROOT = HERE.parent
PRIOR = REPO / "docs/research/pdf-core-g2-inline-api-2026-10-15/parsed/parse.py"
spec = importlib.util.spec_from_file_location("frozen_boundary_segment_parser", PRIOR)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
read, save, sha = parser.read, parser.save, parser.sha


def main():
    manifest = read(ROOT / "inputs/input-manifest.json")
    outcomes = []
    for row in manifest["inputs"]:
        folder = HERE / row["id"]
        folder.mkdir(exist_ok=False)
        output = ROOT / "api" / row["id"] / "output.json"
        record = {"input_id": row["id"], "input_metadata": row,
            "api_output_ref": {"path": str(output.relative_to(REPO)), "sha256": sha(output)}}
        try:
            if sha(REPO / row["image_path"]) != row["image_sha256"]:
                raise ValueError("stale input image")
            if sha(output.parent / "input.png") != row["image_sha256"]:
                raise ValueError("API image differs from frozen producer input")
            data = read(output)
            parser.validate(data, row["image_pixels_wh"])
            markdown, blocks = parser.render(data)
            save(folder / "original-blocks.json", data)
            (folder / "document.md").write_text(markdown)
            record.update(status="parsed", blocks=blocks, uncertainties=data["uncertainties"],
                eligible_for_association=not any(s["text"] is None or s["kind"] == "unknown" for b in data["blocks"] for s in b["segments"]),
                markdown_sha256=sha(folder / "document.md"),
                source_precision="Model image block bounds and inferred segment associations only; original fragment mappings remain separate")
            save(folder / "render-map.json", record)
        except (ValueError, KeyError, TypeError, FileNotFoundError) as error:
            record.update(status="parse_failed", reason=str(error))
            save(folder / "failure.json", record)
        outcomes.append({k: record[k] for k in ("input_id", "status", "reason") if k in record})
    save(HERE / "summary.json", {"scope": "Six direct API component responses, offline; no semantic repair or Docling provider claim",
        "input_manifest_sha256": sha(ROOT / "inputs/input-manifest.json"),
        "reused_parser_ref": {"path": str(PRIOR.relative_to(REPO)), "sha256": sha(PRIOR)},
        "adapter_sha256": sha(Path(__file__)), "outcomes": outcomes})
    print("Parsed six boundary responses; all model strings retained exactly.")


def selfcheck():
    # The frozen checks write only this new lane by changing their output directory.
    original = parser.HERE
    try:
        parser.HERE = HERE
        parser.selfcheck()
    finally:
        parser.HERE = original


if __name__ == "__main__":
    selfcheck() if sys.argv[1:] == ["--selfcheck"] else main()
