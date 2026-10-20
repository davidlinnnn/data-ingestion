"""Read-only integrity and census checks; no generation or inference."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


frozen = json.loads((ROOT / "artifact-hashes.json").read_text())
for rel, digest in frozen.items():
    assert sha(ROOT / rel) == digest, rel
references = json.loads((ROOT / "referenced-hashes.json").read_text())
for path, digest in references.items():
    assert sha(Path(path)) == digest, path
census = json.loads((ROOT / "source-census.json").read_text())
pages, groups = census["pages"], census["figures"]
assert len(pages) == 55
assert len({(p["source_sha256"], p["physical_page_1based"]) for p in pages}) == 55
assert all(p["review_status"] == "visual_presence_and_caption_location_reviewed" for p in pages)
assert len(groups) == len({g["source_group_id"] for g in groups}) == 19
assert sum(g["visual_kind"] == "chart" for g in groups) == 10
assert sum(g["required_work"]["chart_data"] == "required" for g in groups) == 9
assert all(g["evaluation_only"] and g["producer_owner"] is None and g["same_revision_image_key"] is None for g in groups)
assert census["producer_jobs"] is None and census["N_3"] is None
assert census["native_inventory_used_as_truth"] is False
assert census["embedded_images_used_as_truth"] is False
assert all(sha(ROOT / p["image"]) == p["image_sha256"] for p in pages)
assert sum(bool(p["raster_page_wrapper"]) for p in pages) == 8
registration = json.loads((ROOT / "registration.json").read_text())
assert all(registration[k] == 0 for k in ["api_calls", "model_calls", "install", "downloads", "holdout_reads", "production_changes", "sdk_changes", "github_writes"])
print(json.dumps({"status": "read_only_source_and_evidence_checks_passed", "pages": 55,
                  "logical_source_groups": 19, "new_model_calls": 0,
                  "own_files_verified": len(frozen), "reference_files_verified": len(references),
                  "full_C_readiness": "partial", "N_3": None}))
