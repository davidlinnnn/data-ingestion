"""Verify saved JSON rendering and exact whole-item source association, offline."""

import importlib.util
from pathlib import Path

from docling_core.types.doc import DoclingDocument

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    adapter = load("api_review_adapter", HERE / "apply.py")
    parser = load("api_segment_renderer", HERE.parent / "parsed/parse.py")
    prior = adapter.inputs.preserve_prior()
    manifest = adapter.read(HERE.parent / "inputs/input-manifest.json")
    plan = adapter.read(HERE / "plan.json")
    parsed_checks = []
    for row in manifest["inputs"]:
        folder = HERE.parent / "parsed" / row["id"]
        raw_path = HERE.parent / "api" / row["id"] / "output.json"
        data = parser.read(raw_path)
        parser.validate(data, row["image_pixels_wh"])
        markdown, mapped = parser.render(data)
        record = adapter.read(folder / "render-map.json")
        assert adapter.read(folder / "original-blocks.json") == data
        assert (folder / "document.md").read_text() == markdown
        assert record["blocks"] == mapped and record["input_source_metadata"] == row
        assert record["api_output_sha256"] == adapter.old.sha(raw_path)
        assert adapter.old.sha(HERE.parent / "api" / row["id"] / "input.png") == row["image_sha256"]
        for block in mapped:
            for segment in block["segments"]:
                left, right = segment["markdown_charspan"]
                assert markdown[left:right] == segment["rendered_markup"]
        parsed_checks.append({"input_id": row["id"], "original_blocks_unchanged": True,
            "exact_api_input_png_preserved": True, "segment_output_offsets_exact": True})
    applied, total = 0, 0
    source_checks = []
    for source in prior["sources"]:
        folder = HERE / source["name"]
        record = adapter.read(folder / "inline-structure.json")
        raw = adapter.read(REPO / source["document_path"])
        document = DoclingDocument.model_validate(raw)
        assert (folder / "baseline.md").read_text() == document.export_to_markdown()
        rows = [r for r in plan["rows"] if r["source"] == source["name"]]
        assert {r["candidate_id"] for r in rows} == {r["candidate_id"] for r in record["candidates"]}
        accepted = [c for c in record["candidates"] if c["status"] != "not_applied"]
        adapter.old.validate_batch(raw, rows, accepted)
        markdown, spans = adapter.old.render(document, accepted)
        assert (folder / "candidate.md").read_text() == markdown
        for candidate in record["candidates"]:
            total += 1
            if candidate["status"] == "not_applied":
                assert candidate["main_markdown_charspan"] is None and candidate["reason"]
                continue
            applied += 1
            assert candidate["main_markdown_charspan"] == spans[candidate["candidate_id"]]
            left, right = candidate["main_markdown_charspan"]
            assert markdown[left:right] == candidate["markdown"]
            for segment in candidate["main_markdown_segment_offsets"]:
                start, end = segment["main_markdown_charspan"]
                assert markdown[start:end] == segment["rendered_markup"]
            assert all(n["before_sha256"] == n["after_sha256"] for n in candidate["neighbors"])
        source_checks.append({"source": source["name"], "outside_scope_serialization_unchanged": True,
            "raw_provider_document_unchanged": True, "applied_whole_item_and_segment_ranges_exact": True})
    assert total == 17 and len(parsed_checks) == 22
    summary = adapter.read(HERE / "summary.json")
    assert applied == summary["status_counts"].get("structurally_applied_semantic_quality_unverified", 0)
    adapter.inputs.preserve_prior()
    adapter.save(HERE / "verification.json", {"passed": True, "parsed_inputs": parsed_checks,
        "source_associations": source_checks, "structurally_applied": applied, "not_applied": total-applied,
        "prior_646_payloads_unchanged": True, "semantic_quality": "Independent review; no correctness inferred from association"})
    print(f"Verified22 original JSON/render inputs and17 paragraph associations: {applied} applied, {total-applied} abstained.")


if __name__ == "__main__":
    main()
