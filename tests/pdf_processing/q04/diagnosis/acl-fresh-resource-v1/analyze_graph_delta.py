"""Prove whether an ACL graph delta is only one provenance-preserving split.

This is an offline diagnostic.  It does not redefine the Q04 oracle: an exact
graph mismatch remains a qualification failure even when this proof succeeds.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


COLLECTIONS = (
    "groups",
    "texts",
    "pictures",
    "tables",
    "key_value_items",
    "form_items",
)
GRAPH_KEYS = ("body", "furniture", *COLLECTIONS, "pages")
SPLIT_FIELDS = frozenset({"self_ref", "text", "orig", "prov"})


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fragment(node: dict[str, Any], provenance: dict[str, Any]) -> str:
    text = node.get("text")
    if text is not None:
        text = text[slice(*provenance["charspan"])]
    return _canonical(
        [node.get("label"), provenance["page_no"], provenance["bbox"], text]
    )


def _fragments(node: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_fragment(node, provenance) for provenance in node.get("prov", []))


def _ref(value: dict[str, Any] | None) -> str | None:
    if not value:
        return None
    return value.get("$ref", value.get("cref"))


def _split_metadata(node: dict[str, Any]) -> dict[str, Any]:
    """Fields that a source-region split is not allowed to change or discard."""
    return {key: value for key, value in node.items() if key not in SPLIT_FIELDS}


def _remap(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            normalized_key = "$ref" if key == "cref" else key
            if normalized_key in ("$ref", "self_ref") and isinstance(child, str):
                result[normalized_key] = mapping.get(child, child)
            elif child is not None:
                result[normalized_key] = _remap(child, mapping)
        return result
    if isinstance(value, list):
        return [_remap(child, mapping) for child in value]
    return value


def _without_reviewed_split_edge(
    body: dict[str, Any], split_ids: list[str]
) -> dict[str, Any]:
    """Remove only the second body edge created by the one reviewed split."""
    result = copy.deepcopy(body)
    children = result.get("children", [])
    matches = [
        index
        for index in range(len(children) - 1)
        if [_ref(children[index]), _ref(children[index + 1])] == split_ids
    ]
    if len(matches) != 1:
        raise AssertionError("reviewed split body edge is absent or ambiguous")
    children.pop(matches[0] + 1)
    return result


def rebase_provenance(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    offset = 0
    for index, node in enumerate(nodes):
        text = node.get("text") or ""
        for provenance in node.get("prov", []):
            shifted = copy.deepcopy(provenance)
            start, end = shifted["charspan"]
            shifted["charspan"] = [offset + start, offset + end]
            result.append(shifted)
        offset += len(text)
        if index + 1 < len(nodes):
            offset += 1
    return result


def analyze(reference: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    reference_texts = reference["texts"]
    actual_texts = actual["texts"]
    actual_by_fragments: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for node in actual_texts:
        actual_by_fragments.setdefault(_fragments(node), []).append(node)

    mapping: dict[str, str] = {}
    split: dict[str, Any] | None = None
    actual_position = {node["self_ref"]: index for index, node in enumerate(actual_texts)}

    for reference_node in reference_texts:
        exact = actual_by_fragments.get(_fragments(reference_node), [])
        if len(exact) == 1:
            mapping[exact[0]["self_ref"]] = reference_node["self_ref"]
            continue
        if exact:
            raise AssertionError(f"ambiguous exact provenance match: {reference_node['self_ref']}")

        target_fragments = _fragments(reference_node)
        candidates = []
        for index in range(len(actual_texts) - 1):
            pair = actual_texts[index : index + 2]
            if _fragments(pair[0]) + _fragments(pair[1]) != target_fragments:
                continue
            if " ".join(node.get("text", "") for node in pair) != reference_node.get(
                "text", ""
            ):
                continue
            if " ".join(node.get("orig", "") for node in pair) != reference_node.get(
                "orig", ""
            ):
                continue
            if len({node.get("label") for node in pair}) != 1:
                continue
            if pair[0].get("label") != reference_node.get("label"):
                continue
            if len({_ref(node.get("parent")) for node in pair}) != 1:
                continue
            candidates.append(pair)
        if len(candidates) != 1 or split is not None:
            raise AssertionError(
                f"expected one unique two-node split for {reference_node['self_ref']}"
            )
        pair = candidates[0]
        if _split_metadata(pair[0]) != _split_metadata(pair[1]):
            raise AssertionError(
                "split fragments differ outside self_ref/text/orig/prov"
            )
        for node in pair:
            mapping[node["self_ref"]] = reference_node["self_ref"]
        split = {
            "reference": reference_node["self_ref"],
            "actual": [node["self_ref"] for node in pair],
            "reference_text": reference_node["text"],
            "actual_texts": [node["text"] for node in pair],
            "reference_parent": _ref(reference_node.get("parent")),
            "actual_parents": [_ref(node.get("parent")) for node in pair],
            "reference_provenance": reference_node["prov"],
            "actual_provenance": [node["prov"] for node in pair],
            "rebased_actual_provenance": rebase_provenance(pair),
            "reference_reading_order": reference["body"]["children"].index(
                {"$ref": reference_node["self_ref"]}
            ),
            "actual_reading_order": [
                actual["body"]["children"].index({"$ref": node["self_ref"]})
                for node in pair
            ],
            "actual_text_positions": [actual_position[node["self_ref"]] for node in pair],
        }

    if split is None:
        raise AssertionError("no split found")
    if set(mapping) != {node["self_ref"] for node in actual_texts}:
        raise AssertionError("not every actual text node maps to the reference")
    if set(mapping.values()) != {node["self_ref"] for node in reference_texts}:
        raise AssertionError("not every reference text node has actual provenance")

    # Reconstruct the current graph after the single proven merge and reference
    # renumbering.  The merged node is built from current output; reference data
    # is used only for equality checks below.
    split_ids = split["actual"]
    normalized_texts = []
    index = 0
    while index < len(actual_texts):
        node = actual_texts[index]
        if node["self_ref"] == split_ids[0]:
            pair = actual_texts[index : index + 2]
            if [item["self_ref"] for item in pair] != split_ids:
                raise AssertionError("split nodes are not adjacent in typed order")
            merged = copy.deepcopy(pair[0])
            merged["text"] = " ".join(item.get("text", "") for item in pair)
            merged["orig"] = " ".join(item.get("orig", "") for item in pair)
            merged["prov"] = rebase_provenance(pair)
            normalized_texts.append(_remap(merged, mapping))
            index += 2
            continue
        normalized_texts.append(_remap(node, mapping))
        index += 1

    normalized_actual = {}
    for key in GRAPH_KEYS:
        if key == "texts":
            normalized_actual[key] = normalized_texts
        elif key == "body":
            normalized_actual[key] = _remap(
                _without_reviewed_split_edge(actual.get(key, {}), split_ids),
                mapping,
            )
        else:
            normalized_actual[key] = _remap(
                actual.get(key, {} if key in ("body", "furniture", "pages") else []),
                mapping,
            )
    normalized_reference = {
        key: _remap(
            reference.get(key, {} if key in ("body", "furniture", "pages") else []),
            {},
        )
        for key in GRAPH_KEYS
    }

    raw_changed = [
        key
        for key in GRAPH_KEYS
        if reference.get(key) != actual.get(key)
    ]
    remaining_changed = [
        key for key in GRAPH_KEYS if normalized_reference[key] != normalized_actual[key]
    ]
    split["rebased_provenance_matches_reference"] = (
        split["rebased_actual_provenance"] == split["reference_provenance"]
    )
    result = {
        "verdict": (
            "one_provenance_preserving_split_explains_full_graph_delta"
            if not remaining_changed
            else "additional_graph_differences_remain"
        ),
        "oracle_status": "FAIL_exact_graph_mismatch_unchanged",
        "raw_changed_collections": raw_changed,
        "remaining_changed_collections_after_diagnostic_normalization": remaining_changed,
        "reference_text_count": len(reference_texts),
        "actual_text_count": len(actual_texts),
        "mapped_reference_text_count": len(set(mapping.values())),
        "mapped_actual_text_count": len(mapping),
        "split": split,
        "reference_origin": reference.get("origin"),
        "actual_origin": actual.get("origin"),
        "schema": {
            "reference": [reference.get("schema_name"), reference.get("version")],
            "actual": [actual.get("schema_name"), actual.get("version")],
        },
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = analyze(
        json.loads(args.reference.read_text()), json.loads(args.actual.read_text())
    )
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
    if result["remaining_changed_collections_after_diagnostic_normalization"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
