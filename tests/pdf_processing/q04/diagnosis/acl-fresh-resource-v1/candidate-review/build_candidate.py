"""Build the fixture-09 Option A review package without changing active inputs.

The output is a source-review candidate.  It is deliberately marked
``NOT_ACCEPTED`` and cannot be used as an acceptance result by this module.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[6]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from pdf_processing.evidence import graph_items, top_left  # noqa: E402
from tests.pdf_processing.q04.consumer import (  # noqa: E402
    canonical,
    check_graph,
    graph_projection,
    sha,
)

DELTA_SPEC = importlib.util.spec_from_file_location(
    "acl_option_a_graph_delta", Path(__file__).resolve().parent.parent / "analyze_graph_delta.py"
)
assert DELTA_SPEC and DELTA_SPEC.loader
GRAPH_DELTA = importlib.util.module_from_spec(DELTA_SPEC)
DELTA_SPEC.loader.exec_module(GRAPH_DELTA)


EXPECTED = {
    "reference": "aaa62538d423472fd4999675fdcd39501eaa11bce89d630843c8609177533c6c",
    "candidate": "ff3cdcb6142e7046f5e248827548a1cd303f68c9317b2488d9dd251805c3f506",
    "retained_report": "32bf568a25a4f9c7d85d3673edeb6e715b76b6a7bba41552aa224d2945f15afe",
    "quality_oracle": "f9494c36cc7d628a73658f14b0a6637e20540641b8815c7313f9cbc6120d0bb2",
    "original_pdf": "9e7692e06ed049928391e2a20bd9b9b7ad4834a6e047a3c4b64df1e82376ced3",
    "fixture_pdf": "bd33fffb2c91f35225f5b89feb29a93013f4814558ac578bef000b632fd169bf",
}

SPLIT_REFERENCE = "#/texts/97"
SPLIT_CANDIDATE = ("#/texts/97", "#/texts/98")


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def load_verified(path: Path, expected: str) -> Any:
    actual = file_sha(path)
    if actual != expected:
        raise ValueError(f"unexpected SHA-256 for {path}: {actual}")
    return json.loads(path.read_text())


def ref(value: dict[str, Any] | None) -> str | None:
    return None if not value else value.get("$ref", value.get("cref"))


def fragments(node: dict[str, Any]) -> tuple[str, ...]:
    result = []
    for provenance in node.get("prov", []):
        text = node.get("text")
        if text is not None:
            text = text[slice(*provenance["charspan"])]
        result.append(
            canonical(
                [
                    node.get("label"),
                    provenance["page_no"],
                    provenance["bbox"],
                    text,
                ]
            )
        )
    return tuple(result)


def text_mapping(
    reference: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, list[str]]:
    """Map each historical text ref to its exact candidate source segment(s)."""
    candidate_texts = candidate["texts"]
    mapping: dict[str, list[str]] = {}
    split_count = 0
    for old in reference["texts"]:
        exact = [node for node in candidate_texts if fragments(node) == fragments(old)]
        if len(exact) == 1:
            mapping[old["self_ref"]] = [exact[0]["self_ref"]]
            continue
        pairs = []
        for index in range(len(candidate_texts) - 1):
            pair = candidate_texts[index : index + 2]
            if fragments(pair[0]) + fragments(pair[1]) != fragments(old):
                continue
            if " ".join(node.get("text", "") for node in pair) != old.get("text", ""):
                continue
            if " ".join(node.get("orig", "") for node in pair) != old.get("orig", ""):
                continue
            if any(node.get("label") != old.get("label") for node in pair):
                continue
            if any(ref(node.get("parent")) != ref(old.get("parent")) for node in pair):
                continue
            pairs.append(pair)
        if len(pairs) != 1:
            raise ValueError(f"no unique source mapping for {old['self_ref']}")
        mapping[old["self_ref"]] = [node["self_ref"] for node in pairs[0]]
        split_count += 1
    if split_count != 1 or mapping.get(SPLIT_REFERENCE) != list(SPLIT_CANDIDATE):
        raise ValueError("candidate is not the reviewed one-node split")
    flattened = [new for values in mapping.values() for new in values]
    if len(flattened) != len(candidate_texts) or set(flattened) != {
        node["self_ref"] for node in candidate_texts
    }:
        raise ValueError("text mapping does not cover the complete candidate")
    return mapping


def reviewed_delta(
    reference: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Verify the one fixed-fixture split before the full relational comparison."""
    old_by_ref = {node["self_ref"]: node for node in reference["texts"]}
    new_by_ref = {node["self_ref"]: node for node in candidate["texts"]}
    old = old_by_ref.get(SPLIT_REFERENCE)
    if old is None:
        raise ValueError(f"active reference missing reviewed node: {SPLIT_REFERENCE}")
    missing = [node_ref for node_ref in SPLIT_CANDIDATE if node_ref not in new_by_ref]
    if missing:
        raise ValueError(f"reviewed fragment missing: {', '.join(missing)}")
    pair = [new_by_ref[node_ref] for node_ref in SPLIT_CANDIDATE]
    if len(candidate["texts"]) != len(reference["texts"]) + 1:
        raise ValueError("candidate text count is not one greater than reference")
    if [candidate["texts"].index(node) for node in pair] != [97, 98]:
        raise ValueError("reviewed fragment text positions changed")
    if any(node.get("label") != old.get("label") for node in pair):
        raise ValueError("split label changed")
    if any(ref(node.get("parent")) != ref(old.get("parent")) for node in pair):
        raise ValueError("split parent changed")
    if " ".join(node.get("text", "") for node in pair) != old.get("text", ""):
        raise ValueError("split text does not reconstruct reference")
    if " ".join(node.get("orig", "") for node in pair) != old.get("orig", ""):
        raise ValueError("split orig does not reconstruct reference")
    try:
        provenance = GRAPH_DELTA.rebase_provenance(pair)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("split provenance is invalid") from error
    if provenance != old.get("prov"):
        raise ValueError("split provenance does not reconstruct reference")
    try:
        order = [
            candidate["body"]["children"].index({"$ref": node_ref})
            for node_ref in SPLIT_CANDIDATE
        ]
        old_order = reference["body"]["children"].index({"$ref": SPLIT_REFERENCE})
    except (KeyError, ValueError) as error:
        raise ValueError("reviewed fragment reading-order edge missing") from error
    if order != [old_order, old_order + 1]:
        raise ValueError("split reading order changed")
    try:
        graph_delta = GRAPH_DELTA.analyze(reference, candidate)
    except AssertionError as error:
        raise ValueError(f"reviewed relational proof failed: {error}") from error
    remaining = graph_delta[
        "remaining_changed_collections_after_diagnostic_normalization"
    ]
    if (
        graph_delta["verdict"]
        != "one_provenance_preserving_split_explains_full_graph_delta"
        or remaining
    ):
        raise ValueError(
            "additional graph differences remain: " + ", ".join(remaining)
        )
    return graph_delta


