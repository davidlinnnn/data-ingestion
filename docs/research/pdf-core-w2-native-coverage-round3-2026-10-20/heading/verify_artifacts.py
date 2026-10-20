"""Verify saved artifacts without loading Docling or rerunning a stage."""
import copy
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent

def no_images(obj):
    stack = [obj]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            assert value.get("image") is None
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)

def without_levels(obj):
    obj = copy.deepcopy(obj)
    for item in obj["texts"]:
        if item["label"] == "section_header":
            item["level"] = None
    return obj

def main():
    summaries = json.loads((OUT / "summary.json").read_text())
    records = []
    count = 0
    for folder in sorted((OUT / "jobs").iterdir()):
        if not folder.is_dir():
            continue
        baseline = json.loads((folder / "baseline-imagefree.json").read_text())
        no_images(baseline)
        stripped = without_levels(baseline)
        assert json.loads((folder / "b0-n0-s0/document.json").read_text()) == baseline
        for path in sorted(folder.glob("b*-n*-s*/document.json")):
            result = json.loads(path.read_text())
            no_images(result)
            assert without_levels(result) == stripped, str(path)
            count += 1
        inp = json.loads((folder / "inputs.json").read_text())
        changes = inp["source_to_core_normalization_diff"]
        clamp = [v for v in changes if "/bbox/" in v["path"]]
        records.append({"id": folder.name, "image_free": True, "eight_outputs_level_only": True,
            "alloff_equals_imagefree_core_baseline": True,
            "raw_to_core_bbox_coordinate_changes": len(clamp),
            "raw_to_core_bbox_differences": clamp,
            "raw_to_core_full_difference_file": str((folder / "inputs.json").resolve())})
    assert count == 288 and len(records) == 36
    result = {"document_outputs_checked": count, "baseline_snapshots_checked": len(records),
        "all_image_fields_none": True, "all_output_fields_except_heading_levels_equal_to_core_baseline": True,
        "raw_provenance_unchanged_claimed": False,
        "scope": "Stage comparison is to image-free Core-load baseline, not raw saved JSON. Raw bbox clamps remain explicitly separate.",
        "jobs": records}
    (OUT / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("Verified 288 documents + 36 baseline snapshots; only heading.level differences and no non-null images.")

if __name__ == "__main__":
    main()

