"""Apply valid API paragraph renderings through the unchanged frozen provider guards."""

import collections
import copy
import importlib.util
import json
from pathlib import Path
import sys

from docling_core.types.doc import DoclingDocument

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OLD = REPO / "docs/research/pdf-core-g2-inline-2026-10-15"
INPUTS = HERE.parent / "inputs"
PARSED = HERE.parent / "parsed"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load_module("frozen_inline_association", OLD / "reinsertion/apply.py")
inputs = load_module("frozen_api_input_references", INPUTS / "prepare.py")


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def guard_view(blocks):
    labels = {"paragraph": "text", "heading": "section_header", "formula": "formula", "code": "code",
        "caption": "caption", "footnote": "footnote", "list_item": "list_item", "other": "unspecified"}
    texts = []
    for block in blocks:
        parts = []
        for segment in block["segments"]:
            text = segment["text"] or ""
            parts.append("$"+text+"$" if segment["kind"] == "math" else text)
        texts.append({"label": labels[block["kind"]], "text": "".join(parts)})
    return {"body": {"children": [{"$ref": f"#/texts/{i}"} for i in range(len(texts))]}, "texts": texts}


def proposal(row, candidate, plan_row):
    folder = PARSED / row["id"]
    result = {"api_input_id": row["id"], "candidate_id": candidate["id"], "item_ref": candidate["item_ref"],
        "provider_text_sha256": candidate["provider_text_sha256"], "replacement_charspan": candidate["replacement_charspan"],
        "status": "not_applied"}
    try:
        failure = folder / "failure.json"
        if failure.exists():
            result["parse_failure_ref"] = inputs.ref(failure)
            raise ValueError("API contract/renderer parse failed: "+read(failure)["reason"])
        mapped = read(folder / "render-map.json")
        blocks_path = folder / "original-blocks.json"
        blocks = read(blocks_path)
        markdown_path = folder / "document.md"
        result.update(original_model_blocks_ref=inputs.ref(blocks_path), original_model_blocks=blocks,
            parsed_render_map_ref=inputs.ref(folder / "render-map.json"), model_markdown=markdown_path.read_text(),
            uncertainties=blocks["uncertainties"], api_output_ref={"path": mapped["api_output_path"], "sha256": mapped["api_output_sha256"]})
        if old.sha(REPO / mapped["api_output_path"]) != mapped["api_output_sha256"]:
            raise ValueError("stale API output")
        if read(REPO / mapped["api_output_path"]) != blocks:
            raise ValueError("parsed blocks differ from original API output")
        if mapped["input_source_metadata"] != row:
            raise ValueError("parsed input identity differs from frozen manifest")
        if not mapped["eligible_for_reinsertion"]:
            raise ValueError("unknown or null source segments remain; original provider item retained")
        old.check_shape(candidate, guard_view(blocks["blocks"]))
        if not plan_row["item_reachable_in_stock_markdown_traversal"]:
            raise ValueError("provider item is a hidden picture child in stock Markdown; no outer-picture rewrite attempted")
        result.update(status="structurally_applied_semantic_quality_unverified", markdown=markdown_path.read_text(),
            model_blocks_and_segment_offsets=mapped["blocks"])
    except (ValueError, KeyError, TypeError, FileNotFoundError) as error:
        result["reason"] = str(error)
    return result


