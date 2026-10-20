"""Source-only G2 crop planning: ``plan(document)`` returns jobs and dispositions.

Only rows with ``status == 'ready'`` are inference jobs. ``target_item_refs``
are replacement identities; ``context_only_refs`` must never be replaced by
that job. Formula children have a ``member`` disposition pointing to their
parent-envelope job. Every eligible text item remains in the returned inventory.
Run this file directly for synthetic assert checks; it performs no file reads.
"""

from copy import deepcopy
import json
import math


CONFIG = {
    "name": "g2-context-source-structural-v1",
    "ordinary_selection": "all_body_layer_text_items",
    "formula_envelope": "all_direct_children_formula_unique_reciprocal_ownership_one_page",
    "code_context": "consecutive_siblings_same_parent_single_page_single_provenance_per_item",
    "left_alignment_points": 2,
    "code_gap_points": 14,
    "paragraph_context_gap_points": 4,
    "paragraph_context": "immediate_sibling_whole_text_or_formula_same_page_aligned_no_merge",
    "multiprovenance": "complete_charspan_coverage_whitespace_gaps_and_strictly_increasing_pages; same_page_multiple_fragments_abstain",
    "target_identity": "one_native_item_per_job_except_verified_formula_picture_envelope",
    "lexical_selection_gate": False,
}


def _refs(item):
    return [child.get("$ref") for child in item.get("children", [])]


def _union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _fragments(document, item):
    """Retain every provider provenance, rejecting unverifiable coordinates."""
    fragments = []
    for index, prov in enumerate(item.get("prov", [])):
        try:
            page_no = prov["page_no"]
            size = document["pages"][str(page_no)]["size"]
            width, height = size["width"], size["height"]
            box = prov["bbox"]
            if box["coord_origin"] == "TOPLEFT":
                bounds = [box["l"], box["t"], box["r"], box["b"]]
            elif box["coord_origin"] == "BOTTOMLEFT":
                bounds = [box["l"], height - box["t"], box["r"], height - box["b"]]
            else:
                return fragments, "unknown_coordinate_origin"
            if (not isinstance(page_no, int) or isinstance(page_no, bool) or page_no < 1
                    or not all(isinstance(n, (int, float)) and not isinstance(n, bool)
                               and math.isfinite(n) for n in [width, height, *bounds])
                    or not 0 <= bounds[0] < bounds[2] <= width
                    or not 0 <= bounds[1] < bounds[3] <= height):
                return fragments, "invalid_source_geometry"
            fragments.append({"physical_page_1based": page_no,
                              "bbox_top_left_points": bounds,
                              "source_refs": [item["self_ref"]],
                              "provider_provenance_index": index,
                              "provider_provenance": deepcopy(prov)})
        except (KeyError, TypeError, ValueError):
            return fragments, "missing_or_invalid_source_geometry"
    return fragments, None if fragments else "missing_source_provenance"


def _text_problem(item, fragments):
    text = item.get("text")
    if not isinstance(text, str):
        return "missing_native_text"
    cursor = 0
    for fragment in fragments:
        span = fragment["provider_provenance"].get("charspan")
        if (not isinstance(span, list) or len(span) != 2
                or not all(isinstance(n, int) and not isinstance(n, bool) for n in span)):
            return "invalid_provider_charspan"
        start, end = span
        if not cursor <= start <= end <= len(text) or text[cursor:start].strip():
            return "overlapping_or_incomplete_provider_charspans"
        cursor = end
    if text[cursor:].strip():
        return "unlocated_native_text"
    if len(fragments) > 1:
        pages = [f["physical_page_1based"] for f in fragments]
        if len(set(pages)) != len(pages):
            return "same_page_multiple_fragments_have_unproven_paragraph_or_column_boundary"
        if pages != sorted(pages):
            return "provider_charspan_order_disagrees_with_page_order"
    return None


def _eligible(item):
    return (item.get("label") in {"formula", "code"}
            or (item.get("label") == "text" and item.get("content_layer") == "body"))


