"""Official serialization only; preserve model-dump originals, never rerun heading stages."""
import json
from pathlib import Path
from docling_core.types.doc import DoclingDocument

ROOT = Path(__file__).resolve().parent
def main():
    records = []
    for group in ("pdfium-integration", "V2-bookmarks"):
        for folder in sorted((ROOT / group).iterdir()):
            if not folder.is_dir():
                continue
            modeldump = folder / ("document-modeldump.json" if group == "V2-bookmarks" else "document.json")
            target = folder / ("document.json" if group == "V2-bookmarks" else "document-canonical.json")
            if group == "V2-bookmarks" and not modeldump.exists():
                modeldump.write_bytes(target.read_bytes())
            doc = DoclingDocument.model_validate_json(modeldump.read_text())
            before = doc.model_dump(mode="json")
            doc.save_as_json(target)
            reloaded = DoclingDocument.model_validate_json(target.read_text())
            assert reloaded.model_dump(mode="json") == before
            assert reloaded.export_to_markdown().encode() == (folder / "document.md").read_bytes()
            records.append({"group": group, "id": folder.name, "canonical_json": str(target.resolve()),
                "modeldump_json_preserved": str(modeldump.resolve()),
                "official_save_as_json": True, "roundtrip_modeldump_equal": True,
                "markdown_bytes_equal": True, "stage_rerun": False})
    assert len(records) == 72
    (ROOT / "canonical-serialization.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    print("72 official canonical JSON exports; semantic roundtrip and Markdown equal, no stage rerun.")

if __name__ == "__main__":
    main()