def main():
    prior = inputs.preserve_prior()
    manifest = read(INPUTS / "input-manifest.json")
    for name, digest in read(INPUTS / "artifact-sha256.json").items():
        assert old.sha(INPUTS / name) == digest
    old.check_inputs()
    plan = old.make_plan(prior)
    plan.update(api_input_manifest_sha256=old.sha(INPUTS / "input-manifest.json"),
        reused_guard_source_ref=inputs.ref(OLD / "reinsertion/apply.py"),
        scope="API structured-segment component review association; original provider data unchanged; no Docling Core/provider output claim")
    save(HERE / "plan.json", plan)
    proposals = []
    for row in [r for r in manifest["inputs"] if r["phase"] == "paragraph"]:
        candidate = next(c for c in prior["candidates"] if c["id"] == row["prior_input_id"])
        plan_row = next(r for r in plan["rows"] if r["candidate_id"] == candidate["id"])
        proposals.append(proposal(row, candidate, plan_row))
    for source in prior["sources"]:
        folder = HERE / source["name"]
        folder.mkdir(exist_ok=False)
        raw = read(REPO / source["document_path"])
        before_hash = old.digest(raw)
        document = DoclingDocument.model_validate(raw)
        rows = [r for r in plan["rows"] if r["source"] == source["name"]]
        ids = {r["candidate_id"] for r in rows}
        selected = [p for p in proposals if p["candidate_id"] in ids]
        accepted = [p for p in selected if p["status"] != "not_applied"]
        old.validate_batch(raw, rows, accepted)
        baseline_md = document.export_to_markdown()
        assert old.render(document, [])[0] == baseline_md
        markdown, spans = old.render(document, accepted)
        assert old.digest(raw) == before_hash
        (folder / "baseline.md").write_text(baseline_md)
        (folder / "candidate.md").write_text(markdown)
        association = []
        for item in selected:
            row = next(r for r in rows if r["candidate_id"] == item["candidate_id"])
            span = spans.get(item["candidate_id"])
            segments = []
            if span is not None:
                for block in item["model_blocks_and_segment_offsets"]:
                    for segment in block["segments"]:
                        left, right = segment["markdown_charspan"]
                        segments.append({**segment, "main_markdown_charspan": [span[0]+left, span[0]+right]})
            association.append({**item, "main_markdown_charspan": span, "main_markdown_segment_offsets": segments,
                "source_association": row["source_association"], "provider_join_gaps": row["provider_join_gaps"],
                "neighbors": [{"item_ref": n["item_ref"], "before_sha256": n["item_sha256"], "after_sha256": n["item_sha256"], "unchanged": True} for n in row["neighbors"]],
                "source_precision": "Original provider paragraph/page-fragment bounds only; API block/segment associations are inferred, never measured source glyph boxes"})
        save(folder / "inline-structure.json", {"format": "g2-inline-api-review-association-v1",
            "method": "Offline structured-segment Markdown substitution through reused frozen provider guards",
            "provider_document_ref": {"path": source["document_path"], "sha256": source["document_sha256"]},
            "provider_unchanged": True, "outside_scope_content_unchanged": True, "all_provider_refs_preserved": True,
            "structural_application_is_not_semantic_acceptance": True, "candidates": association})
    inputs.preserve_prior()
    save(HERE / "summary.json", {"candidate_count": len(proposals),
        "status_counts": dict(collections.Counter(p["status"] for p in proposals)),
        "outcomes": [{k: v for k, v in p.items() if k in {"api_input_id", "candidate_id", "status", "reason"}} for p in proposals],
        "reused_guard_source_ref": inputs.ref(OLD / "reinsertion/apply.py"), "adapter_sha256": old.sha(Path(__file__)),
        "semantic_quality": "Independent review; no model content repaired", "prior_646_payloads_unchanged": True})
    print("API paragraph association complete; rejected model blocks retained and provider originals unchanged.")


def selfcheck():
    raw = {"texts": [{"self_ref": "#/texts/0", "text": "alpha"}, {"self_ref": "#/texts/1", "text": "neighbor"}]}
    row = {"candidate_id": "example", "item_ref": "#/texts/0", "canonical_document_sha256": old.digest(raw),
        "item_sha256": old.digest(raw["texts"][0]), "replacement_charspan": [0, 5], "provider_text_sha256": "expected", "neighbors": []}
    valid = {"candidate_id": "example", "item_ref": "#/texts/0", "replacement_charspan": [0, 5], "provider_text_sha256": "expected"}
    old.validate_batch(raw, [row], [valid])
    negatives = []
    for name, document, proposals in [
        ("stale", raw, [{**valid, "provider_text_sha256": "stale"}]),
        ("duplicate", raw, [valid, valid]),
        ("unknownref", raw, [{**valid, "item_ref": "#/texts/99"}]),
        ("drop_outside_scope", {"texts": raw["texts"][:1]}, [valid])]:
        try:
            old.validate_batch(document, [row], proposals)
        except ValueError:
            negatives.append(name)
        else:
            raise AssertionError(name+" was accepted")
    example = {"provider_label": "text", "provider_text": "alpha beta gamma delta epsilon zeta"}
    block = {"kind": "paragraph", "segments": [{"kind": "text", "text": example["provider_text"]}]}
    old.check_shape(example, guard_view([block]))
    for name, blocks in [("multiple_roots", [block, block]), ("new_repeat", [{**block, "segments": [{"kind": "text", "text": (example["provider_text"]+" ")*2}]}])]:
        try:
            old.check_shape(example, guard_view(blocks))
        except ValueError:
            negatives.append(name)
        else:
            raise AssertionError(name+" was accepted")
    save(HERE / "selfcheck.json", {"passed": True, "reused_guards_negative_controls": negatives,
        "old_guard_source_sha256": old.sha(OLD / "reinsertion/apply.py")})
    print("Reused offline source-association guards passed.")


if __name__ == "__main__":
    selfcheck() if sys.argv[1:] == ["--selfcheck"] else main()