def remap_refs(value: Any, mapping: dict[str, list[str]]) -> Any:
    if isinstance(value, list):
        return [remap_refs(child, mapping) for child in value]
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            if key == "refs" and isinstance(child, list):
                result[key] = [new for old in child for new in mapping.get(old, [old])]
            else:
                result[key] = remap_refs(child, mapping)
        return result
    return value


def candidate_report(
    document: dict[str, Any], retained: dict[str, Any], mapping: dict[str, list[str]]
) -> dict[str, Any]:
    report = copy.deepcopy(retained)
    records = []
    for node in graph_items(document):
        record = {
            "ref": node["self_ref"],
            "actual_type": node.get("label", "group"),
            "collection": node["self_ref"].split("/")[1],
            "text": node.get("text"),
            "parent": node.get("parent"),
            "children": node.get("children", []),
            "captions": node.get("captions", []),
            "regions": [],
            "representation": "not_independently_validated",
            "text_empty": node.get("text") == "",
        }
        for provenance in node.get("prov", []):
            page = report["pages"][str(provenance["page_no"])]
            box = top_left(provenance["bbox"], *page["size_points"])
            record["regions"].append(
                {
                    "page": provenance["page_no"],
                    "provenance": provenance,
                    "bbox_top_left_points": box,
                    "page_artifact": page["artifact"],
                    "page_sha256": page["sha256"],
                    "crop_recipe": {"scale": 3, "box_pixels": [x * 3 for x in box]},
                }
            )
        records.append(record)
    report["items"] = records
    report["document_sha256"] = EXPECTED["candidate"]
    report["formula_occurrences"] = remap_refs(
        retained["formula_occurrences"], mapping
    )
    report["representation_observations"] = remap_refs(
        retained["representation_observations"], mapping
    )
    report["candidate_status"] = "NOT_ACCEPTED"
    report["candidate_scope"] = "fixture-09 reviewed representation delta only"
    check_graph(document, report)
    return report


