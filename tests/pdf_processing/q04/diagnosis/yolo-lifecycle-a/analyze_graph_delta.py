"""Offline review of the retained fixture-07 graph-gate failure.

This diagnostic never changes the active reference or turns the failed runtime
attempt into an acceptance pass.  Its narrow normalization exists only to prove
whether a fixed set of source-preserving text splits accounts for the complete
graph delta.
"""

from __future__ import annotations

import argparse
import copy
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import tarfile
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
EXPECTED_ARCHIVE_SHA256 = (
    "5c183da78740cb68cc7114dc06a4e2a7bd890b17c7f7637dd69adc8495bb9bc9"
)
EXPECTED_BATCH_STATE_SHA256 = (
    "f6b607f008354b4b69a62a36bd174bb3e157af18acebe43132d169d61d1686ce"
)
EXPECTED_REFERENCE_FILE_SHA256 = (
    "a3ac9eb345949cdc83423ba1ae38c794400e8f4f89061056c1102517b6a1e6a1"
)
EXPECTED_REFERENCE_GRAPH_SHA256 = (
    "b270e1818bdeecf5f88cc83766c8ab3fa1e89a1586fb0cacbfbf049614a8c276"
)
EXPECTED_ACTUAL_GRAPH_SHA256 = (
    "80c435fc8dc171c6da52a1353195b7221ad2449a518c326efbb0193d9828587d"
)
EXPECTED_SOURCE_SHA256 = (
    "e6bda9784cfd83fd38c92a1162731aa1ec3413dbe1505946611595bfe59f29ab"
)
EXPECTED_INPUTS_SHA256 = (
    "67eba79d6125c536ab728edb4f7d8ee070d8aead49384f4afc3a48c78267d420"
)
EXPECTED_HISTORICAL_METHODS_FILE_SHA256 = (
    "eb58ea3afd15952ef06390d62e3f5fc48f7f213d046e2ca210b11f247b8b83a9"
)
EXPECTED_HISTORICAL_METHOD_SHA256 = (
    "a37699da0a689066bd68fa9067e980272159afb7ae8554ac7dadefd471dabd36"
)
EXPECTED_CONTINUATION_SHA256 = (
    "791e2ebef036d6f2468fb607162a135eecb3c4eaa056d4e35b1a81bffde49772"
)
MAX_CGROUP_BYTES = 4 * 1024**3
EXPECTED_RUNTIME_FILE_SHA256 = {
    "cleanup.json": "7bea7c849b2f757b851b703fe13deb867b98baf498e7171c83276a9da2bdcb85",
    "health-after.json": "6b17064be4e1a88b027c8bbd20dc89734fcef00ee5b767c9d871052df0e1ef66",
    "held-services-before.json": "d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4",
    "held-services-after.json": "d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4",
    "lease-state.json": "babe1b94a84ae8634db6eaeeef701eb0b829bba46099e8e365735fb8eecddd55",
    "admission.json": "c27adac4aae515d470421a5bd5997a8f9127882add1b9b5a11a62f11d0c1ba93",
    "frozen-postcheck.json": "daf464788f3a513509149709ddf93f0c8543fc6b5f9279be78e4fc68f24fcdfb",
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_file_hashes(root: Path, expected: dict[str, str]) -> dict[str, str]:
    observed = {name: file_sha(root / name) for name in expected}
    if observed != expected:
        changed = sorted(name for name in expected if observed[name] != expected[name])
        raise AssertionError(f"retained evidence changed: {changed}")
    return observed


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


def graph_sha(document: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(graph_projection(document)).encode()).hexdigest()


def _ref(value: dict[str, Any] | None) -> str | None:
    if not value:
        return None
    return value.get("$ref", value.get("cref"))


def _references(value: Any):
    if isinstance(value, dict):
        if "$ref" in value or "cref" in value:
            yield _ref(value)
        for child in value.values():
            yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def _fragment(node: dict[str, Any], provenance: dict[str, Any]) -> str:
    text = node.get("text")
    if text is not None:
        text = text[slice(*provenance["charspan"])]
    return canonical(
        [node.get("label"), provenance["page_no"], provenance["bbox"], text]
    )


def _fragments(node: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_fragment(node, provenance) for provenance in node.get("prov", []))


def _split_metadata(node: dict[str, Any]) -> dict[str, Any]:
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


def _reading_orders(document: dict[str, Any], refs: list[str]) -> list[int]:
    children = [_ref(child) for child in document["body"].get("children", [])]
    return [children.index(ref) for ref in refs]


def _find_split(
    reference_node: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    target = _fragments(reference_node)
    matches = []
    for pair in itertools.combinations(candidates, 2):
        for ordered in (list(pair), list(reversed(pair))):
            if _fragments(ordered[0]) + _fragments(ordered[1]) != target:
                continue
            if " ".join(node.get("text", "") for node in ordered) != reference_node.get(
                "text", ""
            ):
                continue
            if " ".join(node.get("orig", "") for node in ordered) != reference_node.get(
                "orig", ""
            ):
                continue
            matches.append(ordered)
    if len(matches) != 1:
        raise AssertionError(
            f"expected one unique two-node split for {reference_node['self_ref']}"
        )
    pair = matches[0]
    reference_metadata = _split_metadata(reference_node)
    if any(_split_metadata(node) != reference_metadata for node in pair):
        raise AssertionError("split metadata differs from the reference")
    return pair


def _normalize(
    actual: dict[str, Any],
    mapping: dict[str, str],
    splits: list[tuple[dict[str, Any], list[dict[str, Any]]]],
) -> dict[str, Any]:
    secondary = {pair[1]["self_ref"] for _, pair in splits}
    primary = {pair[0]["self_ref"]: (reference, pair) for reference, pair in splits}
    normalized = _remap(actual, mapping)

    texts = []
    for node in actual["texts"]:
        if node["self_ref"] in secondary:
            continue
        if node["self_ref"] in primary:
            _, pair = primary[node["self_ref"]]
            node = copy.deepcopy(node)
            node["text"] = " ".join(item.get("text", "") for item in pair)
            node["orig"] = " ".join(item.get("orig", "") for item in pair)
            node["prov"] = _rebase_provenance(pair)
        texts.append(_remap(node, mapping))
    normalized["texts"] = texts

    children = actual["body"].get("children", [])
    remove_once = Counter(secondary)
    normalized_children = []
    for child in children:
        child_ref = _ref(child)
        if remove_once[child_ref]:
            remove_once[child_ref] -= 1
            continue
        normalized_children.append(_remap(child, mapping))
    if any(remove_once.values()):
        raise AssertionError("reviewed split body edge is absent")
    normalized["body"]["children"] = normalized_children
    return normalized


def analyze(
    reference: dict[str, Any],
    actual: dict[str, Any],
    *,
    required_split_count: int = 2,
) -> dict[str, Any]:
    reference_texts = reference["texts"]
    actual_texts = actual["texts"]
    actual_by_fragments: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for node in actual_texts:
        actual_by_fragments[_fragments(node)].append(node)

    mapping: dict[str, str] = {}
    used: set[str] = set()
    unmatched_reference = []
    for reference_node in reference_texts:
        exact = [
            node
            for node in actual_by_fragments[_fragments(reference_node)]
            if node["self_ref"] not in used
        ]
        if len(exact) == 1:
            node = exact[0]
            mapping[node["self_ref"]] = reference_node["self_ref"]
            used.add(node["self_ref"])
        elif exact:
            raise AssertionError(
                f"ambiguous exact provenance match: {reference_node['self_ref']}"
            )
        else:
            unmatched_reference.append(reference_node)

    splits = []
    for reference_node in unmatched_reference:
        candidates = [node for node in actual_texts if node["self_ref"] not in used]
        pair = _find_split(reference_node, candidates)
        splits.append((reference_node, pair))
        for node in pair:
            mapping[node["self_ref"]] = reference_node["self_ref"]
            used.add(node["self_ref"])

    if len(splits) != required_split_count:
        raise AssertionError(
            f"expected {required_split_count} reviewed splits, found {len(splits)}"
        )
    if used != {node["self_ref"] for node in actual_texts}:
        raise AssertionError("not every actual text node maps to the reference")
    if set(mapping.values()) != {node["self_ref"] for node in reference_texts}:
        raise AssertionError("not every reference text node has actual provenance")

    normalized_actual = _normalize(actual, mapping, splits)
    normalized_reference = graph_projection(reference)
    normalized_actual_projection = graph_projection(normalized_actual)
    raw_changed = [
        key
        for key in GRAPH_KEYS
        if graph_projection(reference)[key] != graph_projection(actual)[key]
    ]
    remaining_changed = [
        key
        for key in GRAPH_KEYS
        if normalized_reference[key] != normalized_actual_projection[key]
    ]

    node_index = {
        node["self_ref"]: node
        for key in ("groups", "texts", "pictures", "tables")
        for node in actual.get(key, [])
    }
    body_refs = [_ref(child) for child in actual["body"].get("children", [])]
    split_reports = []
    for reference_node, pair in splits:
        rebased = _rebase_provenance(pair)
        actual_refs = [node["self_ref"] for node in pair]
        actual_orders = _reading_orders(actual, actual_refs)
        left_provenance = pair[0]["prov"][-1]
        right_provenance = pair[1]["prov"][0]
        left_height = actual["pages"][str(left_provenance["page_no"])]["size"][
            "height"
        ]
        right_height = actual["pages"][str(right_provenance["page_no"])]["size"][
            "height"
        ]
        exit_bottom = 1 - left_provenance["bbox"]["b"] / left_height
        target_top = 1 - right_provenance["bbox"]["t"] / right_height
        intervening = [
            {
                "ref": ref,
                "label": node_index[ref].get("label"),
                "pages": [
                    provenance["page_no"]
                    for provenance in node_index[ref].get("prov", [])
                ],
            }
            for ref in body_refs[actual_orders[0] + 1 : actual_orders[1]]
        ]
        split_reports.append(
            {
                "reference": reference_node["self_ref"],
                "actual": actual_refs,
                "reference_text": reference_node["text"],
                "actual_texts": [node["text"] for node in pair],
                "reference_parent": _ref(reference_node.get("parent")),
                "actual_parents": [_ref(node.get("parent")) for node in pair],
                "reference_provenance": reference_node["prov"],
                "actual_provenance": [node["prov"] for node in pair],
                "rebased_actual_provenance": rebased,
                "rebased_provenance_matches_reference": rebased
                == reference_node["prov"],
                "reference_reading_order": _reading_orders(
                    reference, [reference_node["self_ref"]]
                )[0],
                "actual_reading_order": actual_orders,
                "reference_text_position": reference_texts.index(reference_node),
                "actual_text_positions": [actual_texts.index(node) for node in pair],
                "intervening_reading_order": intervening,
                "continuation_policy_boundary": {
                    "normalized_exit_bottom": exit_bottom,
                    "exit_reaches_bottom_threshold_0_8": exit_bottom >= 0.8,
                    "normalized_target_top": target_top,
                    "target_meets_top_quarter_threshold": target_top <= 0.25,
                    "intervening_table": any(
                        item["label"] == "table" for item in intervening
                    ),
                },
            }
        )

    return {
        "verdict": (
            "two_source_preserving_splits_explain_full_graph_delta"
            if len(splits) == 2 and not remaining_changed
            else "additional_graph_differences_remain"
        ),
        "oracle_status": "FAIL_GRAPH_GATE_unchanged",
        "expected_graph_sha256": graph_sha(reference),
        "actual_graph_sha256": graph_sha(actual),
        "raw_changed_collections": raw_changed,
        "remaining_changed_collections_after_diagnostic_normalization": remaining_changed,
        "reference_counts": {
            key: len(reference.get(key, []))
            for key in ("groups", "texts", "pictures", "tables")
        },
        "actual_counts": {
            key: len(actual.get(key, []))
            for key in ("groups", "texts", "pictures", "tables")
        },
        "mapping_counts": {
            "reference_texts": len(reference_texts),
            "actual_texts": len(actual_texts),
            "one_to_two": len(splits),
            "renumbered_actual_refs": sum(
                actual_ref != reference_ref
                for actual_ref, reference_ref in mapping.items()
            ),
        },
        "splits": split_reports,
        "collection_disposition": {
            "body": "two additional split-node reading-order edges",
            "groups": "later text refs renumbered only",
            "texts": "two source-preserving two-node splits plus later ref renumbering",
            "pictures": "caption/text refs renumbered only",
            "tables": "text refs renumbered only; cells unchanged",
            "furniture": "unchanged",
            "key_value_items": "unchanged",
            "form_items": "unchanged",
            "pages": "unchanged",
        },
    }


def validate_graph(document: dict[str, Any]) -> dict[str, Any]:
    nodes = [document[key] for key in ("body", "furniture") if document.get(key)]
    for key in ("groups", "texts", "pictures", "tables", "key_value_items", "form_items"):
        nodes.extend(document.get(key, []))
    index = {node["self_ref"]: node for node in nodes}
    if len(index) != len(nodes):
        raise AssertionError("duplicate document ref")
    dangling = sorted({ref for ref in _references(nodes) if ref not in index})
    if dangling:
        raise AssertionError(f"dangling graph refs: {dangling}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(key: str) -> None:
        if key in visiting:
            raise AssertionError("cyclic children")
        if key in visited:
            return
        visiting.add(key)
        children = [_ref(child) for child in index[key].get("children", [])]
        if len(children) != len(set(children)):
            raise AssertionError("duplicate child")
        for child in children:
            if _ref(index[child].get("parent")) != key:
                raise AssertionError("child parent mismatch")
            visit(child)
        visiting.remove(key)
        visited.add(key)

    for key in index:
        visit(key)
    return {"nodes": len(nodes), "refs": len(index), "dangling": 0, "cycles": 0}


def audit_table(document: dict[str, Any], oracle: list[dict[str, Any]]) -> dict[str, Any]:
    tables = [table for table in document["tables"] if table["data"]["num_rows"] == 15]
    if len(tables) != 1:
        raise AssertionError("ambiguous source-audited table")
    table = tables[0]
    cells = {
        (cell["start_row_offset_idx"], cell["start_col_offset_idx"]): cell
        for cell in table["data"]["table_cells"]
    }
    expected = {(entry["row"], entry["col"]): entry for entry in oracle}
    if set(cells) != set(expected):
        raise AssertionError("table audit coverage")
    normalize = lambda text: " ".join(text.split())
    for key, entry in expected.items():
        cell = cells[key]
        source = (
            entry["parsed_text"]
            if "\x02" in entry["source_text"]
            else entry["source_text"]
        )
        if normalize(cell["text"]) != normalize(source):
            raise AssertionError(f"source-audited cell changed: {key}")
        if cell["row_span"] != entry["rowspan"]:
            raise AssertionError(f"source-audited rowspan changed: {key}")
    return {
        "audited_table": table["self_ref"],
        "audited_table_cells": len(expected),
        "rows": table["data"]["num_rows"],
        "columns": table["data"]["num_cols"],
    }


def _load_json(member: tarfile.ExFileObject | None) -> Any:
    if member is None:
        raise AssertionError("required retained member missing")
    return json.load(member)


def _load_lines(member: tarfile.ExFileObject | None) -> list[dict[str, Any]]:
    if member is None:
        raise AssertionError("required retained member missing")
    return [json.loads(line) for line in member]


def build_runtime_summary(
    archive: Path,
    runtime_root: Path,
    batch_state_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    if file_sha(archive) != EXPECTED_ARCHIVE_SHA256:
        raise AssertionError("retained archive changed")
    if file_sha(batch_state_path) != EXPECTED_BATCH_STATE_SHA256:
        raise AssertionError("retained batch state changed")
    runtime_file_sha256 = verify_file_hashes(
        runtime_root, EXPECTED_RUNTIME_FILE_SHA256
    )
    with tarfile.open(archive) as retained:
        prefix = "./state/yolo-lifecycle-a"
        document = _load_json(retained.extractfile(prefix + "/fresh-07/document.json"))
        result = _load_json(retained.extractfile(prefix + "/fresh-07/result.json"))
        graph_delta = _load_json(
            retained.extractfile(prefix + "/fresh-07/graph-delta.json")
        )
        attribution = _load_lines(
            retained.extractfile(
                "./state/yolo-lifecycle-a-measurement/resource-attribution.jsonl"
            )
        )
        attribution_summary = _load_json(
            retained.extractfile(
                "./state/yolo-lifecycle-a-measurement/resource-attribution-summary.json"
            )
        )
        guard_samples = _load_lines(
            retained.extractfile(prefix + "/worker-1/samples.jsonl")
        )
        trace_member = retained.extractfile("./logs/yolo-lifecycle-a.log")
        if trace_member is None:
            raise AssertionError("retained trace missing")
        trace = trace_member.read().decode()

    warm_fresh_overlap = []
    for index, sample in enumerate(attribution):
        live = {
            process["command_class"]
            for process in sample["processes"]
            if process.get("pss_bytes", 0) > 0
        }
        if "warm_parser" in live and "fresh_parse_child" in live:
            warm_fresh_overlap.append(index)

    batch = json.loads(batch_state_path.read_text())
    cleanup = json.loads((runtime_root / "cleanup.json").read_text())
    health = json.loads((runtime_root / "health-after.json").read_text())
    held_before = (runtime_root / "held-services-before.json").read_bytes()
    held_after = (runtime_root / "held-services-after.json").read_bytes()
    held = json.loads(held_after)
    lease = json.loads((runtime_root / "lease-state.json").read_text())
    outer = json.loads((runtime_root / "admission.json").read_text())
    frozen = json.loads((runtime_root / "frozen-postcheck.json").read_text())

    maximum_guard = max(sample["memory_current"] for sample in guard_samples)
    maximum_attribution = max(sample["memory_current"] for sample in attribution)
    component_steps = [
        step for step in result["steps"] if step["stage"] == "component_ocr"
    ]
    runtime_summary = {
        "status": "FAIL_GRAPH_GATE",
        "acceptance_pass": False,
        "batch": {
            "phase": batch["phase"],
            "completed_phases": batch["completed"],
            "failure": batch["failed"],
            "automatic_retry": batch["automatic_retry"],
            "retry_count": lease["retry_count"],
            "fresh_accepted": result["canonical_accepted"],
            "fresh_processing_complete": result["processing_complete"],
            "restored_ran": False,
            "exact_replay_ran": False,
            "later_fixtures_ran": False,
        },
        "graph_gate": graph_delta,
        "delivery_before_graph_gate": {
            "pages": result["pages"],
            "registered_pages": result["registered_pages"],
            "selected_components": result["selected_components"],
            "registered_components": result["registered_components"],
            "component_ocr": [
                {"component": step["component"], "outcome": step["outcome"]}
                for step in component_steps
            ],
            "pre_graph_consumer_checks_passed": (
                "Consumer(self.store, target).verify" in trace
                and "check_reference(document, reference" in trace
            ),
        },
        "outer_admission": outer,
        "guards": {
            "max_cgroup_bytes": MAX_CGROUP_BYTES,
            "samples": len(guard_samples),
            "maximum_sampled_memory_current_bytes": maximum_guard,
            "sampled_guard_crossed": maximum_guard > MAX_CGROUP_BYTES,
            "minimum_available_bytes": min(
                sample["available"] for sample in guard_samples
            ),
            "maximum_full_psi_avg10": max(
                sample["psi_full_avg10"] for sample in guard_samples
            ),
            "memory_events_max": {
                key: max(sample["memory_events"][key] for sample in guard_samples)
                for key in guard_samples[0]["memory_events"]
            },
        },
        "resource_attribution": {
            "samples": len(attribution),
            "maximum_memory_current_bytes": maximum_attribution,
            "maximum_owned_pss_bytes": max(
                sample["owned_pss_total_bytes"] for sample in attribution
            ),
            "maximum_gap_seconds": attribution_summary["maximum_gap_seconds"],
            "incomplete_samples": attribution_summary["incomplete_samples"],
            "peak_sample_attribution_complete": attribution_summary[
                "peak_sample_attribution_complete"
            ],
            "required_observations_in_order": attribution_summary[
                "required_observations_in_order"
            ],
            "handoff_observed": "warm_handoff_observed"
            in attribution_summary["observed_observation_labels"],
            "no_warm_fresh_overlap": not warm_fresh_overlap,
            "warm_fresh_overlap_sample_indexes": warm_fresh_overlap,
            "diagnostic_peak_exceeds_active_guard_bytes": max(
                0, maximum_attribution - MAX_CGROUP_BYTES
            ),
        },
        "cleanup": {
            "verified": lease["cleanup_verified"],
            "reservation_released": lease["reservation_released"],
            "errors": cleanup["errors"],
            "current_scratch_remaining": cleanup["current_scratch_remaining"],
            "running_after_cleanup": cleanup["running_after_cleanup"],
            "unexpected_active_processes": cleanup["unexpected_active_processes"],
            "unexpected_active_workflows": cleanup["unexpected_active_workflows"],
            "health": health,
        },
        "held_services": {
            "count": len(held),
            "all_expected_uids": all(
                deployment["uid"] == deployment["expected_uid"] for deployment in held
            ),
            "all_closed": all(
                deployment["replicas"] == 0 and deployment["ready"] == 0
                for deployment in held
            ),
            "before_after_byte_identical": held_before == held_after,
            "before_after_sha256": hashlib.sha256(held_after).hexdigest(),
            "restored": lease["services_restored"],
        },
        "retained_evidence": {
            "archive_sha256": file_sha(archive),
            "archive_bytes": archive.stat().st_size,
            "batch_state_sha256": file_sha(batch_state_path),
            "runtime_files_sha256": runtime_file_sha256,
            "frozen_state_unchanged": lease["frozen_state_unchanged"],
            "source_state_unchanged": lease["source_state_unchanged"],
            "frozen_postcheck": frozen,
        },
    }
    return runtime_summary, document, trace


def source_review(
    source_pdf: Path,
    splits: list[dict[str, Any]],
) -> dict[str, Any]:
    if file_sha(source_pdf) != EXPECTED_SOURCE_SHA256:
        raise AssertionError("fixture-07 source changed")
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(source_pdf)
    pages = [pdf[index].get_textpage().get_text_range() for index in range(len(pdf))]
    compact = lambda text: "".join(character.lower() for character in text if character.isalnum())
    checks = []
    for split in splits:
        for text, provenance in zip(split["actual_texts"], split["actual_provenance"]):
            page = provenance[0]["page_no"]
            checks.append(
                {
                    "page": page,
                    "text_present_in_source_extraction": compact(text)
                    in compact(pages[page - 1]),
                }
            )
    if not all(check["text_present_in_source_extraction"] for check in checks):
        raise AssertionError("reviewed split text missing from source PDF")
    return {
        "source_sha256": file_sha(source_pdf),
        "pages": len(pdf),
        "split_fragment_source_checks": checks,
        "rendered_pages_reviewed": [2, 3, 8, 9],
    }


def compare_method_payloads(
    historical: dict[str, Any], candidate_method: dict[str, Any]
) -> dict[str, Any]:
    if len(historical) != 1:
        raise AssertionError("historical method inventory changed")
    historical_sha, historical_method = next(iter(historical.items()))
    if historical_sha != EXPECTED_HISTORICAL_METHOD_SHA256:
        raise AssertionError("historical method identity changed")
    method_digest = hashlib.sha256(
        json.dumps(historical_method, sort_keys=True).encode()
    ).hexdigest()
    if method_digest != historical_sha:
        raise AssertionError("historical method payload digest changed")
    continuation = candidate_method.get("continuation")
    if continuation != {
        "sha256": EXPECTED_CONTINUATION_SHA256,
        "version": "column-edge-continuation-v1",
    }:
        raise AssertionError("candidate continuation method identity changed")
    candidate_without_continuation = {
        key: value for key, value in candidate_method.items() if key != "continuation"
    }
    if historical_method != candidate_without_continuation:
        raise AssertionError("non-continuation method fields changed")
    return {
        "historical_method_sha256": historical_sha,
        "historical_has_continuation_attestation": "continuation" in historical_method,
        "candidate_continuation": continuation,
        "all_non_continuation_fields_equal": historical_method
        == candidate_without_continuation,
        "cause_boundary": (
            "historical_reference_used_upstream_reading-order_merges; candidate "
            "attests conservative column-edge-continuation-v1"
        ),
    }


def compare_methods(historical_methods: Path, candidate_inputs: Path) -> dict[str, Any]:
    if file_sha(historical_methods) != EXPECTED_HISTORICAL_METHODS_FILE_SHA256:
        raise AssertionError("historical methods file changed")
    if file_sha(candidate_inputs) != EXPECTED_INPUTS_SHA256:
        raise AssertionError("candidate inputs file changed")
    historical = json.loads(historical_methods.read_text())
    candidate_method = json.loads(candidate_inputs.read_text())["base_profile"]["method"]
    result = compare_method_payloads(historical, candidate_method)
    result["historical_methods_file_sha256"] = file_sha(historical_methods)
    result["candidate_inputs_sha256"] = file_sha(candidate_inputs)
    return result


def build_local_oracle_proposal(graph: dict[str, Any]) -> dict[str, Any]:
    """Describe the reviewed equivalence without activating it as an oracle."""

    reviewed_regions = []
    for split in graph["splits"]:
        reviewed_regions.append(
            {
                "reference": split["reference"],
                "actual": split["actual"],
                "reference_text_sha256": hashlib.sha256(
                    split["reference_text"].encode()
                ).hexdigest(),
                "actual_text_sha256": [
                    hashlib.sha256(text.encode()).hexdigest()
                    for text in split["actual_texts"]
                ],
                "source_provenance": split["actual_provenance"],
                "parents": split["actual_parents"],
                "reading_order": split["actual_reading_order"],
                "intervening_reading_order": split["intervening_reading_order"],
                "continuation_policy_boundary": split[
                    "continuation_policy_boundary"
                ],
            }
        )

    return {
        "status": "PROPOSAL_NOT_ACTIVE",
        "acceptance_effect": "none",
        "fixture": "07",
        "source_sha256": graph["source_review"]["source_sha256"],
        "historical_reference_graph_sha256": graph["expected_graph_sha256"],
        "candidate_graph_sha256": graph["actual_graph_sha256"],
        "candidate_inputs_sha256": graph["method_comparison"][
            "candidate_inputs_sha256"
        ],
        "historical_methods_file_sha256": graph["method_comparison"][
            "historical_methods_file_sha256"
        ],
        "historical_method_payload_sha256": graph["method_comparison"][
            "historical_method_sha256"
        ],
        "candidate_continuation_method": graph["method_comparison"][
            "candidate_continuation"
        ],
        "reviewed_regions": reviewed_regions,
        "required_checks": [
            "exactly these two two-node source-preserving splits",
            "joined text, rebased provenance, parent, and reading order equal the historical reference",
            "the normalized complete nine-collection graph equals the historical reference",
            "the 60-cell source table audit and all picture/caption links pass",
            "all four required OCR components have text_detected outcomes",
        ],
        "reject_on": [
            "any additional or missing split",
            "any text, provenance geometry, parent, or reading-order difference",
            "any table-cell, picture, caption-link, or other graph difference",
            "any source, reference-graph, actual-graph, or continuation-method identity change",
            "any candidate-inputs or historical-method evidence identity change",
        ],
        "historical_runtime_disposition": "FAIL_GRAPH_GATE_unchanged",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--batch-state", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--historical-methods", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    reference_path = args.bundle / "references/07.json"
    if file_sha(reference_path) != EXPECTED_REFERENCE_FILE_SHA256:
        raise AssertionError("fixture-07 reference changed")
    runtime, document, _ = build_runtime_summary(
        args.archive, args.runtime_root, args.batch_state
    )
    reference = json.loads(reference_path.read_text())
    graph = analyze(reference, document, required_split_count=2)
    if graph["expected_graph_sha256"] != EXPECTED_REFERENCE_GRAPH_SHA256:
        raise AssertionError("reference graph identity changed")
    if graph["actual_graph_sha256"] != EXPECTED_ACTUAL_GRAPH_SHA256:
        raise AssertionError("retained actual graph identity changed")
    if graph["remaining_changed_collections_after_diagnostic_normalization"]:
        raise AssertionError("additional graph differences remain")

    graph["post_run_document_checks"] = {
        "graph_structure": validate_graph(document),
        **audit_table(
            document,
            json.loads((args.bundle / "oracles/07-table-full-audit.json").read_text()),
        ),
        "captions": sum(node.get("label") == "caption" for node in document["texts"]),
        "caption_linkage_equal_after_diagnostic_normalization": True,
        "required_ocr": runtime["delivery_before_graph_gate"]["registered_components"],
        "required_ocr_outcomes": runtime["delivery_before_graph_gate"]["component_ocr"],
        "boundary": "post-run document review; not runtime acceptance",
    }
    graph["source_review"] = source_review(
        args.bundle / "originals/07.pdf", graph["splits"]
    )
    graph["method_comparison"] = compare_methods(
        args.historical_methods, args.bundle / "inputs.json"
    )
    graph["recommended_disposition"] = {
        "kind": "local_source_reviewed_equivalent_representation_oracle",
        "reason": (
            "The current attested continuation policy intentionally preserves two "
            "table-interrupted cross-page paragraphs as two nodes. Both fragments "
            "are source-backed and the complete graph equals the historical graph "
            "after only those two reviewed merges and ref renumbering."
        ),
        "constraints": [
            "retain this runtime attempt as FAIL_GRAPH_GATE",
            "do not replace or rewrite the historical reference",
            "bind any future local oracle to these four source regions and the current continuation method",
            "reject any text, provenance, parent, reading-order, table-cell, picture/caption, or additional graph delta",
        ],
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "full-semantic-delta.json").write_text(
        json.dumps(graph, indent=2, ensure_ascii=False) + "\n"
    )
    (args.output_dir / "runtime-summary.json").write_text(
        json.dumps(runtime, indent=2, ensure_ascii=False) + "\n"
    )
    (args.output_dir / "local-oracle-proposal.json").write_text(
        json.dumps(build_local_oracle_proposal(graph), indent=2, ensure_ascii=False)
        + "\n"
    )


if __name__ == "__main__":
    main()
