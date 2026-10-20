"""Independent, stdlib-only checks of saved heading-stage artifacts; no inference."""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[4]
WORK = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
FROZEN_SHA = "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
MISSING = {"missing_key": True}


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def differences(left, right, path=""):
    if type(left) is not type(right):
        return [{"path": path, "before": left, "after": right}]
    if isinstance(left, dict):
        changes = []
        for key in sorted(left.keys() | right.keys()):
            if key not in left or key not in right:
                changes.append({"path": f"{path}/{key}", "before": left.get(key, MISSING),
                                "after": right.get(key, MISSING)})
            else:
                changes.extend(differences(left[key], right[key], f"{path}/{key}"))
        return changes
    if isinstance(left, list):
        if len(left) != len(right):
            return [{"path": path, "before": left, "after": right}]
        return [change for i, pair in enumerate(zip(left, right))
                for change in differences(*pair, f"{path}/{i}")]
    return [] if left == right else [{"path": path, "before": left, "after": right}]


def normalize_load(value):
    if isinstance(value, dict):
        return {("$ref" if key == "cref" else key): normalize_load(item)
                for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [normalize_load(item) for item in value]
    return value


def ref(value):
    return value.get("cref", value.get("$ref")) if value else None


def graph(document):
    nodes = {document[name]["self_ref"]: document[name] for name in ("body", "furniture")}
    for name in ("texts", "groups", "pictures", "tables", "key_value_items", "form_items"):
        for node in document.get(name, []):
            assert node["self_ref"] not in nodes, "duplicate self_ref"
            nodes[node["self_ref"]] = node
    errors, ordered = [], []

    def visit(node_ref, ancestors):
        if node_ref in ancestors:
            errors.append(f"cycle: {node_ref}")
            return
        if node_ref not in nodes:
            errors.append(f"unresolved child: {node_ref}")
            return
        ordered.append(node_ref)
        for child in nodes[node_ref].get("children", []):
            child_ref = ref(child)
            if child_ref in nodes and ref(nodes[child_ref].get("parent")) != node_ref:
                errors.append(f"parent mismatch: {child_ref}")
            visit(child_ref, ancestors | {node_ref})

    for root in ("#/body", "#/furniture"):
        visit(root, set())
    counts = Counter(ordered)
    errors.extend(f"tree multiplicity {key}: {n}" for key, n in counts.items() if n != 1)
    errors.extend(f"unreachable item: {key}" for key in nodes.keys() - counts.keys())
    return {"errors": errors, "order": ordered, "nodes": nodes}


def headings(document):
    tree = graph(document)
    rows, stack = [], []
    title = None
    for node_ref in tree["order"]:
        item = tree["nodes"][node_ref]
        if item.get("label") == "title":
            title, stack = node_ref, []
            level, parent = 0, "#/body"
        elif item.get("label") == "section_header":
            level = item["level"]
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else title or "#/body"
            stack.append((level, node_ref))
        else:
            continue
        rows.append({"ref": node_ref, "title": item["text"], "label": item["label"],
                     "level": level, "inferred_parent": parent,
                     "actual_parent": ref(item.get("parent")),
                     "pages": [p["page_no"] for p in item.get("prov", [])]})
    return rows


def stage_audit(before, after):
    delta = differences(before, after)
    bad = []
    for change in delta:
        match = re.fullmatch(r"/texts/(\d+)/level", change["path"])
        if (not match or before["texts"][int(match[1])].get("label") != "section_header"
                or type(change["after"]) is not int or not 1 <= change["after"] <= 6):
            bad.append(change)
    a, b = graph(before), graph(after)
    return {"changes": len(delta), "all_changes": delta, "unexpected_changes": bad,
            "only_existing_section_header_levels_changed": not bad,
            "tree_order_identical": a["order"] == b["order"],
            "before_graph_errors": a["errors"], "after_graph_errors": b["errors"],
            "counts": {name: len(after.get(name, [])) for name in
                       ("texts", "groups", "pictures", "tables")}}


def score(document, expected):
    rows = headings(document)
    number_refs = {re.match(r"^([A-Z]|\d+)(?:\.\d+)*", row["title"])[0]: row["ref"]
                   for row in rows if re.match(r"^([A-Z]|\d+)(?:\.\d+)*\.", row["title"])}
    title_refs = {row["title"]: row["ref"] for row in rows}
    result, positions = [], []
    for wanted in expected:
        found = [(i, row) for i, row in enumerate(rows) if row["title"] == wanted["title"]]
        row = found[0][1] if len(found) == 1 else None
        parent = wanted.get("parent_number")
        expected_parent = number_refs.get(parent) if parent else "#/body"
        if wanted.get("parent_title"):
            expected_parent = title_refs.get(wanted["parent_title"])
        result.append({"expected": wanted, "observed": row, "unique_heading": len(found) == 1,
                       "page_correct": bool(row and wanted["page"] in row["pages"]),
                       "level_correct": bool(row and row["level"] == wanted["level"]),
                       "expected_parent_ref": expected_parent,
                       "inferred_parent_correct": bool(row and row["inferred_parent"] == expected_parent),
                       "actual_parent_matches_expected_section": bool(row and row["actual_parent"] == expected_parent)})
        if row:
            positions.append(found[0][0])
    return {"nodes": result, "expected_count": len(expected),
            "unique_heading_count": sum(row["unique_heading"] for row in result),
            "page_correct_count": sum(row["page_correct"] for row in result),
            "level_correct_count": sum(row["level_correct"] for row in result),
            "inferred_parent_correct_count": sum(row["inferred_parent_correct"] for row in result),
            "actual_parent_matches_expected_section_count": sum(row["actual_parent_matches_expected_section"] for row in result),
            "selected_relative_order_correct": len(positions) == len(expected) and positions == sorted(set(positions))}


def lane_review(name, cases):
    path = WORK / "runtime" / f"{name}-final"
    manifest = read(path / "input-manifest.json")
    original = read(manifest["old_document"])
    before = read(path / "document-before.json")
    normalization = differences(original, before)
    residual = differences(normalize_load(original), normalize_load(before))
    result = {"input_manifest": manifest,
              "source_pdf_hash_correct": digest(manifest["pdf"]) == manifest["pdf_sha256"],
              "old_document_hash_correct": digest(manifest["old_document"]) == manifest["old_document_sha256"],
              "persisted_input_hashes_correct": all(digest(path / f) == value for f, value in manifest["input_hashes"].items()),
              "outline_hash_correct": digest(path / "outline.json") == manifest["outline_sha256"],
              "normalization": {"raw_change_count": len(normalization),
                                "terminal_path_counts": dict(Counter(d["path"].rsplit("/", 1)[-1] for d in normalization)),
                                "residual_after_alias_and_null_default_normalization": residual},
              "artifact_sha256": {}, "variants": {}}
    execution = read(path / "bounded-execution.json")
    result["execution"] = {key: execution[key] for key in
        ("status", "seconds", "max_sampled_rss_bytes", "limits", "runner_sha256")}
    result["execution"]["runner_hashes_still_match"] = all(
        digest(WORK / "runtime" / f) == value for f, value in execution["runner_sha256"].items())
    expected = {case["id"]: case["details"]["oracle"].get("heading_nodes", []) for case in cases}
    if name == "controls-p1":
        oracle = cases[0]["details"]["oracle"]
        expected["G1-C07"] = [{"title": t, "level": 1, "page": 1} for t in oracle["level1"][:1]]
        expected["G1-C07"] += [{"title": t, "level": 2, "page": 1, "parent_title": oracle["level1"][0]}
                                for t in oracle["level2_under_mathematical_structures"]]
        expected["G1-C07"] += [{"title": oracle["level1"][1], "level": 1, "page": 1}]
    selected_pages = set(p for case in cases for p in case["physical_pages_1based"])
    selected_titles = {node["title"] for nodes in expected.values() for node in nodes}
    for variant in ("before", "fresh", "no-outline", "reloaded"):
        p = path / f"document-{variant}.json"
        if not p.exists():
            continue
        document = read(p)
        result["artifact_sha256"][p.name] = digest(p)
        audit = stage_audit(before, document)
        audit["cases"] = {case_id: score(document, nodes) for case_id, nodes in expected.items()}
        audit["selected_scope_extra_heading_roles"] = [row for row in headings(document)
            if selected_pages.intersection(row["pages"]) and row["title"] not in selected_titles]
        audit["selected_scope_extra_heading_role_count"] = len(audit["selected_scope_extra_heading_roles"])
        if name == "controls-p1":
            title = cases[0]["details"]["oracle"]["title"]
            title_items = [t for t in document["texts"] if t["text"] == title]
            audit["title_role"] = {"expected_title": title, "observed_labels": [t["label"] for t in title_items],
                "title_content_present": len(title_items) == 1,
                "distinct_title_role_recovered": len(title_items) == 1 and title_items[0]["label"] == "title"}
        # These are scoped negative controls; all unselected full-paper headings remain unscored.
        audit["nonheading_controls"] = [{"ref": t["self_ref"], "label": t["label"], "text": t["text"]}
            for t in document["texts"] if selected_pages.intersection(p["page_no"] for p in t.get("prov", []))
            and t["label"] not in ("section_header", "title")]
        if variant != "before":
            audit["newly_promoted_heading_refs"] = [t["self_ref"] for t, old in zip(document["texts"], before["texts"])
                if t["label"] in ("section_header", "title") and old["label"] not in ("section_header", "title")]
            producer = read(path / f"diff-{variant}.json")
            audit["producer_delta_matches_independent_delta"] = producer == audit["all_changes"]
        result["variants"][variant] = audit
    result["fresh_reloaded_json_identical"] = read(path / "document-fresh.json") == read(path / "document-reloaded.json")
    result["fresh_reloaded_markdown_identical"] = (path / "document-fresh.md").read_bytes() == (path / "document-reloaded.md").read_bytes()
    result["fresh_and_no_outline_same"] = (read(path / "document-fresh.json") == read(path / "document-no-outline.json")) if (path / "document-no-outline.json").exists() else None
    return result


def self_check(before, after, expected):
    tests = {}
    altered = deepcopy(after)
    altered["texts"][89]["level"] = 6
    tests["reject_incorrect_depth"] = score(altered, expected)["level_correct_count"] < len(expected)
    altered = deepcopy(after)
    altered["texts"][89]["parent"] = {"cref": "#/texts/87"}
    tests["reject_parent_change"] = bool(stage_audit(before, altered)["unexpected_changes"])
    altered = deepcopy(after)
    altered["texts"][89]["prov"][0]["page_no"] = 1
    tests["reject_provenance_change"] = bool(stage_audit(before, altered)["unexpected_changes"])
    altered = deepcopy(after)
    altered["body"]["children"][30:32] = reversed(altered["body"]["children"][30:32])
    tests["reject_tree_order_change"] = not stage_audit(before, altered)["tree_order_identical"]
    assert all(tests.values()), tests
    return tests


def main():
    assert digest(FROZEN) == FROZEN_SHA, "frozen oracle changed"
    frozen = read(FROZEN)
    cases = {case["id"]: case for case in frozen["cases"]}
    result = {"format": "pdf-heading-independent-review-v1", "frozen_cases_sha256": digest(FROZEN),
              "checker_sha256": digest(__file__),
              "method": "Read saved source and candidate artifacts only; no package imports or inference. Frozen headings are evaluator expectations only.",
              "lanes": {"wikiskill": lane_review("wikiskill", [cases["G1-S02"], cases["G1-S03"]]),
                        "controls-p1": lane_review("controls-p1", [cases["G1-C07"]])}}
    result["independent_raw_bookmark_check"] = read(WORK / "review/bookmark-raw-check.json")
    path = WORK / "runtime/wikiskill-final"
    result["self_checks"] = self_check(read(path / "document-before.json"), read(path / "document-fresh.json"),
                                       cases["G1-S02"]["details"]["oracle"]["heading_nodes"])
    (WORK / "review/output-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"self_checks": result["self_checks"], "lanes": {
        name: {"normalization_residual": len(lane["normalization"]["residual_after_alias_and_null_default_normalization"]),
               "variants": {v: {"changes": a["changes"], "unexpected": len(a["unexpected_changes"]),
                   "graph_errors": len(a["after_graph_errors"]),
                   "scores": {c: {k: s[k] for k in ("level_correct_count", "inferred_parent_correct_count", "expected_count")}
                              for c, s in a["cases"].items()}} for v, a in lane["variants"].items()}}
        for name, lane in result["lanes"].items()}}, indent=2))


if __name__ == "__main__":
    main()
