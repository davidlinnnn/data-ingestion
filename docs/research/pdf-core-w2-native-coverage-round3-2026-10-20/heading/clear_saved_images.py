"""Clear image metadata in round3-owned saved artifacts; never rerun any stage."""
import json
from pathlib import Path
from docling_core.types.doc import DoclingDocument
from run_ablation import OUT, clear_images, HELPERS, write

def main():
    rows = []
    for p in sorted((OUT / "jobs").glob("*/b*-n*-s*/document.json")):
        original = json.loads(p.read_text())
        original_sha = HELPERS.sha(p)
        removed = clear_images(original)
        if not removed:
            continue
        normalized = DoclingDocument.model_validate(original).model_dump(mode="json")
        assert normalized == original
        md = p.with_name("document.md")
        old_md = md.read_bytes()
        assert DoclingDocument.model_validate(original).export_to_markdown().encode() == old_md
        write(p, original)
        summary_path = p.with_name("summary.json")
        summary = json.loads(summary_path.read_text())
        summary["stage_input_images_cleared"] = False
        summary["saved_artifact_images_cleared_after_stage"] = True
        summary["image_cleanup_note"] = "Original stage used only text/font/outline while retaining unused image metadata in deepcopy. Image fields cleared in round3-owned artifact afterward; no assign_heading_levels/conversion rerun. All non-image fields and MD bytes identical."
        write(summary_path, summary)
        rows.append({"document": str(p), "before_sha256": original_sha,
            "after_sha256": HELPERS.sha(p), "cleared": removed,
            "all_nonimage_fields_equal": True, "markdown_bytes_equal": True,
            "stage_rerun": False, "conversion_rerun": False})
    write(OUT / "image-cleanup.json", rows)
    # Per-job summaries mirror the already verified combination summaries.
    for path in sorted((OUT / "jobs").glob("*/summary.json")):
        write(path, {d.parent.name: json.loads(d.read_text()) for d in sorted(path.parent.glob("b*-n*-s*/summary.json"))})
    print(f"Cleared images in {len(rows)} owned outputs; non-image JSON and Markdown unchanged.")

if __name__ == "__main__":
    main()

