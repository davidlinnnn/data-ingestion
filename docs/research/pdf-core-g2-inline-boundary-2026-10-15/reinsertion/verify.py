"""Read-only reconstruction and hash verification of the frozen boundary lane."""

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("verify_boundary_working_delta", HERE / "apply.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def main():
    for directory in (a.ROOT / "inputs", a.ROOT / "parsed", HERE):
        for name, expected in a.read(directory / "artifact-sha256.json").items():
            assert a.sha(directory / name) == expected, str(directory / name)
    manifest = a.read(a.ROOT / "inputs/input-manifest.json")
    preserved = 0
    for old in manifest["prior_payload_manifests"]:
        for payload in a.read(a.checked(old))["files"]:
            a.checked(payload)
            preserved += 1
    a.checked(manifest["registry_ref"])
    cells = a.read(a.checked(manifest["native_cells_ref"]))
    a.checked(manifest["native_checkpoint_ref"])
    plans = a.read(HERE / "plan.json")["rows"]
    for row in manifest["inputs"]:
        a.checked(row["source"])
        a.checked(row["baseline_document_ref"])
        assert a.sha(a.REPO / row["image_path"]) == row["image_sha256"]
        assert a.sha(a.ROOT / "api" / row["id"] / "input.png") == row["image_sha256"]
        parsed = a.ROOT / "parsed" / row["id"]
        mapped = a.read(parsed / "render-map.json")
        data = a.read(a.checked(mapped["api_output_ref"]))
        a.parser.validate(data, row["image_pixels_wh"])
        markdown, offsets = a.parser.render(data)
        assert data == a.read(parsed / "original-blocks.json")
        assert markdown == (parsed / "document.md").read_text()
        assert mapped["blocks"] == offsets and mapped["input_metadata"] == row
        for fragment in row["source_fragments"]:
            a.checked(fragment["full_page_raster_ref"])
            a.checked(fragment["image_ref"])
    for source in ("controls", "seal"):
        folder = HERE / source
        delta = a.read(folder / "working-delta.json")
        raw = a.read(a.checked(delta["provider_document_ref"]))
        document = a.DoclingDocument.model_validate(raw)
        assert document.export_to_markdown() == (folder / "baseline.md").read_text()
        accepted = [p for p in delta["proposals"] if p["status"] != "not_applied"]
        for p in delta["proposals"]:
            if p["method"] == "new_API_response":
                recomputed = a.model_proposal(raw, p["original_input_metadata"], cells)
                assert (recomputed["status"], recomputed.get("reason"), recomputed.get("markdown")) == (p["status"], p.get("reason"), p.get("markdown"))
            elif p["method"] == "native_boundary_fallback":
                recomputed = a.native_boundary(raw, p["original_input_metadata"])
                for key in ("markdown", "native_blocks", "source_charspan_accounting", "native_output_segment_offsets"):
                    assert recomputed[key] == p[key]
            elif p["status"] != "not_applied":
                code = next(q for q in delta["proposals"] if "code_character_operator_indentation_evidence" in q)
                recomputed = a.inline_reuse(raw, manifest["reused_without_inference"]["inline_role"], code["code_character_operator_indentation_evidence"]["native_code_font_key"])
                assert recomputed["markdown"] == p["markdown"]
        for p in accepted:
            plan_id = p["original_input_metadata"]["id"] if "original_input_metadata" in p else p["id"]
            a.scope_guard(raw, next(r for r in plans if r["id"] == plan_id), p["consumed_item_refs"])
        markdown, spans, outside = a.render(document, accepted)
        assert markdown == (folder / "working.md").read_text()
        assert spans == delta["working_serialization_spans"] and outside == delta["unchanged_outside_literal_spans"]
        for p in accepted:
            for segment in p["main_markdown_segment_offsets"]:
                assert markdown[slice(*segment["main_markdown_charspan"])] == segment["rendered_markup"]
    assert a.read(HERE / "selfcheck.json")["passed"]
    assert a.read(a.ROOT / "parsed/selfcheck.json")["passed"]
    print(json.dumps({"passed": True, "parsed_responses": 6, "working_sources": 2,
        "prior_payloads_unchanged": preserved, "source_and_output_hashes_checked": True,
        "working_markdown_offsets_and_outside_literal_order_reconstructed": True,
        "semantic_approval": False, "API_calls": 0, "writes": 0}))


if __name__ == "__main__":
    main()