def text_sha(text: Any) -> str:
    return sha(json.dumps(text, ensure_ascii=False).encode())


def quality_item(node: dict[str, Any], typed: dict[str, dict[str, Any]], page: int):
    caption_hashes = []
    for caption in node["captions"]:
        caption_ref = ref(caption)
        if caption_ref is None:
            raise ValueError("caption reference missing")
        caption_hashes.append(text_sha(typed[caption_ref]["text"]))
    return {
        "type": node["actual_type"],
        "text_sha256": text_sha(node["text"]),
        "boxes": [
            region["provenance"]["bbox"]
            for region in node["regions"]
            if region["page"] == page
        ],
        "caption_text_hashes": caption_hashes,
    }


def candidate_quality_oracle(
    old: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any]:
    result = copy.deepcopy(old)
    typed = {node["ref"]: node for node in report["items"]}
    for page in result["pages"]:
        if page["source_id"] != "09":
            continue
        number = page["processed_page"]
        nodes = [
            node
            for node in report["items"]
            if any(region["page"] == number for region in node["regions"])
        ]
        page["items"] = [quality_item(node, typed, number) for node in nodes]
    result["scope"] = (
        "CANDIDATE NOT ACCEPTED: fixture-09 source-reviewed representation delta; "
        "all other source pages copied byte-for-byte from the prior oracle"
    )
    result["candidate_status"] = "NOT_ACCEPTED"
    return result


def split_record(
    reference: dict[str, Any], candidate: dict[str, Any], mapping: dict[str, list[str]]
) -> dict[str, Any]:
    old = next(node for node in reference["texts"] if node["self_ref"] == SPLIT_REFERENCE)
    new = [
        next(node for node in candidate["texts"] if node["self_ref"] == node_ref)
        for node_ref in SPLIT_CANDIDATE
    ]
    return {
        "status": "NOT_ACCEPTED",
        "source": {"fixture": "09", "processed_page": 2, "original_pdf_page": 3},
        "reference": {
            "node": old,
            "text_position": reference["texts"].index(old),
            "reading_order": reference["body"]["children"].index(
                {"$ref": old["self_ref"]}
            ),
        },
        "candidate": [
            {
                "node": node,
                "text_position": candidate["texts"].index(node),
                "reading_order": candidate["body"]["children"].index(
                    {"$ref": node["self_ref"]}
                ),
                "maps_to": SPLIT_REFERENCE,
            }
            for node in new
        ],
        "mapping_counts": {
            "reference_texts": len(mapping),
            "candidate_texts": sum(len(values) for values in mapping.values()),
            "one_to_two": sum(len(values) == 2 for values in mapping.values()),
        },
    }


def manifest(
    *,
    paths: argparse.Namespace,
    reference: dict[str, Any],
    candidate: dict[str, Any],
    report: dict[str, Any],
    old_quality: dict[str, Any],
    quality: dict[str, Any],
    ocr_summary: dict[str, Any],
    q01_hashes: dict[str, str],
    graph_delta: dict[str, Any],
) -> dict[str, Any]:
    old_others = [p for p in old_quality["pages"] if p["source_id"] != "09"]
    new_others = [p for p in quality["pages"] if p["source_id"] != "09"]
    fixture_pages = [p for p in quality["pages"] if p["source_id"] == "09"]
    formula_ids = {
        item.get("review_id") for item in report["formula_occurrences"] if item.get("review_id")
    }
    typed = {item["ref"]: item for item in report["items"]}
    eq2 = next(item for item in report["formula_occurrences"] if item.get("review_id") == "eq2")
    steps = ocr_summary["fresh"]["workflow_result"]["steps"]
    ocr = [step for step in steps if step["stage"] == "component_ocr"]
    return {
        "status": "NOT_ACCEPTED",
        "acceptance_result": "FAIL_exact_graph_against_active_reference",
        "scope": "fixture-09 reviewed representation delta only",
        "hashes": {
            "source_original_pdf": file_sha(paths.original_pdf),
            "source_fixed_fixture_pdf": file_sha(paths.fixture_pdf),
            "active_reference_09": file_sha(paths.reference),
            "candidate_reference_09": file_sha(paths.candidate),
            "active_reference_graph": sha(canonical(graph_projection(reference)).encode()),
            "candidate_reference_graph": sha(canonical(graph_projection(candidate)).encode()),
            "retained_content_evidence": file_sha(paths.retained_report),
            "candidate_content_evidence": sha(json_bytes(report)),
            "active_quality_oracle": file_sha(paths.quality_oracle),
            "candidate_quality_oracle": sha(json_bytes(quality)),
            "runtime_ocr_summary": file_sha(paths.ocr_summary),
            **q01_hashes,
        },
        "proof": {
            "only_change": "one provenance-preserving text split plus reference renumbering",
            "full_graph_delta": graph_delta,
            "reference_texts": len(reference["texts"]),
            "candidate_texts": len(candidate["texts"]),
            "fixture_09_quality_items_by_page": {
                str(page["processed_page"]): len(page["items"]) for page in fixture_pages
            },
            "non_09_quality_pages_unchanged": old_others == new_others,
            "six_formula_ids": sorted(formula_ids),
            "eq2_text_item": all(typed[item_ref]["actual_type"] == "text" for item_ref in eq2["refs"]),
            "required_ocr": [
                {
                    "component": step["component"],
                    "outcome": step["outcome"],
                    "operation": step["operation"],
                }
                for step in ocr
            ],
            "caption_edges": sum(len(item["captions"]) for item in report["items"]),
            "complete_graph": check_graph(candidate, report),
        },
        "boundaries": {
            "active_inputs_modified": False,
            "production_modified": False,
            "runtime_executed": False,
            "candidate_is_pass": False,
        },
    }