def _row(item, kind, fragments):
    reference = item["self_ref"]
    return {"id": kind + "--" + reference.removeprefix("#/").replace("/", "-"),
            "kind": kind, "status": "ready", "reason": "whole_native_item",
            "target_item_refs": [reference], "member_item_refs": [], "context_only_refs": [],
            "targets": [{"item_ref": reference, "native_label": item.get("label"),
                         "replacement_charspan": [0, len(item["text"])] if isinstance(item.get("text"), str) else None}],
            "source_fragments": deepcopy(fragments),
            "source_accounting": [{"item_ref": reference, "role": "target",
                                   "provider_provenance": deepcopy(item.get("prov", []))}],
            "replacement_policy": "preserve_native_item_identity"}


def plan(document):
    """Inventory all native body text/formula/code, without source-name gates.

    Complete cross-page paragraphs retain their full text and all fragments.
    Same-page multi-fragment paragraphs remain explicit abstentions, since the
    provider alone does not establish their column or semantic boundary.
    """
    all_items = [document[key] for key in ("body", "furniture") if key in document]
    for key in ("groups", "texts", "pictures", "tables", "key_value_items", "form_items"):
        all_items.extend(document.get(key, []))
    by_ref = {item["self_ref"]: item for item in all_items}
    owners = {}
    for parent in all_items:
        for reference in _refs(parent):
            owners.setdefault(reference, []).append(parent["self_ref"])

    def ownership_problem(item):
        reference = item["self_ref"]
        parent_ref = item.get("parent", {}).get("$ref")
        if sum(other["self_ref"] == reference for other in all_items) != 1:
            return "duplicate_native_item_identity"
        if parent_ref not in by_ref or owners.get(reference) != [parent_ref]:
            return "ownership_is_not_unique_and_reciprocal"
        return None

    geometry = {reference: _fragments(document, item)
                for reference, item in by_ref.items() if item.get("prov") is not None}
    rows, formula_members = [], {}
    for picture in document.get("pictures", []):
        children = [by_ref.get(reference) for reference in _refs(picture)]
        if not any(child and child.get("label") == "formula" for child in children):
            continue
        fragments, problem = geometry.get(picture["self_ref"], ([], "missing_source_provenance"))
        row = _row(picture, "formula_envelope", fragments)
        row["replacement_policy"] = "replace_verified_formula_picture_container"
        problem = problem or ownership_problem(picture)
        if not children or any(child is None or child.get("label") != "formula" for child in children):
            problem = problem or "formula_picture_contains_unverified_or_nonformula_children"
        member_fragments = []
        for child in children:
            if child is None or child.get("label") != "formula":
                continue
            reference = child["self_ref"]
            row["member_item_refs"].append(reference)
            child_fragments, child_problem = geometry.get(reference, ([], "missing_source_provenance"))
            problem = problem or child_problem or ownership_problem(child)
            problem = problem or _text_problem(child, child_fragments)
            row["source_accounting"].append({"item_ref": reference, "role": "member",
                                             "provider_provenance": deepcopy(child.get("prov", []))})
            member_fragments.extend(child_fragments)
            formula_members[reference] = row
        all_fragments = fragments + member_fragments
        if len({fragment["physical_page_1based"] for fragment in all_fragments}) != 1:
            problem = problem or "formula_envelope_ownership_spans_multiple_pages"
        if problem:
            row.update(status="abstain", reason=problem, source_fragments=deepcopy(all_fragments))
        else:
            row["source_fragments"] = [{"physical_page_1based": all_fragments[0]["physical_page_1based"],
                                        "bbox_top_left_points": _union([f["bbox_top_left_points"] for f in all_fragments]),
                                        "source_refs": [picture["self_ref"], *row["member_item_refs"]]}]
            row["reason"] = "verified_formula_picture_and_all_formula_children_union"
        rows.append(row)

    for item in document.get("texts", []):
        if not _eligible(item):
            continue
        reference = item["self_ref"]
        kind = {"text": "ordinary_paragraph", "code": "code_item", "formula": "formula"}[item["label"]]
        fragments, problem = geometry.get(reference, ([], "missing_source_provenance"))
        row = _row(item, kind, fragments)
        if reference in formula_members:
            envelope = formula_members[reference]
            row.update(status="member", job_id=envelope["id"],
                       reason="inventoried_formula_child_owned_by_parent_envelope",
                       envelope_status=envelope["status"])
            rows.append(row)
            continue
        problem = problem or ownership_problem(item) or _text_problem(item, fragments)
        if problem:
            row.update(status="abstain", reason=problem)
        elif item.get("parent", {}).get("$ref", "").startswith("#/pictures/"):
            row.update(status="unsupported", reason="picture_child_is_not_a_proven_independent_paragraph_or_code_target")
        rows.append(row)

    ready = {row["target_item_refs"][0]: row for row in rows if row["status"] == "ready"}

    def adjacent(left, right, gap):
        if left not in ready or right not in ready:
            return False
        a, b = geometry[left][0], geometry[right][0]
        if len(a) != 1 or len(b) != 1 or a[0]["physical_page_1based"] != b[0]["physical_page_1based"]:
            return False
        box_a, box_b = a[0]["bbox_top_left_points"], b[0]["bbox_top_left_points"]
        return (abs(box_a[0] - box_b[0]) <= CONFIG["left_alignment_points"]
                and 0 <= box_b[1] - box_a[3] <= gap)

    def add_context(row, references, reason):
        row["context_only_refs"] = references
        row["reason"] = reason
        for reference in references:
            item = by_ref[reference]
            row["source_accounting"].append({"item_ref": reference, "role": "context_only",
                                             "provider_provenance": deepcopy(item.get("prov", []))})
            row["source_fragments"].extend(deepcopy(geometry[reference][0]))
        row["source_fragments"].sort(key=lambda f: (f["physical_page_1based"],
                                                   f["bbox_top_left_points"][1],
                                                   f["bbox_top_left_points"][0]))

    for parent in all_items:
        siblings = _refs(parent)
        for index, reference in enumerate(siblings):
            if reference not in ready:
                continue
            row = ready[reference]
            if row["kind"] == "code_item":
                start, end = index, index
                while (start > 0 and by_ref.get(siblings[start - 1], {}).get("label") == "code"
                       and adjacent(siblings[start - 1], siblings[start], CONFIG["code_gap_points"])):
                    start -= 1
                while (end + 1 < len(siblings) and by_ref.get(siblings[end + 1], {}).get("label") == "code"
                       and adjacent(siblings[end], siblings[end + 1], CONFIG["code_gap_points"])):
                    end += 1
                contexts = [r for r in siblings[start:end + 1] if r != reference]
                if contexts:
                    add_context(row, contexts, "adjacent_code_run_context_with_one_native_target")
            elif row["kind"] == "ordinary_paragraph" and len(row["source_fragments"]) == 1:
                contexts = []
                for before, after in ((index - 1, index), (index, index + 1)):
                    if before < 0 or after >= len(siblings):
                        continue
                    neighbor = siblings[before] if after == index else siblings[after]
                    other = by_ref.get(neighbor, {})
                    if (other.get("label") in {"text", "formula"}
                            and adjacent(siblings[before], siblings[after], CONFIG["paragraph_context_gap_points"])):
                        contexts.append(neighbor)
                if contexts:
                    add_context(row, contexts, "whole_immediate_sibling_context_with_one_native_paragraph_target")
    return rows


