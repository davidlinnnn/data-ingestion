"""Inactive, fixture-local validator for the reviewed YOLO graph representation.

The validator proves that one exact candidate graph and its four reviewed source
regions still match the bundle presented to main.  It deliberately cannot turn
a runtime result into PASS; activation requires a separate reviewed change.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


GRAPH_KEYS = (
    "body",
    "furniture",
    "groups",
    "texts",
    "pictures",
    "tables",
    "key_value_items",
    "form_items",
    "pages",
)
EMPTY_OBJECT_KEYS = frozenset({"body", "furniture", "pages"})
SPLIT_FIELDS = frozenset({"self_ref", "text", "orig", "prov"})
REQUIRED_CHECKS = [
    "exactly these two two-node source-preserving splits",
    "joined text, rebased provenance, parent, and reading order equal the historical reference",
    "the normalized complete nine-collection graph equals the historical reference",
    "the 60-cell source table audit and all picture/caption links pass",
    "all four required OCR components have text_detected outcomes",
]
REJECT_ON = [
    "any additional or missing split",
    "any text, provenance geometry, parent, or reading-order difference",
    "any table-cell, picture, caption-link, or other graph difference",
    "any source, reference-graph, actual-graph, or continuation-method identity change",
    "any candidate-inputs or historical-method evidence identity change",
]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def method_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def graph_projection(document: dict[str, Any]) -> dict[str, Any]:
    def clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                ("$ref" if key == "cref" else key): clean(child)
                for key, child in value.items()
                if child is not None
            }
        if isinstance(value, list):
            return [clean(child) for child in value]
        return value

    return clean(
        {
            key: document.get(key, {} if key in EMPTY_OBJECT_KEYS else [])
            for key in GRAPH_KEYS
        }
    )


def graph_sha256(document: dict[str, Any]) -> str:
    return sha256_bytes(canonical(graph_projection(document)).encode())


def ref(value: dict[str, Any]) -> str:
    return value.get("$ref", value.get("cref"))


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label} changed")


def _fragment(node: dict[str, Any], provenance: dict[str, Any]) -> str:
    text = node.get("text")
    if text is not None:
        text = text[slice(*provenance["charspan"])]
    return canonical([node.get("label"), provenance["page_no"], provenance["bbox"], text])


def _fragments(node: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_fragment(node, provenance) for provenance in node.get("prov", []))


def _split_metadata(node: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in node.items() if key not in SPLIT_FIELDS}


def _rebase_provenance(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    offset = 0
    for index, node in enumerate(nodes):
        for provenance in node.get("prov", []):
            shifted = copy.deepcopy(provenance)
            start, end = shifted["charspan"]
            shifted["charspan"] = [offset + start, offset + end]
            result.append(shifted)
        offset += len(node.get("text", ""))
        if index + 1 < len(nodes):
            offset += 1
    return result


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


def _normalize_reviewed_splits(
    reference: dict[str, Any],
    actual: dict[str, Any],
    reviewed: list[tuple[dict[str, Any], list[dict[str, Any]]]],
) -> tuple[dict[str, Any], dict[str, str]]:
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for reference_node, nodes in reviewed:
        for node in nodes:
            if node["self_ref"] in used:
                raise AssertionError("reviewed source fragment is duplicated")
            mapping[node["self_ref"]] = reference_node["self_ref"]
            used.add(node["self_ref"])

    actual_by_fragments: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for node in actual["texts"]:
        if node["self_ref"] not in used:
            actual_by_fragments[_fragments(node)].append(node)
    reviewed_reference = {reference_node["self_ref"] for reference_node, _ in reviewed}
    for reference_node in reference["texts"]:
        if reference_node["self_ref"] in reviewed_reference:
            continue
        matches = [
            node
            for node in actual_by_fragments[_fragments(reference_node)]
            if node["self_ref"] not in used
        ]
        if len(matches) != 1:
            raise AssertionError("unreviewed text mapping is not one-to-one")
        mapping[matches[0]["self_ref"]] = reference_node["self_ref"]
        used.add(matches[0]["self_ref"])
    if used != {node["self_ref"] for node in actual["texts"]}:
        raise AssertionError("additional actual text nodes remain")
    if set(mapping.values()) != {node["self_ref"] for node in reference["texts"]}:
        raise AssertionError("reference text coverage changed")

    primary = {
        nodes[0]["self_ref"]: (reference_node, nodes)
        for reference_node, nodes in reviewed
    }
    secondary = {nodes[1]["self_ref"] for _, nodes in reviewed}
    normalized = _remap(actual, mapping)
    normalized_texts = []
    for node in actual["texts"]:
        if node["self_ref"] in secondary:
            continue
        if node["self_ref"] in primary:
            _, nodes = primary[node["self_ref"]]
            node = copy.deepcopy(node)
            node["text"] = " ".join(item["text"] for item in nodes)
            node["orig"] = " ".join(item["orig"] for item in nodes)
            node["prov"] = _rebase_provenance(nodes)
        normalized_texts.append(_remap(node, mapping))
    normalized["texts"] = normalized_texts
    normalized["body"]["children"] = [
        _remap(child, mapping)
        for child in actual["body"]["children"]
        if ref(child) not in secondary
    ]
    return normalized, mapping


def validate_candidate(
    bundle: dict[str, Any],
    reference: dict[str, Any],
    actual: dict[str, Any],
    *,
    source_bytes: bytes,
    candidate_inputs_bytes: bytes,
    historical_methods_bytes: bytes,
) -> dict[str, Any]:
    require_equal(bundle.get("schema_version"), 1, "bundle schema")
    require_equal(bundle.get("fixture"), "07", "fixture")
    require_equal(bundle.get("status"), "PENDING_MAIN_APPROVAL", "candidate status")
    require_equal(bundle.get("runtime_active"), False, "runtime activation")
    require_equal(bundle.get("acceptance_effect"), "none", "acceptance effect")
    require_equal(bundle.get("required_checks"), REQUIRED_CHECKS, "required checks")
    require_equal(bundle.get("reject_on"), REJECT_ON, "rejection contract")
    require_equal(
        sha256_bytes(Path(__file__).read_bytes()),
        bundle["validator_sha256"],
        "candidate validator",
    )

    identities = bundle["identities"]
    observed = {
        "source_sha256": sha256_bytes(source_bytes),
        "candidate_inputs_sha256": sha256_bytes(candidate_inputs_bytes),
        "historical_methods_file_sha256": sha256_bytes(historical_methods_bytes),
        "historical_reference_graph_sha256": graph_sha256(reference),
        "candidate_graph_sha256": graph_sha256(actual),
    }
    for name, value in observed.items():
        require_equal(value, identities[name], name)

    candidate_inputs = json.loads(candidate_inputs_bytes)
    historical_methods = json.loads(historical_methods_bytes)
    require_equal(len(historical_methods), 1, "historical method inventory")
    historical_key, historical_payload = next(iter(historical_methods.items()))
    require_equal(
        historical_key,
        identities["historical_method_payload_sha256"],
        "historical method key",
    )
    require_equal(method_digest(historical_payload), historical_key, "method payload")
    require_equal(
        candidate_inputs["base_profile"]["method"].get("continuation"),
        identities["candidate_continuation_method"],
        "candidate continuation method",
    )

    reference_texts = {node["self_ref"]: node for node in reference["texts"]}
    actual_texts = {node["self_ref"]: node for node in actual["texts"]}
    body_refs = [ref(child) for child in actual["body"]["children"]]
    reviewed_fragments = 0
    reviewed = []
    require_equal(len(bundle["reviewed_regions"]), 2, "reviewed region count")
    for region in bundle["reviewed_regions"]:
        reference_node = reference_texts[region["reference"]]
        require_equal(
            sha256_bytes(reference_node["text"].encode()),
            region["reference_text_sha256"],
            f"{region['reference']} reference text",
        )
        nodes = [actual_texts[item] for item in region["actual"]]
        require_equal(len(nodes), 2, "reviewed split node count")
        require_equal(
            [sha256_bytes(node["text"].encode()) for node in nodes],
            region["actual_text_sha256"],
            f"{region['reference']} actual texts",
        )
        require_equal(
            [node["prov"] for node in nodes],
            region["source_provenance"],
            f"{region['reference']} source provenance",
        )
        require_equal(
            [ref(node["parent"]) for node in nodes],
            region["parents"],
            f"{region['reference']} parents",
        )
        positions = [body_refs.index(node["self_ref"]) for node in nodes]
        if positions != sorted(positions) or positions[0] == positions[1]:
            raise AssertionError("reviewed reading order is not increasing")
        require_equal(positions, region["reading_order"], "reviewed reading order")
        intervening = []
        node_index = {
            node["self_ref"]: node
            for key in ("groups", "texts", "pictures", "tables")
            for node in actual.get(key, [])
        }
        for item in body_refs[positions[0] + 1 : positions[1]]:
            node = node_index[item]
            intervening.append(
                {
                    "ref": item,
                    "label": node.get("label"),
                    "pages": [entry["page_no"] for entry in node.get("prov", [])],
                }
            )
        require_equal(
            intervening,
            region["intervening_reading_order"],
            "intervening reading order",
        )
        left = nodes[0]["prov"][-1]
        right = nodes[1]["prov"][0]
        exit_bottom = 1 - left["bbox"]["b"] / actual["pages"][str(left["page_no"])][
            "size"
        ]["height"]
        target_top = 1 - right["bbox"]["t"] / actual["pages"][str(right["page_no"])][
            "size"
        ]["height"]
        require_equal(
            {
                "normalized_exit_bottom": exit_bottom,
                "exit_reaches_bottom_threshold_0_8": exit_bottom >= 0.8,
                "normalized_target_top": target_top,
                "target_meets_top_quarter_threshold": target_top <= 0.25,
                "intervening_table": any(
                    item["label"] == "table" for item in intervening
                ),
            },
            region["continuation_policy_boundary"],
            "continuation policy boundary",
        )
        require_equal(
            " ".join(node["text"] for node in nodes),
            reference_node["text"],
            "joined text",
        )
        require_equal(
            " ".join(node["orig"] for node in nodes),
            reference_node["orig"],
            "joined original text",
        )
        require_equal(
            _rebase_provenance(nodes),
            reference_node["prov"],
            "rebased provenance",
        )
        require_equal(
            [_split_metadata(node) for node in nodes],
            [_split_metadata(reference_node), _split_metadata(reference_node)],
            "split metadata",
        )
        reviewed.append((reference_node, nodes))
        reviewed_fragments += len(nodes)

    require_equal(reviewed_fragments, 4, "reviewed source fragment count")
    normalized, mapping = _normalize_reviewed_splits(reference, actual, reviewed)
    require_equal(
        graph_projection(normalized),
        graph_projection(reference),
        "normalized complete graph",
    )
    return {
        "status": "CANDIDATE_VALID",
        "runtime_active": False,
        "runtime_accepted": False,
        "acceptance_effect": "none",
        "fixture": "07",
        "reviewed_regions": len(bundle["reviewed_regions"]),
        "reviewed_source_fragments": reviewed_fragments,
        "normalized_collections": list(GRAPH_KEYS),
        "mapped_actual_texts": len(mapping),
        "identities": observed,
        "next_step": "main approval is required before any runtime integration",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate-inputs", type=Path, required=True)
    parser.add_argument("--historical-methods", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate_candidate(
        json.loads(args.bundle.read_text()),
        json.loads(args.reference.read_text()),
        json.loads(args.actual.read_text()),
        source_bytes=args.source.read_bytes(),
        candidate_inputs_bytes=args.candidate_inputs.read_bytes(),
        historical_methods_bytes=args.historical_methods.read_bytes(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