def write_exclusive(path: Path, value: Any) -> None:
    raw = json_bytes(value)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def copy_exclusive(source: Path, target: Path) -> None:
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
    try:
        with source.open("rb") as incoming, os.fdopen(descriptor, "wb") as outgoing:
            while block := incoming.read(1024 * 1024):
                outgoing.write(block)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def build(args: argparse.Namespace) -> None:
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite candidate directory: {args.output}")
    output = args.output.resolve()
    try:
        output.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("full candidate output must remain outside the repository")
    reference = load_verified(args.reference, EXPECTED["reference"])
    candidate = load_verified(args.candidate, EXPECTED["candidate"])
    retained = load_verified(args.retained_report, EXPECTED["retained_report"])
    old_quality = load_verified(args.quality_oracle, EXPECTED["quality_oracle"])
    for key in ("original_pdf", "fixture_pdf"):
        path = getattr(args, key)
        if file_sha(path) != EXPECTED[key]:
            raise ValueError(f"unexpected SHA-256 for {path}")
    ocr_summary = json.loads(args.ocr_summary.read_text())
    mapping = text_mapping(reference, candidate)
    graph_delta = reviewed_delta(reference, candidate)
    report = candidate_report(candidate, retained, mapping)
    quality = candidate_quality_oracle(old_quality, report)
    q01_hashes = {
        "q01_continuation_oracle": file_sha(args.continuation_oracle),
        "q03_reviewed_representation": file_sha(args.reviewed_representation),
        "q04_fixtures_manifest": file_sha(args.fixtures_manifest),
    }
    package_manifest = manifest(
        paths=args,
        reference=reference,
        candidate=candidate,
        report=report,
        old_quality=old_quality,
        quality=quality,
        ocr_summary=ocr_summary,
        q01_hashes=q01_hashes,
        graph_delta=graph_delta,
    )
    split = split_record(reference, candidate, mapping)
    output.mkdir(mode=0o755)
    try:
        copy_exclusive(args.candidate, output / "candidate-reference-09.json")
        write_exclusive(output / "candidate-content-evidence-09.json", report)
        write_exclusive(output / "candidate-quality-oracle.json", quality)
        write_exclusive(output / "split-review.json", split)
        write_exclusive(output / "review-manifest.json", package_manifest)
        output.chmod(0o555)
    except BaseException:
        for child in output.iterdir():
            child.chmod(0o644)
            child.unlink()
        output.chmod(0o755)
        output.rmdir()
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--retained-report", type=Path, required=True)
    parser.add_argument("--quality-oracle", type=Path, required=True)
    parser.add_argument("--original-pdf", type=Path, required=True)
    parser.add_argument("--fixture-pdf", type=Path, required=True)
    parser.add_argument("--ocr-summary", type=Path, required=True)
    parser.add_argument("--continuation-oracle", type=Path, required=True)
    parser.add_argument("--reviewed-representation", type=Path, required=True)
    parser.add_argument("--fixtures-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    build(parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