def selfcheck():
    """Small synthetic fixtures exercise policy independently of paper fixtures."""
    def text(reference, label="text", box=(10, 10, 40, 20), page=1, value="plain prose", parent="#/body"):
        return {"self_ref": reference, "label": label, "content_layer": "body", "text": value,
                "parent": {"$ref": parent}, "children": [],
                "prov": [{"page_no": page, "bbox": dict(zip(("l", "t", "r", "b"), box), coord_origin="TOPLEFT"),
                          "charspan": [0, len(value)]}]}

    def doc(items, pictures=None):
        pictures = pictures or []
        return {"name": "unrelated-case", "body": {"self_ref": "#/body", "children": [
                    {"$ref": i["self_ref"]} for i in items + pictures if i["parent"]["$ref"] == "#/body"]},
                "texts": items, "pictures": pictures, "pages": {
                    str(p): {"size": {"width": 200, "height": 200}} for p in (1, 2)}}

    checks = []
    ordinary = doc([text("#/texts/9")])
    row = plan(ordinary)[0]
    assert row["status"] == "ready" and row["targets"][0]["replacement_charspan"] == [0, 11]
    translated = deepcopy(ordinary)
    translated["name"] = "anything-else"
    translated["texts"][0]["text"] = "普通的一段文字"
    translated["texts"][0]["prov"][0]["charspan"] = [0, 7]
    assert plan(translated)[0]["status"] == row["status"]
    checks.append("ordinary_inventory_has_no_document_id_or_character_gate")

    formula = text("#/texts/91", "formula", box=(10, 10, 50, 25), value="x", parent="#/pictures/7")
    picture = {"self_ref": "#/pictures/7", "label": "picture", "parent": {"$ref": "#/body"},
               "children": [{"$ref": formula["self_ref"]}], "prov": [
                   {"page_no": 1, "bbox": {"l": 20, "t": 12, "r": 45, "b": 23, "coord_origin": "TOPLEFT"}}]}
    formula_doc = doc([formula], [picture])
    envelope, member = plan(formula_doc)
    assert envelope["source_fragments"][0]["bbox_top_left_points"] == [10, 10, 50, 25]
    assert member["status"] == "member" and member["job_id"] == envelope["id"]
    broken = deepcopy(formula_doc)
    broken["texts"][0]["parent"] = {"$ref": "#/body"}
    assert plan(broken)[0]["status"] == "abstain"
    broken = deepcopy(formula_doc)
    broken["texts"][0]["prov"][0]["page_no"] = 2
    assert plan(broken)[0]["status"] == "abstain"
    moved = deepcopy(formula_doc)
    for item in moved["texts"] + moved["pictures"]:
        for prov in item["prov"]:
            for coordinate in ("l", "t", "r", "b"):
                prov["bbox"][coordinate] += 15
    assert plan(moved)[0]["source_fragments"][0]["bbox_top_left_points"] == [25, 25, 65, 40]
    checks.append("formula_envelope_requires_reciprocal_ownership_and_one_page")
    checks.append("formula_union_is_invariant_under_coordinate_translation")

    a, b = text("#/texts/50", "code"), text("#/texts/60", "code", box=(10, 22, 40, 32))
    code_rows = plan(doc([a, b]))
    assert all(r["status"] == "ready" and len(r["target_item_refs"]) == 1 for r in code_rows)
    assert code_rows[0]["context_only_refs"] == [b["self_ref"]]
    assert code_rows[1]["context_only_refs"] == [a["self_ref"]]
    assert all(not set(r["target_item_refs"]) & set(r["context_only_refs"]) for r in code_rows)
    third = text("#/texts/70", "code", box=(10, 35, 40, 45))
    code_doc = doc([a, b, third])
    original = deepcopy(code_doc)
    assert all(len(r["context_only_refs"]) == 2 for r in plan(code_doc))
    assert code_doc == original
    checks.append("adjacent_code_context_preserves_separate_target_identity")
    checks.append("planning_retains_full_code_runs_without_mutating_source")

    crosspage = text("#/texts/80", value="first second")
    crosspage["prov"][0]["charspan"] = [0, 5]
    second = deepcopy(crosspage["prov"][0])
    second.update(page_no=2, charspan=[6, 12])
    crosspage["prov"].append(second)
    multipage_row = plan(doc([crosspage]))[0]
    assert multipage_row["status"] == "ready" and len(multipage_row["source_fragments"]) == 2
    assert multipage_row["targets"][0]["replacement_charspan"] == [0, 12]
    samepage = deepcopy(crosspage)
    samepage["prov"][1]["page_no"] = 1
    assert plan(doc([samepage]))[0]["status"] == "abstain"
    missing = deepcopy(crosspage)
    missing["prov"][1]["charspan"] = [7, 12]
    assert plan(doc([missing]))[0]["status"] == "abstain"
    checks.append("complete_crosspage_spans_ready_samepage_ambiguity_and_missing_text_abstain")

    paragraph = text("#/texts/101", value="introductory text")
    following = text("#/texts/102", "formula", box=(10, 22, 40, 32), value="y")
    paragraph_rows = plan(doc([paragraph, following]))
    assert paragraph_rows[0]["context_only_refs"] == [following["self_ref"]]
    assert paragraph_rows[0]["target_item_refs"] == [paragraph["self_ref"]]
    assert paragraph_rows[1]["target_item_refs"] == [following["self_ref"]]
    assert paragraph_rows[0]["targets"][0]["replacement_charspan"] == [0, len(paragraph["text"])]
    checks.append("ordinary_context_is_whole_item_and_never_a_replacement_target")
    return {"passed": True, "checks": checks, "config": CONFIG, "fixture_file_reads": 0}


if __name__ == "__main__":
    print(json.dumps(selfcheck(), ensure_ascii=False, indent=2))
