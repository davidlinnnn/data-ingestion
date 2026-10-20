"""Evaluator only: compare frozen native discovery with source-reviewed groups."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent.parent / "pdf-core-bc-closure-2026-10-17/C"
inventory_path = ROOT / "producer-inventory.json"
inventory = json.loads(inventory_path.read_text())
custody = json.loads((ROOT / "producer-custody-v1.json").read_text())
assert hashlib.sha256(inventory_path.read_bytes()).hexdigest() == custody["files"]["producer-inventory.json"]
census = json.loads((OLD / "source-census.json").read_text())
# Manual evaluator associations after source/native image review; never used by producer.
indices = [5, 6, 7, 15, 3, 16, 17, 18, 4, 19, 20, 21, 22, 23, 25, 24, 26, 27, 28]
assert len(indices) == len(census["figures"]) == 19
rows = []
for source, i in zip(census["figures"], indices):
    native = inventory["pictures"][i]
    assert source["source_id"] == native["source_id"]
    assert source["physical_page_1based"] == native["provenance"][0]["page_no"]
    row = {"source_group_id": source["source_group_id"], "native_index": i,
           "owner_ref": native["owner_ref"], "image_key": native["image_key"],
           "crop_sha256": native["crop_sha256"], "discovery": "matched_one_native_owner",
           "source_input_scope": "necessary_graphic_meaning_visible",
           "caption_status": "source_caption_link_or_standalone_preserved",
           "source_truth": "source-only census plus visual comparison; no model outputs used",
           "new_model_quality": "unattempted", "evaluation_only": True}
    if source["source_group_id"] == "SRC11-p02-figure1":
        row.update(source_input_scope="material_partial_title_outside_crop",
                   diagnostic="Entire RL Outer Loop Iteration t title is absent; main graphic branches remain visible. A math ownership is still separate.")
    if source["source_group_id"] == "SRC13-p09-figure5":
        row.update(caption_status="material_failure_native_caption_neighbor_pollution_and_duplication",
                   diagnostic="Native #/texts/68 mixes surrounding prose and broken/repeated caption; generated description must not replace source caption.")
    if source["source_group_id"] == "SRC01-p01-figure1":
        row["caption_status"] = "standalone_caption_texts_28_preserved_no_picture_link"
        row["minor_edge_note"] = "Final model label touches right crop edge; meaning remains identifiable; no manual crop repair."
    rows.append(row)
used = set(indices)
extra = [{"native_index": i, "owner_ref": p["owner_ref"], "image_key": p["image_key"],
          "responsibility": "A_formula_source" if i < 3 else "B_Table3_check_cross_glyph",
          "remote_jobs_retained_in_candidate_cost": 2}
         for i, p in enumerate(inventory["pictures"]) if i not in used]
assert len(extra) == 10
result = {"scope_pages": 55, "source_groups": 19, "source_groups_matched": 19,
          "native_inputs": 29, "material_input_partial_groups": 1,
          "material_caption_failure_groups": 1, "unmatched_source_groups": 0,
          "extra_native_C_candidates": extra, "groups": rows,
          "source_presence_is_not_content_accuracy": True,
          "full_C_coverage_gate": "blocked", "N_C_candidate_remote": 58,
          "N_C_candidate_local_OCR": 29, "N_3_complete_profile": None,
          "reason": "Known partial source input, material original-caption failure, semantic/OCR contracts and live runner not all ready; no manual source jobs added."}
(ROOT / "source-coverage.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
print(json.dumps({k:v for k,v in result.items() if k not in {"groups", "extra_native_C_candidates"}}, ensure_ascii=False))
